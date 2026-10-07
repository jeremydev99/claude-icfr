"""결재 흐름 공통 (ADR-0038 2-1) — `approval_states` 를 쓰는 문서(재무제표부터, 이후 미비점·평가 결론·RCM)의 전이.

판정은 `approval.can` 하나뿐이다(스코핑과 같은 규칙). 여기는 **전이 실행**만 한다 — 상태 칸 바꾸기, 이력
(`governance_events`) 남기기, 재오픈 요청·외부 승인 기록. 문서별로 다른 일(검토 요청 전 검증, 확정 처리, 재오픈 처리)은
`DocHooks` 로 받는다.

스코핑은 1단계 구현(`api/scoping.py`)을 그대로 둔다 — 자기 표의 칸을 쓰기 때문이다(2026-10-07 결정).

오류는 `FlowError(status_code, detail)` 하나로 올린다. API 가 그대로 HTTPException 으로 바꾼다.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.minio_client import build_governance_key, upload_object
from app.models.governance import (
    AS_CONFIRMED,
    AS_DRAFT,
    AS_REVIEW,
    EV_APPROVE,
    EV_EXTERNAL_APPROVE,
    EV_REOPEN_APPROVE,
    EV_REOPEN_REJECT,
    EV_REOPEN_REQUEST,
    EV_REVIEW_DONE,
    EV_REVIEW_RETURN,
    EV_SUBMIT,
    EV_WITHDRAW,
    EXTERNAL_BODIES,
    PATH_EXTERNAL,
    PATH_LEAD_THEN_MASTER,
    REOPEN_APPROVED,
    REOPEN_REJECTED,
    ApprovalState,
    ExternalApproval,
    GovernanceFile,
    ReopenRequest,
)
from app.services import approval

ALLOWED_EVIDENCE = {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/tiff"}
MAX_EVIDENCE_BYTES = 20 * 1024 * 1024


class FlowError(Exception):
    def __init__(self, status_code: int, detail):
        super().__init__(detail if isinstance(detail, str) else str(detail))
        self.status_code, self.detail = status_code, detail


@dataclass
class DocHooks:
    """문서별 동작. 각 함수는 실패 시 `FlowError` 를 올린다."""
    entity_type: str
    entity_id: UUID
    # 문서가 지금 확정돼 있는가(문서 자기 상태 기준 — 결재 상태 행이 없을 때 판단에 쓴다)
    is_confirmed: Callable[[], bool]
    # 검토 요청 전 점검(검증 관문 등)
    check_submit: Callable[[], None]
    # 승인 → 확정 처리(문서 자기 상태를 확정으로). 사유를 받는다
    confirm: Callable[[UUID, str], None]
    # 재오픈 승인 → 문서를 작성 중으로
    reopen: Callable[[UUID, str], None]


def get_state(db: Session, entity_type: str, entity_id: UUID) -> ApprovalState | None:
    return db.query(ApprovalState).filter(ApprovalState.entity_type == entity_type,
                                          ApprovalState.entity_id == entity_id,
                                          ApprovalState.is_deleted == False).first()  # noqa: E712


def view_state(db: Session, h: DocHooks) -> ApprovalState:
    """판정용 상태 — 행이 없으면 **저장하지 않는** 임시 객체(조회가 쓰기를 만들지 않게)."""
    st = get_state(db, h.entity_type, h.entity_id)
    if st is not None:
        return st
    confirmed = h.is_confirmed()
    return ApprovalState(entity_type=h.entity_type, entity_id=h.entity_id,
                         status=AS_CONFIRMED if confirmed else AS_DRAFT, version=1, legacy_confirmed=confirmed)


def _ensure_state(db: Session, h: DocHooks) -> ApprovalState:
    st = get_state(db, h.entity_type, h.entity_id)
    if st is None:
        st = view_state(db, h)
        db.add(st)
        db.flush()
    return st


def _deny(db: Session, user_id: UUID, why: str) -> FlowError:
    # 마스터인데 막힌 것 = 규칙 위반(자기 승인 등) 409, 단계가 모자란 것 = 403 — 스코핑과 같다
    return FlowError(409 if approval.user_tier(db, user_id) == 3 else 403, why)


def _clear_review(st: ApprovalState) -> None:
    st.review_requested_by_id = st.review_requested_at = st.review_path = None
    st.reviewed_by_id = st.reviewed_at = None


def _rec(db: Session, h: DocHooks, st: ApprovalState, action: str, *, reason: str | None = None,
         after: dict | None = None) -> None:
    glog.record(db, h.entity_id, action, version=st.version, reason=reason, after=after, entity_type=h.entity_type)


def submit(db: Session, h: DocHooks, user_id: UUID, reason: str | None) -> None:
    """작성 중 → 검토 중. 요청자 단계로 승인 경로를 정해 저장한다."""
    st = view_state(db, h)
    if st.status != AS_DRAFT:
        raise FlowError(409, "작성 중인 문서만 검토 요청할 수 있습니다")
    c = approval.can(db, st, user_id)
    if not c.submit:
        raise FlowError(403, c.why.get("all", "검토 요청 권한이 없습니다"))
    h.check_submit()
    st = _ensure_state(db, h)
    t = approval.user_tier(db, user_id)
    st.review_path = approval.path_for(t, approval.has_lead(db))
    st.review_requested_by_id, st.review_requested_at = user_id, datetime.now(UTC)
    st.reviewed_by_id = st.reviewed_at = None
    st.status = AS_REVIEW
    _rec(db, h, st, EV_SUBMIT, reason=reason, after={"승인 경로": st.review_path})


def back_to_draft(db: Session, h: DocHooks, user_id: UUID, reason: str | None) -> None:
    """검토 중 → 작성 중 — 요청자 **회수** 또는 검토·승인자 **반려**(사유 필수)."""
    st = view_state(db, h)
    if st.status != AS_REVIEW:
        raise FlowError(409, "검토 중인 문서가 아닙니다")
    c = approval.can(db, st, user_id)
    if c.withdraw:
        action = EV_WITHDRAW
    elif c.review_return:
        if not reason:
            raise FlowError(422, "반려 사유가 필요합니다")
        action = EV_REVIEW_RETURN
    else:
        raise FlowError(403, "요청자(회수) 또는 검토·승인 권한자(반려)만 되돌릴 수 있습니다")
    _clear_review(st)
    st.status = AS_DRAFT
    _rec(db, h, st, action, reason=reason)


def review(db: Session, h: DocHooks, user_id: UUID, action: str, reason: str | None) -> None:
    """책임관리자 검토 — 경로 `lead_then_master` 에서만. done | return."""
    st = view_state(db, h)
    if st.status != AS_REVIEW or st.review_path != PATH_LEAD_THEN_MASTER or st.reviewed_by_id is not None:
        raise FlowError(409, "책임관리자 검토 단계가 아닙니다")
    c = approval.can(db, st, user_id)
    if not c.review:
        raise FlowError(409, c.why.get("review", "검토할 수 없습니다"))
    if action == "done":
        st.reviewed_by_id, st.reviewed_at = user_id, datetime.now(UTC)
        _rec(db, h, st, EV_REVIEW_DONE, reason=reason)
        return
    if not reason:
        raise FlowError(422, "반려 사유가 필요합니다")
    _clear_review(st)
    st.status = AS_DRAFT
    _rec(db, h, st, EV_REVIEW_RETURN, reason=reason)


def _do_confirm(db: Session, h: DocHooks, st: ApprovalState, user_id: UUID, reason: str) -> None:
    h.confirm(user_id, reason)
    st.status = AS_CONFIRMED
    st.confirmed_by_id, st.confirmed_at = user_id, datetime.now(UTC)


def approve(db: Session, h: DocHooks, user_id: UUID, reason: str | None) -> None:
    """검토 중 → 확정 — 마스터관리자, **요청자·검토자 본인 불가**. 사유 필수."""
    st = view_state(db, h)
    if st.status != AS_REVIEW:
        raise FlowError(409, "검토 중인 문서가 아닙니다")
    c = approval.can(db, st, user_id)
    if not c.approve:
        raise _deny(db, user_id, c.why.get("approve", "승인할 수 없습니다"))
    if not reason:
        raise FlowError(422, "확정 사유가 필요합니다")
    _do_confirm(db, h, st, user_id, reason)
    _rec(db, h, st, EV_APPROVE, reason=reason)


def request_reopen(db: Session, h: DocHooks, user_id: UUID, reason: str) -> None:
    """확정 문서 재오픈 요청 — 사유 필수, 미결 요청은 하나만. 이전 방식 확정분도 여기서 결재 상태 행이 생긴다."""
    st = view_state(db, h)
    if st.status != AS_CONFIRMED:
        raise FlowError(409, "확정된 문서만 재오픈을 요청할 수 있습니다")
    if approval.user_tier(db, user_id) == 0:
        raise FlowError(403, "내부회계 관리자(일반·책임·마스터) 역할이 필요합니다")
    if approval.pending_reopen(db, h.entity_id) is not None:
        raise FlowError(409, "이미 결정 대기 중인 재오픈 요청이 있습니다")
    reason = (reason or "").strip()
    if not reason:
        raise FlowError(422, "재오픈 사유가 필요합니다")
    st = _ensure_state(db, h)
    db.add(ReopenRequest(entity_type=h.entity_type, entity_id=h.entity_id, requested_by_id=user_id,
                         requested_tier=approval.user_tier(db, user_id), reason=reason))
    _rec(db, h, st, EV_REOPEN_REQUEST, reason=reason)


def _do_reopen(db: Session, h: DocHooks, st: ApprovalState, user_id: UUID, reason: str) -> None:
    h.reopen(user_id, reason)
    _clear_review(st)
    st.status = AS_DRAFT
    st.confirmed_by_id = st.confirmed_at = None
    st.version = (st.version or 1) + 1


def decide_reopen(db: Session, h: DocHooks, user_id: UUID, request_id: UUID, approve_: bool,
                  reason: str | None) -> None:
    """재오픈 승인·거절 — 마스터관리자, **요청자 본인 불가**. 마스터의 요청은 외부 승인 증빙으로만."""
    st = view_state(db, h)
    r = approval.pending_reopen(db, h.entity_id)
    if r is None or r.id != request_id:
        raise FlowError(404, "결정 대기 중인 재오픈 요청이 없습니다")
    c = approval.can(db, st, user_id)
    if not c.reopen_decide:
        raise _deny(db, user_id, c.why.get("reopen", "재오픈을 결정할 수 없습니다"))
    if not approve_ and not reason:
        raise FlowError(422, "거절 사유가 필요합니다")
    r.status = REOPEN_APPROVED if approve_ else REOPEN_REJECTED
    r.decided_by_id, r.decided_at, r.decision_reason = user_id, datetime.now(UTC), reason
    _rec(db, h, st, EV_REOPEN_APPROVE if approve_ else EV_REOPEN_REJECT, reason=reason, after={"요청 사유": r.reason})
    if approve_:
        _do_reopen(db, h, st, user_id, f"재오픈 승인 — {r.reason}")


@dataclass
class EvidenceFile:
    filename: str
    content_type: str | None
    data: bytes


def record_external(db: Session, h: DocHooks, user_id: UUID, *, purpose: str, approver_body: str,
                    approved_on: str, reference: str | None, files: list[EvidenceFile]) -> None:
    """대표이사·이사회 **외부 승인 기록**(ADR-0038 §2.2.1) — 마스터 작성분의 확정, 마스터 요청 재오픈의 승인.
    증빙 파일 필수(PDF·이미지, 각 20MB). 일반관리자 이상 누구나 등록한다(기록 행위)."""
    if purpose not in ("approve", "reopen"):
        raise FlowError(422, "purpose 는 approve 또는 reopen 입니다")
    if approver_body not in EXTERNAL_BODIES:
        raise FlowError(422, "승인 기관은 대표이사(ceo) 또는 이사회(board)입니다")
    try:
        on = date.fromisoformat(approved_on)
    except ValueError:
        raise FlowError(422, "승인일 형식이 올바르지 않습니다(YYYY-MM-DD)") from None
    real = [f for f in files if f.filename]
    if not real:
        raise FlowError(422, "외부 승인 증빙(의사록·결재 문서 스캔)을 첨부하세요")
    for f in real:
        if len(f.data) > MAX_EVIDENCE_BYTES:
            raise FlowError(413, f"{f.filename}: 20MB 를 넘습니다")
        if (f.content_type or "") not in ALLOWED_EVIDENCE:
            raise FlowError(415, f"{f.filename}: PDF·이미지 파일만 첨부할 수 있습니다")
    st = view_state(db, h)
    c = approval.can(db, st, user_id)
    pend = approval.pending_reopen(db, h.entity_id)
    if purpose == "approve" and not (st.status == AS_REVIEW and st.review_path == PATH_EXTERNAL and c.external_approve):
        raise FlowError(409, "외부 승인 대상(마스터관리자가 검토 요청한 건)이 아닙니다")
    if purpose == "reopen" and not (pend is not None and c.reopen_external):
        raise FlowError(409, "외부 승인이 필요한 재오픈 요청(마스터관리자 요청)이 없습니다")

    ref = (reference or "").strip() or None
    ea = ExternalApproval(entity_type=h.entity_type, entity_id=h.entity_id, purpose=purpose,
                          reopen_request_id=pend.id if purpose == "reopen" else None, approver_body=approver_body,
                          approved_on=on, reference=ref, recorded_by_id=user_id)
    db.add(ea)
    db.flush()
    names = []
    for f in real:
        gf = GovernanceFile(external_approval_id=ea.id, filename=f.filename[:300], mime_type=f.content_type,
                            size_bytes=len(f.data), minio_key="pending")
        db.add(gf)
        db.flush()
        gf.minio_key = build_governance_key(h.entity_type, h.entity_id, gf.id)
        upload_object(gf.minio_key, f.data, f.content_type)
        names.append(f.filename)
    label = f"{EXTERNAL_BODIES[approver_body]} 승인 {on.isoformat()}" + (f" · {ref}" if ref else "")
    st = _ensure_state(db, h)
    _rec(db, h, st, EV_EXTERNAL_APPROVE, reason=label,
         after={"목적": "확정" if purpose == "approve" else "재오픈", "증빙": names})
    if purpose == "approve":
        _do_confirm(db, h, st, user_id, label)
    else:
        pend.status, pend.decided_by_id, pend.decided_at = REOPEN_APPROVED, user_id, datetime.now(UTC)
        pend.decision_reason = label
        _do_reopen(db, h, st, user_id, f"재오픈 외부 승인 — {pend.reason}")
