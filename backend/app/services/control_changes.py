"""통제 변경 결재 서비스 (models/control_change.py) — 임시저장 → 조직장 → 내부회계 담당자 일괄 상신 → 내부회계관리자.

규칙은 여기 하나 — API 와 화면(`can`)이 같은 규칙을 본다.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.core.permissions import has_icfr_manager, tenant_roles
from app.models.control_change import (
    ACTIVE,
    B_DONE,
    B_REVIEW,
    CH_APPLIED,
    CH_DEPT_APPROVED,
    CH_DEPT_REVIEW,
    CH_DRAFT,
    CH_IN_BATCH,
    CH_REJECTED,
    CH_WITHDRAWN,
    ENTITY_CONTROL_CHANGE,
    ControlChange,
    ControlChangeBatch,
)
from app.models.role_assignment import ROLE_DEPT_APPROVER, ROLE_ICFR_MANAGER
from app.services import approval
from app.services.control_resolver import resolve_controls


class ChangeError(ValueError):
    """규칙 위반 — API 409."""


def _now():
    return datetime.now(UTC)


def control_of(db: Session, control_id: UUID) -> dict | None:
    return next((c for c in resolve_controls(db) if c["id"] == control_id), None)


def active_for(db: Session, control_id: UUID) -> ControlChange | None:
    return db.query(ControlChange).filter(ControlChange.control_id == control_id, ControlChange.is_deleted == False,  # noqa: E712
                                          ControlChange.status.in_(ACTIVE)).first()


def direct_edit_allowed(db: Session, user_id: UUID) -> bool:
    """바로 반영 — 내부회계관리자. 회사에 내부회계관리자가 아직 없으면(결재할 사람이 없으면) 종전처럼 누구나."""
    return ROLE_ICFR_MANAGER in tenant_roles(db, user_id) or not has_icfr_manager(db)


def save_draft(db: Session, control_id: UUID, user_id: UUID, changes: dict, note: str | None,
               allowed_fields: set[str]) -> ControlChange:
    c = control_of(db, control_id)
    if c is None:
        raise ChangeError("통제를 찾을 수 없습니다")
    bad = set(changes) - allowed_fields
    if bad:
        raise ChangeError(f"고칠 수 없는 항목입니다: {', '.join(sorted(bad))}")
    # 현재 값과 같은 항목은 변경이 아니다
    changes = {k: v for k, v in changes.items() if c.get(k) != v}
    ch = active_for(db, control_id)
    if ch is not None:
        if ch.author_id != user_id:
            raise ChangeError("다른 사람이 이 통제의 변경을 진행 중입니다 — 끝난 뒤 고치세요")
        if ch.status not in (CH_DRAFT, CH_REJECTED):
            raise ChangeError("상신한 변경은 고칠 수 없습니다 — 반려되거나 회수한 뒤 고치세요")
    else:
        ch = ControlChange(control_id=control_id, author_id=user_id, status=CH_DRAFT, changes={}, before={})
        db.add(ch)
    if not changes:
        raise ChangeError("바뀐 내용이 없습니다")
    ch.control_code, ch.control_name = c.get("code"), c.get("name")
    ch.changes, ch.before = changes, {k: c.get(k) for k in changes}
    ch.note, ch.status = (note or "").strip() or None, CH_DRAFT
    ch.rejected_by = None
    return ch


def dept_approver_for(db: Session, control_id: UUID) -> UUID | None:
    from app.services.role_resolver import resolve_control_process_id, resolve_roles_for_control
    roles = resolve_roles_for_control(db, control_id, resolve_control_process_id(db, control_id))
    return next((r["user_id"] for r in roles if r["role_name"] == ROLE_DEPT_APPROVER and r["user_id"]), None)


def submit(db: Session, ch: ControlChange, user_id: UUID) -> None:
    if ch.author_id != user_id:
        raise ChangeError("작성자만 상신할 수 있습니다")
    if ch.status not in (CH_DRAFT, CH_REJECTED):
        raise ChangeError("이미 상신한 변경입니다")
    if not ch.changes:
        raise ChangeError("바뀐 내용이 없습니다")
    approver = dept_approver_for(db, ch.control_id)
    ch.submitted_at, ch.dept_note, ch.admin_note, ch.batch_id = _now(), None, None, None
    if approver is None or approver == user_id:
        ch.dept_approver_id = approver
        ch.dept_skipped = "조직장 미지정" if approver is None else "작성자가 조직장"
        ch.status, ch.dept_decided_at = CH_DEPT_APPROVED, _now()
    else:
        ch.dept_approver_id, ch.dept_skipped, ch.status = approver, None, CH_DEPT_REVIEW
    glog.record(db, ch.id, "change_submit", version=None, entity_type=ENTITY_CONTROL_CHANGE,
                target=f"{ch.control_code} {ch.control_name}", after={"항목": list(ch.changes), "조직장 단계": ch.dept_skipped or "결재"})


def withdraw(db: Session, ch: ControlChange, user_id: UUID) -> None:
    if ch.author_id != user_id:
        raise ChangeError("작성자만 회수할 수 있습니다")
    if ch.status not in (CH_DRAFT, CH_DEPT_REVIEW, CH_REJECTED):
        raise ChangeError("내부회계 단계로 넘어간 변경은 회수할 수 없습니다")
    ch.status = CH_WITHDRAWN


def dept_decide(db: Session, ch: ControlChange, user_id: UUID, approve: bool, note: str | None) -> None:
    if ch.status != CH_DEPT_REVIEW:
        raise ChangeError("조직장 결재 단계가 아닙니다")
    if ch.dept_approver_id != user_id:
        raise ChangeError("이 변경의 조직장만 결재할 수 있습니다")
    if not approve and not (note or "").strip():
        raise ChangeError("반려 사유가 필요합니다")
    ch.dept_decided_at, ch.dept_note = _now(), (note or "").strip() or None
    if approve:
        ch.status = CH_DEPT_APPROVED
    else:
        ch.status, ch.rejected_by = CH_REJECTED, "dept"
    glog.record(db, ch.id, "change_dept_" + ("approve" if approve else "reject"), version=None,
                entity_type=ENTITY_CONTROL_CHANGE, target=f"{ch.control_code} {ch.control_name}", reason=ch.dept_note)


def submit_batch(db: Session, ids: list[UUID], user_id: UUID, note: str | None) -> ControlChangeBatch:
    """내부회계 담당자(1~3단계)가 조직장 승인된 변경을 묶어 내부회계관리자에게 상신."""
    if approval.user_tier(db, user_id) < 1:
        raise ChangeError("일괄 상신은 내부회계 담당자가 합니다")
    rows = db.query(ControlChange).filter(ControlChange.id.in_(ids), ControlChange.is_deleted == False).all()  # noqa: E712
    if not rows or len(rows) != len(set(ids)):
        raise ChangeError("변경을 찾을 수 없습니다")
    if any(r.status != CH_DEPT_APPROVED for r in rows):
        raise ChangeError("조직장 승인이 끝난 변경만 일괄 상신할 수 있습니다")
    b = ControlChangeBatch(status=B_REVIEW, submitted_by_id=user_id, note=(note or "").strip() or None, item_count=len(rows))
    db.add(b)
    db.flush()
    for r in rows:
        r.status, r.batch_id = CH_IN_BATCH, b.id
    glog.record(db, b.id, "change_batch_submit", version=None, entity_type=ENTITY_CONTROL_CHANGE,
                target=f"통제 변경 {len(rows)}건", reason=b.note)
    return b


def decide_batch(db: Session, b: ControlChangeBatch, user_id: UUID, decisions: dict[UUID, tuple[bool, str | None]],
                 note: str | None, apply_fn) -> dict:
    """내부회계관리자 결재 — 항목별 승인/반려. 승인 항목은 `apply_fn(db, control_id, changes)` 로 반영."""
    if b.status != B_REVIEW:
        raise ChangeError("이미 결재가 끝난 묶음입니다")
    if ROLE_ICFR_MANAGER not in tenant_roles(db, user_id):
        raise ChangeError("결재는 내부회계관리자가 합니다")
    if b.submitted_by_id == user_id:
        raise ChangeError("일괄 상신한 본인은 결재할 수 없습니다 — 자기 승인 금지")
    items = db.query(ControlChange).filter(ControlChange.batch_id == b.id, ControlChange.is_deleted == False).all()  # noqa: E712
    if set(decisions) != {i.id for i in items}:
        raise ChangeError("모든 항목을 승인 또는 반려로 결정하세요")
    applied = rejected = 0
    for i in items:
        ok, n = decisions[i.id]
        if not ok and not (n or "").strip():
            raise ChangeError(f"반려 사유가 필요합니다: {i.control_code}")
        i.admin_decided_by_id, i.admin_decided_at, i.admin_note = user_id, _now(), (n or "").strip() or None
        if ok:
            if not apply_fn(db, i.control_id, dict(i.changes)):
                raise ChangeError(f"통제를 찾을 수 없습니다: {i.control_code}")
            i.status = CH_APPLIED
            applied += 1
        else:
            i.status, i.rejected_by = CH_REJECTED, "admin"
            rejected += 1
        glog.record(db, i.id, "change_admin_" + ("approve" if ok else "reject"), version=None,
                    entity_type=ENTITY_CONTROL_CHANGE, target=f"{i.control_code} {i.control_name}", reason=i.admin_note,
                    before=i.before if ok else None, after=i.changes if ok else None)
    b.status, b.decided_by_id, b.decided_at = B_DONE, user_id, _now()
    b.decision_note, b.result = (note or "").strip() or None, {"applied": applied, "rejected": rejected}
    return b.result
