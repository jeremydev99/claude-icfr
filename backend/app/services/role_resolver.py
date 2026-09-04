"""역할 배정 해석 — ADR-0031 §2.3, 3-1.

**저장은 차이만, 조회는 해석.** ADR-0029 §2.1·§2.2 와 같은 원칙이되 구조가 다르다.

`control_resolver._resolve_layer` 와 공용화하지 않았다. 그쪽은 baseline 과 instance
**두 테이블을 병합**하는 구조이고, 이쪽은 **한 테이블 안에서 `scope` 로 우선순위를
가르는** 구조다. 매개변수가 맞지 않아 억지로 합치면 양쪽 다 읽기 어려워진다.
같은 것은 "기본값 위에 예외를 얹는다"는 개념뿐이고 코드 형태는 다르다.

우선순위 (높은 것이 이긴다):
1. `scope='control'` 배정 — 이 통제에만 지정된 것
2. `scope='process'` 배정 — 상위 프로세스의 기본값
3. `dept_approver` 한정 — 통제책임자의 주 소속 부서 책임자에서 **유도**

tenant 필터는 걸지 않는다 — `AuditedBase` 자동 격리(ADR-0025).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.org import Department, UserDepartment
from app.models.role_assignment import (
    CONFLICT_PAIRS,
    CONTROL_ROLES,
    CROSS_LAYER_CONFLICT_PAIRS,
    ROLE_CONTROL_OWNER,
    ROLE_DEPT_APPROVER,
    SCOPE_CONTROL,
    SCOPE_PROCESS,
    RoleAssignment,
    conflict_key,
)
from app.models.user import User

SOURCE_CONTROL = "control"
SOURCE_PROCESS = "process"
SOURCE_DERIVED = "derived"
SOURCE_NONE = "none"


def _assignments_by_target(db: Session) -> dict[tuple[str, UUID], dict[str, RoleAssignment]]:
    """(scope, target_id) → {role_name: 배정}. 한 번 읽어 메모리에서 해석한다 —
    통제마다 쿼리를 돌면 93건에 279회가 된다(ADR-0029 §2.1 과 같은 이유)."""
    result: dict[tuple[str, UUID], dict[str, RoleAssignment]] = {}
    for a in db.query(RoleAssignment).filter(
        RoleAssignment.is_deleted == False,  # noqa: E712
    ).all():
        result.setdefault((a.scope, a.target_id), {})[a.role_name] = a
    return result


def _primary_department_manager(db: Session) -> dict[UUID, tuple[UUID, UUID]]:
    """user_id → (부서 id, 부서 책임자 user_id). 주 소속 기준.

    `dept_approver` 유도에 쓴다. 주 소속이 사용자당 1건임은 DB 부분 유니크가 보장한다.
    """
    memberships = db.query(UserDepartment).filter(
        UserDepartment.is_primary == True,  # noqa: E712
        UserDepartment.is_deleted == False,  # noqa: E712
    ).all()
    if not memberships:
        return {}
    dept_manager = {
        d.id: d.manager_id
        for d in db.query(Department).filter(
            Department.id.in_({m.department_id for m in memberships}),
            Department.is_deleted == False,  # noqa: E712
        ).all()
    }
    return {
        m.user_id: (m.department_id, dept_manager[m.department_id])
        for m in memberships
        if dept_manager.get(m.department_id) is not None
    }


def resolve_roles_for_control(
    db: Session, control_id: UUID, process_id: UUID | None,
    assignments=None, primary_dept=None, user_names=None,
) -> list[dict]:
    """통제 1건의 역할 해석 결과. 각 항목에 **출처(`source`)를 함께 낸다.**

    출처가 없으면 FE 가 "이 통제만 예외 지정된 상태"를 표시할 수 없다
    (RCM 의 source envelope 과 같은 개념).

    반복 호출 시 `assignments`/`primary_dept`/`user_names` 를 넘겨 재조회를 피한다.
    """
    if assignments is None:
        assignments = _assignments_by_target(db)
    if primary_dept is None:
        primary_dept = _primary_department_manager(db)

    by_control = assignments.get((SCOPE_CONTROL, control_id), {})
    by_process = assignments.get((SCOPE_PROCESS, process_id), {}) if process_id else {}

    rows: list[dict] = []
    for role in CONTROL_ROLES:
        if role in by_control:
            a = by_control[role]
            rows.append({"role_name": role, "user_id": a.user_id,
                         "source": SOURCE_CONTROL, "source_id": control_id})
            continue
        if role in by_process:
            a = by_process[role]
            rows.append({"role_name": role, "user_id": a.user_id,
                         "source": SOURCE_PROCESS, "source_id": process_id})
            continue
        rows.append({"role_name": role, "user_id": None,
                     "source": SOURCE_NONE, "source_id": None})

    # dept_approver 유도 — 배정이 없을 때만. 개별 지정·기본값이 있으면 그것이 이긴다.
    approver = next(r for r in rows if r["role_name"] == ROLE_DEPT_APPROVER)
    if approver["source"] == SOURCE_NONE:
        owner = next(r for r in rows if r["role_name"] == ROLE_CONTROL_OWNER)
        if owner["user_id"] is not None and owner["user_id"] in primary_dept:
            dept_id, manager_id = primary_dept[owner["user_id"]]
            approver.update({"user_id": manager_id, "source": SOURCE_DERIVED,
                             "source_id": dept_id})

    if user_names is None:
        ids = {r["user_id"] for r in rows if r["user_id"]}
        user_names = {
            u.id: u.display_name for u in db.query(User).filter(User.id.in_(ids or {None})).all()
        }
    for r in rows:
        r["user_name"] = user_names.get(r["user_id"]) if r["user_id"] else None
    return rows


def is_dept_approval_skipped(resolved: list[dict]) -> bool:
    """부서승인 단계가 성립하지 않는가 — 통제책임자가 곧 부서 책임자인 경우.

    **이것은 이해상충이 아니다**(2026-09-04 정정, ADR-0031 §2.4). 부서승인은
    "상급자가 검토한다"는 뜻인데 통제책임자가 팀장 본인이면 그 위 단계가 없다.
    겸직이 아니라 단계가 없는 것이므로 경고 대신 스킵으로 표시한다.

    **`derived` 유래에 한정하지 않는다.** 통제별로 통제책임자 본인을 부서승인자로
    명시 지정한 경우도 같은 상황이다 — 어느 경로로 같아졌든 검토 단계는 없다.
    """
    by_role = {r["role_name"]: r["user_id"] for r in resolved if r["user_id"]}
    owner = by_role.get(ROLE_CONTROL_OWNER)
    return owner is not None and by_role.get(ROLE_DEPT_APPROVER) == owner


def detect_conflicts(resolved: list[dict], tenant_role_users: dict[str, set[UUID]] | None = None,
                     ) -> list[str]:
    """해석된 역할에서 이해상충 조합을 찾는다. **판정은 통제 단위다**(ADR-0031 §2.4).

    사람 단위로 보면 상호 배정이 불가피한 중소기업에서 전부 걸린다 —
    "이 통제에서 이 조합인가"만 본다.

    `tenant_role_users` 는 테넌트 단위 역할(`icfr_manager`)의 보유자 집합.
    그쪽은 `user_roles` 에 있어(ADR-0031 §3.1) 검사 방식이 다르다.

    **`control_owner = dept_approver` 는 여기서 잡지 않는다**(2026-09-04 정정).
    충돌이 아니라 부서승인 단계 부재이며 `is_dept_approval_skipped` 가 다룬다.
    다만 `derived` 유래 값 자체는 계속 판정 대상이다 — 유도값도 실제 승인자가 되므로
    다른 조합에서는 그대로 본다.
    """
    by_role = {r["role_name"]: r["user_id"] for r in resolved if r["user_id"]}
    found = [
        conflict_key(a, b)
        for a, b in CONFLICT_PAIRS
        if a in by_role and b in by_role and by_role[a] == by_role[b]
    ]
    if tenant_role_users:
        for a, b in CROSS_LAYER_CONFLICT_PAIRS:
            holder = by_role.get(a)
            if holder is not None and holder in tenant_role_users.get(b, set()):
                found.append(conflict_key(a, b))
    return found
