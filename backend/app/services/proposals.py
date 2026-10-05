"""제안 결재 규칙·반영 (models/proposal.py). 판정은 여기 하나 — API 와 화면(`can`)이 같은 규칙을 본다.

- 1차: **책임관리자**(단계 2)가 항목별 승인·반려·변경 후 "검토 완료".
- 2차: **마스터관리자**(단계 3), **1차 검토자 본인 불가**(ADR-0038 자기 승인 금지). 승인 순간 반영한다.
- 반려: 1차 단계에선 책임관리자, 2차 단계에선 마스터 — 사유 필수, 묶음이 닫힌다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.models.proposal import (
    D_ACCEPTED,
    D_MODIFIED,
    D_PENDING,
    ENTITY_PROPOSAL,
    ITEM_LINK,
    KIND_CONTROL_LINK,
    KIND_FS_TEMPLATE_LINK,
    P_APPROVED,
    P_PENDING_REVIEW,
    P_RETURNED,
    P_REVIEWED,
    Proposal,
    ProposalItem,
)
from app.models.scoping import STATUS_DRAFT, Scoping, ScopingTemplate
from app.services import approval, scoping_fs
from app.services import fs_template_match as match_svc


class ProposalError(ValueError):
    """규칙 위반 — API 409."""


@dataclass
class PCan:
    decide: bool = False
    review_done: bool = False
    approve: bool = False
    return_: bool = False
    why: dict[str, str] = field(default_factory=dict)


def items_of(db: Session, p: Proposal) -> list[ProposalItem]:
    return db.query(ProposalItem).filter(ProposalItem.proposal_id == p.id,
                                         ProposalItem.is_deleted == False).order_by(  # noqa: E712
        ProposalItem.sort_order).all()


def can(db: Session, p: Proposal, user_id: UUID) -> PCan:
    t = approval.user_tier(db, user_id)
    c = PCan()
    own = p.requested_by_id is not None and user_id == p.requested_by_id   # 사람이 낸 묶음 — 본인 승인 금지
    if p.status == P_PENDING_REVIEW:
        c.decide = c.return_ = t == 2 and not own
        undecided = sum(1 for i in items_of(db, p) if i.decision == D_PENDING)
        c.review_done = t == 2 and not own and undecided == 0
        if own:
            c.why["review"] = "검토를 요청한 본인은 승인할 수 없습니다 — 자기 승인 금지"
        elif t != 2:
            c.why["review"] = "1차 승인은 책임관리자가 합니다"
        elif undecided:
            c.why["review"] = f"결정하지 않은 항목이 {undecided}개 남았습니다"
    elif p.status == P_REVIEWED:
        c.approve = c.return_ = t == 3 and user_id != p.reviewed_by_id and not own
        if not c.approve:
            c.why["approve"] = ("1차 검토자는 2차 승인을 할 수 없습니다 — 자기 승인 금지" if user_id == p.reviewed_by_id
                                else "검토를 요청한 본인은 승인할 수 없습니다 — 자기 승인 금지" if own
                                else "2차 승인은 마스터관리자가 합니다")
    return c


def create(db: Session, *, kind: str, title: str, summary: str | None, proposed_by: str, items: list[dict],
           template: ScopingTemplate | None = None, scoping_id: UUID | None = None) -> Proposal:
    p = Proposal(kind=kind, title=title, summary=summary, proposed_by=proposed_by, status=P_PENDING_REVIEW,
                 template_code=template.code if template else None,
                 template_version=template.version if template else None, scoping_id=scoping_id)
    db.add(p)
    db.flush()
    for n, it in enumerate(items, start=1):
        db.add(ProposalItem(proposal_id=p.id, sort_order=n, **it))
    glog.record(db, p.id, "proposal_create", version=None, entity_type=ENTITY_PROPOSAL, target=title,
                reason=summary, after={"항목 수": len(items), "제안자": proposed_by})
    db.flush()
    return p


def decide_item(db: Session, p: Proposal, item: ProposalItem, user_id: UUID, decision: str,
                template_account_id: UUID | None, note: str | None) -> None:
    if not can(db, p, user_id).decide:
        raise ProposalError("지금 이 제안의 항목을 결정할 수 없습니다(1차 승인 단계·책임관리자만)")
    before = {"결정": item.decision, "연결": item.final_template_name}
    if p.kind == KIND_CONTROL_LINK and decision == D_MODIFIED:
        raise ProposalError("통제 연결 항목은 승인 또는 반려만 합니다 — 다른 연결은 보드에서 새로 요청하세요")
    if p.kind == KIND_CONTROL_LINK:
        pass
    elif decision == D_MODIFIED:
        if template_account_id is None:
            raise ProposalError("변경할 템플릿 계정을 고르세요")
        tpl = match_svc.get_template(db, p.template_code, p.template_version)
        t = next((x for x in match_svc.template_accounts(db, tpl) if x.id == template_account_id), None)
        if t is None:
            raise ProposalError("템플릿 계정을 찾을 수 없습니다")
        item.final_template_account_id, item.final_template_name = t.id, t.name
    elif decision == D_ACCEPTED:
        item.final_template_account_id, item.final_template_name = item.template_account_id, item.template_name
    else:
        item.final_template_account_id = item.final_template_name = None
    item.decision, item.decided_by_id, item.decided_at = decision, user_id, datetime.now(UTC)
    item.decision_note = (note or "").strip() or None
    glog.record(db, p.id, "proposal_item_decide", version=None, entity_type=ENTITY_PROPOSAL,
                target=(f"{item.control_code or ''} ↔ {item.account_name}" if p.kind == KIND_CONTROL_LINK
                        else f"{item.statement_type or ''} {item.account_name}".strip()), reason=item.decision_note,
                before=before, after={"결정": decision, "연결": item.final_template_name})


def review_done(db: Session, p: Proposal, user_id: UUID, note: str | None) -> None:
    c = can(db, p, user_id)
    if not c.review_done:
        raise ProposalError(c.why.get("review", "1차 검토를 마칠 수 없습니다"))
    p.status, p.reviewed_by_id, p.reviewed_at = P_REVIEWED, user_id, datetime.now(UTC)
    counts: dict[str, int] = {}
    for i in items_of(db, p):
        counts[i.decision] = counts.get(i.decision, 0) + 1
    glog.record(db, p.id, "proposal_review_done", version=None, entity_type=ENTITY_PROPOSAL,
                reason=(note or "").strip() or None, after=counts)


def return_(db: Session, p: Proposal, user_id: UUID, reason: str) -> None:
    if not can(db, p, user_id).return_:
        raise ProposalError("지금 이 제안을 반려할 수 없습니다")
    if not reason.strip():
        raise ProposalError("반려 사유가 필요합니다")
    p.status, p.closed_reason = P_RETURNED, reason.strip()
    if p.kind == KIND_CONTROL_LINK:
        from app.services import control_links
        control_links.revert_returned(db, p)
    glog.record(db, p.id, "proposal_return", version=None, entity_type=ENTITY_PROPOSAL, reason=reason.strip())


def approve(db: Session, p: Proposal, user_id: UUID, reason: str | None) -> dict:
    """2차 승인 → 반영. 템플릿 연결 제안이면 링크를 만들고, 작성 중 스코핑이면 다시 불러온다."""
    c = can(db, p, user_id)
    if not c.approve:
        raise ProposalError(c.why.get("approve", "2차 승인을 할 수 없습니다"))
    result: dict = {}
    if p.kind == KIND_CONTROL_LINK:
        from app.services import control_links
        result.update(control_links.apply_approved(db, p, items_of(db, p)))
    elif p.kind == KIND_FS_TEMPLATE_LINK:
        pairs = [{"account_id": i.account_id, "template_account_id": i.final_template_account_id,
                  "note": f"제안 결재 반영 — 1차·2차 승인 「{p.title}」"}
                 for i in items_of(db, p)
                 if i.action == ITEM_LINK and i.decision in (D_ACCEPTED, D_MODIFIED)
                 and i.account_id and i.final_template_account_id]
        links, warns = match_svc.confirm(db, p.template_code, p.template_version, pairs, user_id) if pairs else ([], [])
        result.update(linked=len(links), link_warnings=warns[:10])
        s = db.get(Scoping, p.scoping_id) if p.scoping_id else None
        if s is not None and not s.is_deleted and s.status == STATUS_DRAFT:
            tpl = db.query(ScopingTemplate).filter(ScopingTemplate.code == s.template_code,
                                                   ScopingTemplate.version == s.template_version).one()
            summary = scoping_fs.reload_from_fs(db, s, tpl)
            glog.record(db, s.id, "value_change", version=s.version, target="재무제표에서 다시 불러오기",
                        reason=f"연결 제안 2차 승인 반영 「{p.title}」",
                        after={"새 계정 행": summary["rows"], "템플릿 연결": summary["linked"]})
            result.update(scoping_reloaded=True, scoping_rows=summary["rows"], scoping_linked=summary["linked"])
        elif s is not None:
            result.update(scoping_reloaded=False, scoping_note="스코핑이 작성 중이 아니라 다시 불러오지 않았습니다")
    p.status, p.approved_by_id, p.approved_at, p.result = P_APPROVED, user_id, datetime.now(UTC), result
    glog.record(db, p.id, "proposal_approve", version=None, entity_type=ENTITY_PROPOSAL,
                reason=(reason or "").strip() or None, after=result)
    return result
