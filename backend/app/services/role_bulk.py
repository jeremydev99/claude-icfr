"""역할 일괄 배정 (2026-10-06, 마스터 지시 "통제 1개당 모달 1번이면 93개를 언제 하나").

- `matrix` — 프로세스 기본값 + 통제별 해석 역할(출처 포함) + EUC·IUC 사용 수를 한 번에. 화면이 표 하나로 그린다.
- `apply_bulk` — 여러 (대상, 역할, 사람) 변경을 한 번에 적용. 사람이 `None` 이면 그 배정을 지운다.
  이해상충 판정은 단건 API(`create_assignment`)와 같은 규칙(ADR-0031 §2.5)을 **변경이 닿는 통제 전부**에 적용한다 —
  프로세스 기본값을 바꾸면 그 아래 통제가 모두 영향을 받기 때문이다. 정책이 금지면 409, 아니면 사유 필수.
- 저장은 단건과 같은 `role_assignments`(프로세스 기본값 + 통제 예외). 새 표는 없다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.iuc import InformationItem
from app.models.role_assignment import (
    CONTROL_ROLES,
    SCOPE_CONTROL,
    SCOPE_PROCESS,
    ConflictAcknowledgement,
    RoleAssignment,
    conflict_policy_key,
)
from app.models.user import User
from app.services.control_resolver import resolve_controls, resolve_processes
from app.services.role_resolver import (
    _assignments_by_target,
    _primary_department_manager,
    detect_conflicts,
    is_dept_approval_skipped,
    resolve_roles_for_control,
)


class BulkError(ValueError):
    """규칙 위반 — API 409. `conflicts` 가 있으면 화면이 통제별로 보여 준다."""

    def __init__(self, msg: str, conflicts: list[dict] | None = None, blocked: bool = False):
        super().__init__(msg)
        self.conflicts = conflicts or []
        self.blocked = blocked


def _process_of(controls: list[dict], processes: list[dict]) -> dict[UUID, UUID | None]:
    by_code = {p["code"]: p["id"] for p in processes}
    return {c["id"]: by_code.get(c.get("process_code")) for c in controls}


def matrix(db: Session, tenant_role_users: dict[str, set[UUID]]) -> dict:
    controls, processes = resolve_controls(db), resolve_processes(db)
    proc_of = _process_of(controls, processes)
    assignments = _assignments_by_target(db)
    primary = _primary_department_manager(db)
    users = db.query(User).filter(User.is_deleted == False, User.is_active == True).all()  # noqa: E712
    names = {u.id: u.display_name for u in users}
    info: dict[UUID, dict[str, int]] = {}
    for it in db.query(InformationItem).filter(InformationItem.is_deleted == False).all():  # noqa: E712
        d = info.setdefault(it.control_id, {"iuc": 0, "euc": 0})
        d["iuc"] += 1
        d["euc"] += 1 if it.euc_file_id else 0
    out_controls = []
    for c in controls:
        pid = proc_of[c["id"]]
        roles = resolve_roles_for_control(db, c["id"], pid, assignments=assignments, primary_dept=primary,
                                          user_names=names)
        out_controls.append({
            "id": c["id"], "code": c.get("code"), "name": c.get("name"), "process_id": pid,
            "process_code": c.get("process_code"), "is_key_control": bool(c.get("is_key_control")),
            "owner_name": c.get("owner_name"), "iuc_count": info.get(c["id"], {}).get("iuc", 0),
            "euc_count": info.get(c["id"], {}).get("euc", 0), "roles": roles,
            "conflicts": detect_conflicts(roles, tenant_role_users),
            "dept_approval_skipped": is_dept_approval_skipped(roles),
        })
    out_processes = []
    for p in processes:
        bucket = assignments.get((SCOPE_PROCESS, p["id"]), {})
        out_processes.append({"id": p["id"], "code": p["code"], "name": p.get("name"),
                              "roles": {r: ({"user_id": bucket[r].user_id, "user_name": names.get(bucket[r].user_id)}
                                            if r in bucket else None) for r in CONTROL_ROLES}})
    return {"processes": out_processes, "controls": out_controls,
            "users": [{"id": u.id, "name": u.display_name} for u in sorted(users, key=lambda x: x.display_name)]}


@dataclass
class Change:
    scope: str
    target_id: UUID
    role_name: str
    user_id: UUID | None


@dataclass
class BulkResult:
    applied: int = 0
    removed: int = 0
    acknowledged: list[dict] = field(default_factory=list)


def apply_bulk(db: Session, changes: list[Change], reason: str | None, tenant_role_users: dict[str, set[UUID]],
               policy_blocks) -> BulkResult:
    """변경 전체를 메모리에 먼저 반영해 충돌을 본 뒤 저장한다 — 저장하고 되돌리지 않는다."""
    if not changes:
        raise BulkError("바꿀 배정이 없습니다")
    controls, processes = resolve_controls(db), resolve_processes(db)
    ctrl_ids = {c["id"] for c in controls}
    proc_ids = {p["id"] for p in processes}
    proc_of = _process_of(controls, processes)
    user_ids = {u.id for u in db.query(User).filter(User.is_deleted == False).all()}  # noqa: E712
    for ch in changes:
        if ch.role_name not in CONTROL_ROLES:
            raise BulkError(f"알 수 없는 역할입니다: {ch.role_name}")
        if (ch.scope == SCOPE_CONTROL and ch.target_id not in ctrl_ids) or \
                (ch.scope == SCOPE_PROCESS and ch.target_id not in proc_ids) or ch.scope not in (SCOPE_CONTROL, SCOPE_PROCESS):
            raise BulkError("대상 통제·프로세스를 찾을 수 없습니다")
        if ch.user_id is not None and ch.user_id not in user_ids:
            raise BulkError("담당자를 찾을 수 없습니다")

    current = _assignments_by_target(db)
    pending: dict[tuple[str, UUID], dict] = {k: dict(v) for k, v in current.items()}
    for ch in changes:
        b = pending.setdefault((ch.scope, ch.target_id), {})
        if ch.user_id is None:
            b.pop(ch.role_name, None)
        else:
            b[ch.role_name] = type("_Pending", (), {"user_id": ch.user_id})()

    # 영향받는 통제 — 통제 예외는 그 통제, 프로세스 기본값은 그 아래 통제 전부
    touched_procs = {ch.target_id for ch in changes if ch.scope == SCOPE_PROCESS}
    affected = {ch.target_id for ch in changes if ch.scope == SCOPE_CONTROL} | \
        {cid for cid, pid in proc_of.items() if pid in touched_procs}
    primary = _primary_department_manager(db)
    code_of = {c["id"]: c.get("code") for c in controls}
    found: list[dict] = []
    for cid in affected:
        roles = resolve_roles_for_control(db, cid, proc_of.get(cid), assignments=pending, primary_dept=primary,
                                          user_names={})
        keys = detect_conflicts(roles, tenant_role_users)
        if keys:
            found.append({"control_id": cid, "control_code": code_of.get(cid), "keys": keys,
                          "holders": {r["role_name"]: r["user_id"] for r in roles if r["user_id"]}})
    if found:
        blocked = sorted({k for f in found for k in f["keys"] if policy_blocks(conflict_policy_key(*k.split("=")))})
        if blocked:
            raise BulkError(f"정책상 금지된 겸직 조합이 생깁니다: {', '.join(blocked)}", found, blocked=True)
        if not (reason or "").strip():
            raise BulkError(f"겸직 조합이 통제 {len(found)}개에서 생깁니다 — 사유를 입력해야 저장할 수 있습니다", found)

    res = BulkResult()
    for ch in changes:
        row = db.query(RoleAssignment).filter(
            RoleAssignment.scope == ch.scope, RoleAssignment.target_id == ch.target_id,
            RoleAssignment.role_name == ch.role_name, RoleAssignment.is_deleted == False).first()  # noqa: E712
        if ch.user_id is None:
            if row is not None:
                row.is_deleted = True
                res.removed += 1
            continue
        if row is not None:
            if row.user_id != ch.user_id:
                row.user_id = ch.user_id
                res.applied += 1
        else:
            db.add(RoleAssignment(scope=ch.scope, target_id=ch.target_id, role_name=ch.role_name, user_id=ch.user_id))
            res.applied += 1
    for f in found:
        for k in f["keys"]:
            holder = f["holders"].get(k.split("=")[0])   # 겸직한 사람 — 조합의 앞 역할(통제 단위) 보유자
            if holder is None:
                continue
            db.add(ConflictAcknowledgement(scope=SCOPE_CONTROL, target_id=f["control_id"], conflict_key=k,
                                           user_id=holder, reason=reason.strip()))
        res.acknowledged.append({"control_code": f["control_code"], "keys": f["keys"]})
    return res
