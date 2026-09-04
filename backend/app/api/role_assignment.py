"""역할 배정 API — 3-1, ADR-0031 §2.2~2.6.

**역할은 사람이 아니라 통제에 붙는다.** 같은 사람이 통제 A에서 통제책임자,
통제 B에서 평가자로 배정될 수 있다 — 이 구조가 §2.2 의 핵심이며, 사람 단위 RBAC 로
만들면 중소기업 실무를 표현할 수 없다.

**이해상충은 막지 않고 경고 + 사유를 기록한다**(§2.5). 정책 토글이 금지로 켜져 있을
때만 409 로 거부한다.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_manager, require_write
from app.models.role_assignment import (
    SCOPE_CONTROL,
    SCOPE_PROCESS,
    ConflictAcknowledgement,
    RoleAssignment,
    TenantPolicy,
    conflict_policy_key,
)
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.schemas.org import (
    ControlRolesRead,
    ResolvedRole,
    RoleAssignmentCreate,
    RoleAssignmentRead,
    TenantPolicyRead,
    TenantPolicyUpsert,
)
from app.services.control_resolver import resolve_controls, resolve_processes
from app.services.role_resolver import (
    _assignments_by_target,
    _primary_department_manager,
    detect_conflicts,
    is_dept_approval_skipped,
    resolve_roles_for_control,
)

router = APIRouter(prefix="/api/org", tags=["org"])


def _tenant_role_users(db: Session) -> dict[str, set[UUID]]:
    """테넌트 단위 역할 → 보유자 집합. `user_roles` 를 읽는다(ADR-0031 §3.1)."""
    result: dict[str, set[UUID]] = {}
    for r in db.query(UserRole).filter(UserRole.is_deleted == False).all():  # noqa: E712
        result.setdefault(r.role_name, set()).add(r.user_id)
    return result


def _assert_target_exists(db: Session, scope: str, target_id: UUID) -> None:
    """대상 존재 검증 — resolver 결과와 대조한다.

    `target_id` 에 FK 를 걸 수 없다(baseline 유래면 `baseline_*.id`, add 면
    `*_instances.id` — 정체성 id 규칙, ADR-0027). DB 가 못 막으므로 여기서 본다.
    """
    if scope == SCOPE_PROCESS:
        if any(p["id"] == target_id for p in resolve_processes(db)):
            return
        raise HTTPException(status_code=404, detail="Process not found")
    if any(c["id"] == target_id for c in resolve_controls(db)):
        return
    raise HTTPException(status_code=404, detail="Control not found")


def _policy_blocks(db: Session, key: str) -> bool:
    """조합별 금지 토글. 미설정이면 허용(기본값) — §2.5."""
    row = db.query(TenantPolicy).filter(
        TenantPolicy.policy_key == key,
        TenantPolicy.is_deleted == False,  # noqa: E712
    ).first()
    return row is not None and row.policy_value.lower() in ("true", "1", "yes")


# ── 배정 ──────────────────────────────────────────────────

@router.get("/assignments")
def list_assignments(scope: str | None = None, target_id: UUID | None = None,
                     skip: int = 0, limit: int = 100, user: CurrentUser = None,
                     db: Session = Depends(get_db)) -> dict:
    """저장된 배정 그대로. **해석 결과가 아니다** — 해석은 `/controls/{id}/roles`."""
    q = db.query(RoleAssignment).filter(RoleAssignment.is_deleted == False)  # noqa: E712
    if scope:
        q = q.filter(RoleAssignment.scope == scope)
    if target_id:
        q = q.filter(RoleAssignment.target_id == target_id)
    total = q.count()
    items = q.order_by(RoleAssignment.created_at).offset(skip).limit(limit).all()
    names = {
        u.id: u.display_name
        for u in db.query(User).filter(User.id.in_({a.user_id for a in items} or {None})).all()
    }
    rows = []
    for a in items:
        r = RoleAssignmentRead.model_validate(a)
        r.user_name = names.get(a.user_id)
        rows.append(r)
    return {"items": rows, "total": total, "skip": skip, "limit": limit}


@router.post("/assignments", status_code=status.HTTP_201_CREATED, response_model=RoleAssignmentRead)
def create_assignment(body: RoleAssignmentCreate, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> RoleAssignmentRead:
    """배정 생성/교체. 같은 (대상, 역할) 이 있으면 사람만 바꾼다.

    이해상충이 발생하면:
    - 정책 토글이 금지 → **409 거부**
    - 그 외 → 사유 필수. 없으면 409, 있으면 저장 + 사유를 이력으로 남긴다
    """
    _assert_target_exists(db, body.scope, body.target_id)
    if db.query(User).filter(User.id == body.user_id, User.is_deleted == False).first() is None:  # noqa: E712
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(RoleAssignment).filter(
        RoleAssignment.scope == body.scope,
        RoleAssignment.target_id == body.target_id,
        RoleAssignment.role_name == body.role_name,
        RoleAssignment.is_deleted == False,  # noqa: E712
    ).first()

    # 저장 후 상태를 미리 계산해 충돌을 본다 — 저장하고 되돌리지 않는다.
    assignments = _assignments_by_target(db)
    bucket = assignments.setdefault((body.scope, body.target_id), {})
    bucket[body.role_name] = type("_Pending", (), {"user_id": body.user_id})()

    if body.scope == SCOPE_CONTROL:
        control = next((c for c in resolve_controls(db) if c["id"] == body.target_id), None)
        process_id = _process_of(db, control) if control else None
        resolved = resolve_roles_for_control(
            db, body.target_id, process_id, assignments=assignments,
            primary_dept=_primary_department_manager(db), user_names={},
        )
    else:
        # 프로세스 기본값끼리의 조합만 본다 — 개별 통제 예외는 그 통제 저장 시 판정된다
        resolved = [
            {"role_name": role, "user_id": a.user_id}
            for role, a in bucket.items()
        ]
    conflicts = detect_conflicts(resolved, _tenant_role_users(db))

    if conflicts:
        for key in conflicts:
            role_a, role_b = key.split("=")
            if _policy_blocks(db, conflict_policy_key(role_a, role_b)):
                raise HTTPException(
                    status_code=409,
                    detail=f"정책상 금지된 겸직 조합입니다: {key}",
                )
        if not body.conflict_reason:
            raise HTTPException(
                status_code=409,
                detail=("겸직 조합이 발생합니다(" + ", ".join(conflicts) +
                        "). 사유를 입력해야 저장할 수 있습니다"),
            )

    if existing is not None:
        existing.user_id = body.user_id
        obj = existing
    else:
        obj = RoleAssignment(scope=body.scope, target_id=body.target_id,
                             role_name=body.role_name, user_id=body.user_id)
        db.add(obj)

    for key in conflicts:
        db.add(ConflictAcknowledgement(
            scope=body.scope, target_id=body.target_id, conflict_key=key,
            user_id=body.user_id, reason=body.conflict_reason,
        ))
    db.commit()
    db.refresh(obj)
    row = RoleAssignmentRead.model_validate(obj)
    holder = db.query(User).filter(User.id == obj.user_id).first()
    row.user_name = holder.display_name if holder else None
    return row


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: UUID, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> None:
    obj = db.query(RoleAssignment).filter(
        RoleAssignment.id == assignment_id,
        RoleAssignment.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="RoleAssignment not found")
    obj.is_deleted = True
    db.commit()


# ── 해석 ──────────────────────────────────────────────────

def _process_of(db: Session, control: dict) -> UUID | None:
    """통제의 프로세스 정체성 id. resolve_controls 가 `process_code` 만 주므로 코드로 찾는다."""
    code = control.get("process_code")
    if not code:
        return None
    return next((p["id"] for p in resolve_processes(db) if p["code"] == code), None)


@router.get("/controls/{control_id}/roles", response_model=ControlRolesRead)
def get_control_roles(control_id: UUID, user: CurrentUser = None,
                      db: Session = Depends(get_db)) -> ControlRolesRead:
    """통제 1건의 역할 해석 결과 + 배정 참고 정보.

    각 역할에 **출처**가 붙는다 — 통제별 지정인지, 프로세스 기본값인지, 부서 책임자
    유도인지. `owner_name` 은 문서상 수행자로 함께 싣는다(ADR-0031 §2.4 — 이관하지
    않고 참고 정보로 제공. 배정과 어긋나면 그 자체가 검토 대상이 된다).
    """
    control = next((c for c in resolve_controls(db) if c["id"] == control_id), None)
    if control is None:
        raise HTTPException(status_code=404, detail="Control not found")
    process_id = _process_of(db, control)
    resolved = resolve_roles_for_control(db, control_id, process_id)
    return ControlRolesRead(
        control_id=control_id, control_code=control.get("code"), process_id=process_id,
        owner_name=control.get("owner_name"),
        roles=[ResolvedRole(**r) for r in resolved],
        conflicts=detect_conflicts(resolved, _tenant_role_users(db)),
        dept_approval_skipped=is_dept_approval_skipped(resolved),
    )


# ── 정책 ──────────────────────────────────────────────────

@router.get("/policies")
def list_policies(user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    items = db.query(TenantPolicy).filter(
        TenantPolicy.is_deleted == False,  # noqa: E712
    ).order_by(TenantPolicy.policy_key).all()
    return {"items": [TenantPolicyRead.model_validate(p) for p in items],
            "total": len(items), "skip": 0, "limit": len(items)}


@router.put("/policies", response_model=TenantPolicyRead)
def upsert_policy(body: TenantPolicyUpsert, user: User = Depends(require_icfr_manager),
                  db: Session = Depends(get_db)) -> TenantPolicyRead:
    """정책 설정/변경 — `icfr_manager` 전용 (§2.6)."""
    obj = db.query(TenantPolicy).filter(
        TenantPolicy.policy_key == body.policy_key,
        TenantPolicy.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        obj = TenantPolicy(**body.model_dump())
        db.add(obj)
    else:
        obj.policy_value = body.policy_value
    db.commit()
    db.refresh(obj)
    return TenantPolicyRead.model_validate(obj)


