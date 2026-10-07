"""결재 화면 응답 조립 (ADR-0038 2-1) — `approval_states` 를 쓰는 문서 공통. 스코핑은 `api/scoping.py` 의 자체 조립을 쓴다.

응답 모양(`GovernanceInfo`·`GovernanceEventRead`)은 스코핑과 같다 — 화면의 `ApprovalPanel`·이력 탭을 그대로 쓴다.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.governance import (
    AS_DRAFT,
    ApprovalState,
    ExternalApproval,
    GovernanceEvent,
    GovernanceFile,
    ReopenRequest,
)
from app.models.user import User
from app.schemas.scoping import (
    ExternalApprovalRead,
    ExternalFileRead,
    GovernanceCan,
    GovernanceEventRead,
    GovernanceInfo,
    PersonRef,
    ReopenRead,
)
from app.services import approval


def person(db: Session, uid) -> PersonRef | None:
    if uid is None:
        return None
    u = db.get(User, uid)
    return PersonRef(id=uid, name=u.display_name if u else "(삭제된 사용자)")


def _reopen_read(db: Session, r: ReopenRequest) -> ReopenRead:
    return ReopenRead(id=r.id, requested_by=person(db, r.requested_by_id), requested_tier=r.requested_tier,
                      reason=r.reason, status=r.status, decided_by=person(db, r.decided_by_id),
                      decided_at=r.decided_at, decision_reason=r.decision_reason, created_at=r.created_at)


def governance_info(db: Session, st: ApprovalState, user_id: UUID, *, legacy_confirmed_by=None,
                    no_reopen: str | None = None) -> GovernanceInfo:
    """`st` 는 저장된 행이거나 `approval_flow.view_state` 의 임시 객체. 이전 방식 확정분은 확정자를 따로 받는다.
    `no_reopen` 을 주면 재오픈 없는 문서 — 재오픈 버튼을 끄고 그 사유를 보여 준다(미비점 평가 등, ADR-0038 §3.1)."""
    c = approval.can(db, st, user_id)
    if no_reopen and c.reopen_request:
        c.reopen_request = False
        c.why["reopen"] = no_reopen
    t = approval.user_tier(db, user_id)
    pend = approval.pending_reopen(db, st.entity_id)
    exts = db.query(ExternalApproval).filter(ExternalApproval.entity_type == st.entity_type,
                                             ExternalApproval.entity_id == st.entity_id,
                                             ExternalApproval.is_deleted == False).order_by(  # noqa: E712
        ExternalApproval.created_at).all()
    ext_reads = []
    for e in exts:
        files = db.query(GovernanceFile).filter(GovernanceFile.external_approval_id == e.id,
                                                GovernanceFile.is_deleted == False).all()  # noqa: E712
        ext_reads.append(ExternalApprovalRead(
            id=e.id, purpose=e.purpose, approver_body=e.approver_body, approved_on=e.approved_on,
            reference=e.reference, recorded_by=person(db, e.recorded_by_id), created_at=e.created_at,
            files=[ExternalFileRead(id=f.id, filename=f.filename, size_bytes=f.size_bytes) for f in files]))
    return GovernanceInfo(
        version=st.version or 1, my_tier=t, my_tier_label=approval.TIER_LABELS[t], review_path=st.review_path,
        preview_path=approval.path_for(t, approval.has_lead(db)) if st.status == AS_DRAFT and t else None,
        requested_by=person(db, st.review_requested_by_id), requested_at=st.review_requested_at,
        reviewed_by=person(db, st.reviewed_by_id), reviewed_at=st.reviewed_at,
        confirmed_by=person(db, st.confirmed_by_id or legacy_confirmed_by),
        pending_reopen=_reopen_read(db, pend) if pend else None, external_approvals=ext_reads,
        can=GovernanceCan(**{k: getattr(c, k) for k in GovernanceCan.model_fields}),
    )


def events(db: Session, entity_type: str, entity_id: UUID) -> list[GovernanceEventRead]:
    """변경·검토·승인 이력(최신순) — 지울 수 없는 기록(ADR-0038 §2.4)."""
    rows = db.query(GovernanceEvent).filter(GovernanceEvent.entity_type == entity_type,
                                            GovernanceEvent.entity_id == entity_id).order_by(
        GovernanceEvent.id.desc()).limit(2000).all()   # UUIDv7 = 기록 순서
    cache: dict = {}

    def who(uid):
        if uid not in cache:
            cache[uid] = person(db, uid)
        return cache[uid]
    return [GovernanceEventRead(id=e.id, action=e.action, target=e.target, actor=who(e.actor_id), reason=e.reason,
                                before=e.before, after=e.after, version=e.version, created_at=e.created_at)
            for e in rows]
