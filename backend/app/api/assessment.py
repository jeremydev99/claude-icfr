"""평가 회차·활동·승인 API — 3-2, ADR-0032 §2.1~2.7.

ADR-0020 준수 — 서비스 클래스 없이 직접 함수와 명시적 분기만.
ADR-0025 준수 — 수동 tenant 필터를 걸지 않는다.

**권한 검사는 통제 단위다.** "이 사람이 평가자인가"가 아니라 "이 통제에서 이 사람이
평가자인가"를 본다(ADR-0031 §2.2). 3-1 의 `role_resolver` 를 그대로 쓰며 판정 로직을
복제하지 않는다.
"""
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_manager, require_write
from app.models.assessment import (
    ACTIVITY_RULES,
    APPROVAL_DEPT,
    CYCLE_APPROVED,
    CYCLE_CLOSED,
    CYCLE_DESIGN,
    CYCLE_OPEN,
    CYCLE_OPERATION,
    ActivityApproval,
    AssessmentActivity,
    AssessmentCycle,
    CycleTarget,
)
from app.models.role_assignment import (
    POLICY_DEPT_APPROVAL_ENABLED,
    ROLE_ASSESSOR,
    ROLE_DEPT_APPROVER,
    TenantPolicy,
)
from app.models.user import User
from app.schemas.assessment import (
    ActivityCreate,
    ActivityRead,
    ApprovalCreate,
    ApprovalRead,
    CycleCloseRequest,
    CycleCloseResult,
    CycleCreate,
    CycleRead,
    CycleTargetRead,
    CycleUpdate,
    IncompleteControl,
    PeriodSuggestion,
)
from app.services.assessment_period import (
    current_fiscal_year,
    current_period_index,
    fiscal_year_start_month,
    suggest_period,
)
from app.services.control_resolver import resolve_controls
from app.services.role_resolver import (
    is_dept_approval_skipped,
    resolve_control_process_id,
    resolve_roles_for_control,
)

router = APIRouter(prefix="/api/assessment", tags=["assessment"])

# 회차 종류별 "완료" 판정에 필요한 활동 — 마감 시 미완 판정 기준 (§2.5)
_REQUIRED_ACTIVITIES = {
    CYCLE_DESIGN: ("design", "design_assessment"),
    CYCLE_OPERATION: ("test", "operation_assessment"),
}


def _names(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    return {u.id: u.display_name for u in db.query(User).filter(User.id.in_(ids)).all()}


def _get_cycle_or_404(db: Session, cycle_id: UUID) -> AssessmentCycle:
    obj = db.query(AssessmentCycle).filter(
        AssessmentCycle.id == cycle_id,
        AssessmentCycle.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="AssessmentCycle not found")
    return obj


def _to_cycle_read(db: Session, obj: AssessmentCycle, with_count: bool = True) -> CycleRead:
    row = CycleRead.model_validate(obj)
    names = _names(db, {i for i in (obj.closed_by_id, obj.approved_by_id) if i})
    row.closed_by_name = names.get(obj.closed_by_id) if obj.closed_by_id else None
    row.approved_by_name = names.get(obj.approved_by_id) if obj.approved_by_id else None
    if with_count:
        row.target_count = db.query(CycleTarget).filter(
            CycleTarget.cycle_id == obj.id,
            CycleTarget.is_deleted == False,  # noqa: E712
        ).count()
    return row


def _assert_open(cycle: AssessmentCycle) -> None:
    """마감·최종승인된 회차는 더 이상 기록을 받지 않는다.

    마감 후에도 쓸 수 있으면 "그때 무엇이 완료됐는가"가 사후에 달라진다 —
    미완 사유를 남기고 마감한 의미가 사라진다.
    """
    if cycle.status != CYCLE_OPEN:
        raise HTTPException(
            status_code=409,
            detail=f"마감된 회차에는 기록할 수 없습니다 (상태: {cycle.status})",
        )


def _dept_approval_enabled(db: Session) -> bool:
    """정책 토글. 미설정이면 켜짐이 기본이다(ADR-0031 §2.6 — 부서승인은 선택 단계)."""
    row = db.query(TenantPolicy).filter(
        TenantPolicy.policy_key == POLICY_DEPT_APPROVAL_ENABLED,
        TenantPolicy.is_deleted == False,  # noqa: E712
    ).first()
    if row is None:
        return True
    return row.policy_value.lower() not in ("false", "0", "no")


def _role_holder(db: Session, control_id: UUID, role_name: str) -> UUID | None:
    """이 **통제에서** 해당 역할을 가진 사람. 통제 단위 판정(ADR-0031 §2.2)."""
    process_id = resolve_control_process_id(db, control_id)
    resolved = resolve_roles_for_control(db, control_id, process_id)
    return next((r["user_id"] for r in resolved if r["role_name"] == role_name), None)


# ── 회차 ──────────────────────────────────────────────────

@router.get("/period-suggestion", response_model=PeriodSuggestion)
def get_period_suggestion(frequency: str, period_index: int | None = None,
                          fiscal_year: int | None = None, user: CurrentUser = None,
                          db: Session = Depends(get_db)) -> PeriodSuggestion:
    """기간 제안값. 회차 생성 화면이 미리 받아 채워 넣는다 — **강제가 아니다**(§2.2)."""
    start_month = fiscal_year_start_month(db)
    today = date.today()
    fy = fiscal_year if fiscal_year else current_fiscal_year(today, start_month)
    idx = period_index if period_index else current_period_index(frequency, today, start_month, fy)
    ps, pe = suggest_period(frequency, start_month, fy, idx)
    return PeriodSuggestion(period_start=ps, period_end=pe, fiscal_year=fy,
                            period_index=idx, fiscal_year_start_month=start_month)


@router.get("/cycles")
def list_cycles(kind: str | None = None, status_filter: str | None = None,
                skip: int = 0, limit: int = 100, user: CurrentUser = None,
                db: Session = Depends(get_db)) -> dict:
    q = db.query(AssessmentCycle).filter(AssessmentCycle.is_deleted == False)  # noqa: E712
    if kind:
        q = q.filter(AssessmentCycle.kind == kind)
    if status_filter:
        q = q.filter(AssessmentCycle.status == status_filter)
    total = q.count()
    items = q.order_by(AssessmentCycle.period_start.desc()).offset(skip).limit(limit).all()
    return {"items": [_to_cycle_read(db, c) for c in items],
            "total": total, "skip": skip, "limit": limit}


@router.post("/cycles", status_code=status.HTTP_201_CREATED, response_model=CycleRead)
def create_cycle(body: CycleCreate, user: User = Depends(require_write),
                 db: Session = Depends(get_db)) -> CycleRead:
    """회차 생성 — **`assessor` 만 만들 수 있다**(ADR-0032 §2.1).

    통제책임자는 만들 수 없다. 평가 일정을 실무부서가 정하면 평가자 독립성이 무너진다.
    여기서 `assessor` 판정은 **어느 통제에서든 평가자로 배정된 적이 있는가**로 본다 —
    회차는 특정 통제에 속하지 않으므로 통제 단위 판정을 쓸 수 없다.

    **대상 통제는 이 시점에 스냅샷으로 고정한다.** 주기가 나중에 바뀌어도 과거 회차
    대상은 달라지지 않는다(모델 docstring 참조).
    """
    _assert_can_create_cycle(db, user)

    start_month = fiscal_year_start_month(db)
    today = date.today()
    fy = body.fiscal_year or current_fiscal_year(today, start_month)
    idx = body.period_index or current_period_index(body.frequency, today, start_month, fy)
    default_start, default_end = suggest_period(body.frequency, start_month, fy, idx)

    period_start = body.period_start or default_start
    period_end = body.period_end or default_end
    if period_end < period_start:
        raise HTTPException(status_code=409, detail="평가 종료일이 시작일보다 빠릅니다")

    dup = db.query(AssessmentCycle).filter(
        AssessmentCycle.kind == body.kind,
        AssessmentCycle.name == body.name,
        AssessmentCycle.is_deleted == False,  # noqa: E712
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail=f"회차명 '{body.name}' 은 이미 사용 중입니다")

    cycle = AssessmentCycle(
        kind=body.kind, frequency=body.frequency, name=body.name,
        period_start=period_start, period_end=period_end, due_date=body.due_date,
        status=CYCLE_OPEN,
    )
    db.add(cycle)
    db.flush()

    # 대상 스냅샷 — 회차 주기와 일치하는 **유효 평가주기**를 가진 통제
    for c in resolve_controls(db):
        if c.get("assessment_frequency") == body.frequency:
            db.add(CycleTarget(cycle_id=cycle.id, control_id=c["id"],
                               control_code=c.get("code")))
    db.commit()
    db.refresh(cycle)
    return _to_cycle_read(db, cycle)


def _assert_can_create_cycle(db: Session, user: User) -> None:
    """회차 생성 자격 — 어느 통제에서든 `assessor` 로 배정돼 있어야 한다."""
    from app.models.role_assignment import RoleAssignment

    is_assessor = db.query(RoleAssignment).filter(
        RoleAssignment.role_name == ROLE_ASSESSOR,
        RoleAssignment.user_id == user.id,
        RoleAssignment.is_deleted == False,  # noqa: E712
    ).first() is not None
    if not is_assessor:
        raise HTTPException(
            status_code=403,
            detail="평가 회차는 평가자(전담부서)만 생성할 수 있습니다",
        )


@router.get("/cycles/{cycle_id}", response_model=CycleRead)
def get_cycle(cycle_id: UUID, user: CurrentUser = None,
              db: Session = Depends(get_db)) -> CycleRead:
    return _to_cycle_read(db, _get_cycle_or_404(db, cycle_id))


@router.patch("/cycles/{cycle_id}", response_model=CycleRead)
def update_cycle(cycle_id: UUID, body: CycleUpdate, user: User = Depends(require_write),
                 db: Session = Depends(get_db)) -> CycleRead:
    cycle = _get_cycle_or_404(db, cycle_id)
    _assert_open(cycle)
    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(cycle, f, v)
    if cycle.period_end < cycle.period_start:
        raise HTTPException(status_code=409, detail="평가 종료일이 시작일보다 빠릅니다")
    db.commit()
    db.refresh(cycle)
    return _to_cycle_read(db, cycle)


@router.get("/cycles/{cycle_id}/targets")
def list_cycle_targets(cycle_id: UUID, skip: int = 0, limit: int = 500,
                       user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    """회차 대상 스냅샷. **생성 시점의 사실**이며 이후 주기가 바뀌어도 불변이다."""
    _get_cycle_or_404(db, cycle_id)
    q = db.query(CycleTarget).filter(
        CycleTarget.cycle_id == cycle_id,
        CycleTarget.is_deleted == False,  # noqa: E712
    )
    total = q.count()
    items = q.order_by(CycleTarget.control_code).offset(skip).limit(limit).all()
    return {"items": [CycleTargetRead.model_validate(t) for t in items],
            "total": total, "skip": skip, "limit": limit}


# ── 활동 기록 (§2.3) ──────────────────────────────────────

def _to_activity_read(db: Session, obj: AssessmentActivity,
                      approvals: list[ActivityApproval] | None = None) -> ActivityRead:
    row = ActivityRead.model_validate(obj)
    row.performed_by_name = _names(db, {obj.performed_by_id}).get(obj.performed_by_id)
    if approvals is None:
        approvals = db.query(ActivityApproval).filter(
            ActivityApproval.activity_id == obj.id,
            ActivityApproval.is_deleted == False,  # noqa: E712
        ).all()
    ap_names = _names(db, {a.approved_by_id for a in approvals})
    rows = []
    for a in approvals:
        r = ApprovalRead.model_validate(a)
        r.approved_by_name = ap_names.get(a.approved_by_id)
        rows.append(r)
    row.approvals = rows
    return row


@router.get("/cycles/{cycle_id}/activities")
def list_activities(cycle_id: UUID, control_id: UUID | None = None,
                    skip: int = 0, limit: int = 200, user: CurrentUser = None,
                    db: Session = Depends(get_db)) -> dict:
    """활동 기록. 수행자·수행시각이 함께 나온다 — 감사추적의 실체다(§2.8)."""
    _get_cycle_or_404(db, cycle_id)
    q = db.query(AssessmentActivity).filter(
        AssessmentActivity.cycle_id == cycle_id,
        AssessmentActivity.is_deleted == False,  # noqa: E712
    )
    if control_id:
        q = q.filter(AssessmentActivity.control_id == control_id)
    total = q.count()
    items = q.order_by(AssessmentActivity.performed_at).offset(skip).limit(limit).all()
    return {"items": [_to_activity_read(db, a) for a in items],
            "total": total, "skip": skip, "limit": limit}


@router.post("/cycles/{cycle_id}/activities", status_code=status.HTTP_201_CREATED,
             response_model=ActivityRead)
def create_activity(cycle_id: UUID, body: ActivityCreate, user: User = Depends(require_write),
                    db: Session = Depends(get_db)) -> ActivityRead:
    """활동 기록 — **권한은 통제 단위로 본다**(ADR-0031 §2.2).

    "이 사람이 평가자인가"가 아니라 "이 통제에서 이 사람이 평가자인가"다.
    통제 A 의 평가자가 통제 B 에서 평가를 남길 수 없다.
    """
    cycle = _get_cycle_or_404(db, cycle_id)
    _assert_open(cycle)

    required_role, required_kind = ACTIVITY_RULES[body.activity_kind]
    if cycle.kind != required_kind:
        raise HTTPException(
            status_code=409,
            detail=f"'{body.activity_kind}' 활동은 {required_kind} 회차에만 기록할 수 있습니다",
        )

    target = db.query(CycleTarget).filter(
        CycleTarget.cycle_id == cycle_id,
        CycleTarget.control_id == body.control_id,
        CycleTarget.is_deleted == False,  # noqa: E712
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="이 회차의 대상 통제가 아닙니다")

    if _role_holder(db, body.control_id, required_role) != user.id:
        raise HTTPException(
            status_code=403,
            detail=f"이 통제의 {required_role} 만 '{body.activity_kind}' 을 기록할 수 있습니다",
        )

    obj = AssessmentActivity(
        cycle_id=cycle_id, control_id=body.control_id, activity_kind=body.activity_kind,
        result=body.result, note=body.note,
        performed_by_id=user.id, performed_at=datetime.now(UTC),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _to_activity_read(db, obj, approvals=[])


# ── 승인 (§2.4) ───────────────────────────────────────────

@router.post("/activities/{activity_id}/approvals", status_code=status.HTTP_201_CREATED,
             response_model=ApprovalRead)
def approve_activity(activity_id: UUID, body: ApprovalCreate,
                     user: User = Depends(require_write),
                     db: Session = Depends(get_db)) -> ApprovalRead:
    """부서승인 / 평가자 승인. **최종승인은 여기가 아니다** — 회차 전체 대상이다(§2.6).

    부서승인이 건너뛰어지는 경로는 둘이며 구분해 처리한다.
    - 정책 토글 `dept_approval_enabled` 가 false → **전체** 스킵
    - 해당 통제가 `dept_approval_skipped` → **그 통제만** 스킵
      (통제책임자가 곧 부서 책임자라 검토 단계가 없다, ADR-0031 §2.4 정정)

    둘 다 "승인할 것이 없는" 상태이므로 승인 요청 자체를 409 로 거부한다 —
    없는 단계에 승인 기록을 만들면 그 회차가 무엇을 거쳤는지 왜곡된다.
    """
    activity = db.query(AssessmentActivity).filter(
        AssessmentActivity.id == activity_id,
        AssessmentActivity.is_deleted == False,  # noqa: E712
    ).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="AssessmentActivity not found")
    _assert_open(_get_cycle_or_404(db, activity.cycle_id))

    if body.stage == APPROVAL_DEPT:
        if not _dept_approval_enabled(db):
            raise HTTPException(
                status_code=409,
                detail="부서승인 단계가 비활성화되어 있습니다 (정책: dept_approval_enabled)",
            )
        process_id = resolve_control_process_id(db, activity.control_id)
        if is_dept_approval_skipped(
            resolve_roles_for_control(db, activity.control_id, process_id)
        ):
            raise HTTPException(
                status_code=409,
                detail="이 통제는 통제책임자가 부서 책임자를 겸해 부서승인 단계가 없습니다",
            )
        required_role = ROLE_DEPT_APPROVER
    else:
        required_role = ROLE_ASSESSOR

    if _role_holder(db, activity.control_id, required_role) != user.id:
        raise HTTPException(
            status_code=403, detail=f"이 통제의 {required_role} 만 승인할 수 있습니다")

    dup = db.query(ActivityApproval).filter(
        ActivityApproval.activity_id == activity_id,
        ActivityApproval.stage == body.stage,
        ActivityApproval.is_deleted == False,  # noqa: E712
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="이미 승인된 단계입니다")

    obj = ActivityApproval(
        activity_id=activity_id, stage=body.stage, approved_by_id=user.id,
        approved_at=datetime.now(UTC), note=body.note,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    row = ApprovalRead.model_validate(obj)
    row.approved_by_name = _names(db, {user.id}).get(user.id)
    return row


# ── 마감·최종승인 (§2.5·§2.6) ─────────────────────────────

def _incomplete_controls(db: Session, cycle: AssessmentCycle) -> list[IncompleteControl]:
    """미완 통제 — 회차 종류가 요구하는 활동이 없는 대상.

    **무엇이 없어서 미완인지 함께 낸다.** "3건 미완" 만으로는 담당자가 다음 행동을
    정할 수 없다.
    """
    targets = db.query(CycleTarget).filter(
        CycleTarget.cycle_id == cycle.id,
        CycleTarget.is_deleted == False,  # noqa: E712
    ).all()
    done: dict[UUID, set[str]] = {}
    for a in db.query(AssessmentActivity).filter(
        AssessmentActivity.cycle_id == cycle.id,
        AssessmentActivity.is_deleted == False,  # noqa: E712
    ).all():
        done.setdefault(a.control_id, set()).add(a.activity_kind)

    required = _REQUIRED_ACTIVITIES[cycle.kind]
    result = []
    for t in targets:
        missing = [k for k in required if k not in done.get(t.control_id, set())]
        if missing:
            result.append(IncompleteControl(control_id=t.control_id,
                                            control_code=t.control_code, missing=missing))
    return result


@router.get("/cycles/{cycle_id}/incomplete")
def get_incomplete(cycle_id: UUID, user: CurrentUser = None,
                   db: Session = Depends(get_db)) -> dict:
    """마감 전에 미완 목록을 미리 본다 — 409 를 받고서야 알게 되지 않도록."""
    cycle = _get_cycle_or_404(db, cycle_id)
    items = _incomplete_controls(db, cycle)
    return {"items": items, "total": len(items), "skip": 0, "limit": len(items)}


@router.post("/cycles/{cycle_id}/close", response_model=CycleCloseResult)
def close_cycle(cycle_id: UUID, body: CycleCloseRequest, user: User = Depends(require_write),
                db: Session = Depends(get_db)) -> CycleCloseResult:
    """회차 마감 — **미완이 있어도 마감할 수 있되 사유가 필수다**(ADR-0032 §2.5).

    막으면 회차가 영원히 안 닫히고, 조용히 허용하면 무엇이 빠졌는지 남지 않는다.
    사유 없이 시도하면 **미완 목록과 함께** 409 를 돌려준다(3-1 이해상충과 같은 흐름).

    **마감 단위는 회차다**(§2.4). 통제 단위 마감은 두지 않는다.
    """
    cycle = _get_cycle_or_404(db, cycle_id)
    if cycle.status != CYCLE_OPEN:
        raise HTTPException(status_code=409, detail=f"이미 마감된 회차입니다 (상태: {cycle.status})")
    _assert_can_create_cycle(db, user)   # 마감도 전담부서 권한

    incomplete = _incomplete_controls(db, cycle)
    if incomplete and not body.incomplete_reason:
        shown = ", ".join(i.control_code or str(i.control_id) for i in incomplete[:5])
        more = " 외" if len(incomplete) > 5 else ""
        raise HTTPException(
            status_code=409,
            detail=(f"미완 통제 {len(incomplete)}건이 있습니다({shown}{more}). "
                    "사유를 입력해야 마감할 수 있습니다"),
        )

    cycle.status = CYCLE_CLOSED
    cycle.closed_at = datetime.now(UTC)
    cycle.closed_by_id = user.id
    cycle.incomplete_reason = body.incomplete_reason if incomplete else None
    db.commit()
    db.refresh(cycle)
    return CycleCloseResult(cycle=_to_cycle_read(db, cycle), incomplete=incomplete)


@router.post("/cycles/{cycle_id}/approve", response_model=CycleRead)
def approve_cycle(cycle_id: UUID, user: User = Depends(require_icfr_manager),
                  db: Session = Depends(get_db)) -> CycleRead:
    """최종승인 — `icfr_manager` 가 **회차 전체**에 대해 한다(ADR-0032 §2.6).

    **마감되지 않은 회차는 승인할 수 없다.** 마감이 "이 회차의 작업은 여기까지"를
    확정하는 절차이므로, 그 전에 승인하면 승인 후에도 내용이 바뀔 수 있다.
    """
    cycle = _get_cycle_or_404(db, cycle_id)
    if cycle.status == CYCLE_OPEN:
        raise HTTPException(
            status_code=409, detail="마감되지 않은 회차는 최종승인할 수 없습니다")
    if cycle.status == CYCLE_APPROVED:
        raise HTTPException(status_code=409, detail="이미 최종승인된 회차입니다")

    cycle.status = CYCLE_APPROVED
    cycle.approved_at = datetime.now(UTC)
    cycle.approved_by_id = user.id
    db.commit()
    db.refresh(cycle)
    return _to_cycle_read(db, cycle)
