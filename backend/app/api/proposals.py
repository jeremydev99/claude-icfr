"""제안 결재 API — 목록·상세·항목 결정(1차)·검토 완료·2차 승인·반려·이력 (services/proposals.py)."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_staff
from app.models.governance import GovernanceEvent
from app.models.proposal import ENTITY_PROPOSAL, P_STATUS_LABELS, Proposal, ProposalItem
from app.models.user import User
from app.services import proposals as svc

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


class Person(BaseModel):
    id: UUID
    name: str


class ItemOut(BaseModel):
    id: UUID
    sort_order: int
    account_id: UUID | None
    statement_type: str | None
    account_name: str
    group_label: str | None
    action: str
    template_account_id: UUID | None
    template_name: str | None
    rationale: str
    decision: str
    decided_by: Person | None
    decided_at: datetime | None
    decision_note: str | None
    final_template_account_id: UUID | None
    final_template_name: str | None


class CanOut(BaseModel):
    decide: bool
    review_done: bool
    approve: bool
    return_: bool
    why: dict[str, str]


class ProposalOut(BaseModel):
    id: UUID
    kind: str
    title: str
    summary: str | None
    status: str
    status_label: str
    proposed_by: str
    template_code: str | None
    template_version: int | None
    scoping_id: UUID | None
    reviewed_by: Person | None
    reviewed_at: datetime | None
    approved_by: Person | None
    approved_at: datetime | None
    closed_reason: str | None
    result: dict | None
    created_at: datetime
    counts: dict[str, int]
    items: list[ItemOut] = []
    can: CanOut | None = None


class Decide(BaseModel):
    decision: str = Field(pattern="^(accepted|rejected|modified)$")
    template_account_id: UUID | None = None
    note: str | None = None


class Note(BaseModel):
    reason: str | None = None


class EventOut(BaseModel):
    id: UUID
    action: str
    target: str | None
    actor: Person | None
    reason: str | None
    before: dict | None
    after: dict | None
    created_at: datetime


def _person(db: Session, uid) -> Person | None:
    if uid is None:
        return None
    u = db.get(User, uid)
    return Person(id=uid, name=u.display_name if u else "(삭제된 사용자)")


def _get(db: Session, pid: UUID) -> Proposal:
    p = db.query(Proposal).filter(Proposal.id == pid, Proposal.is_deleted == False).first()  # noqa: E712
    if p is None:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    return p


def _out(db: Session, p: Proposal, user_id: UUID | None, with_items: bool) -> ProposalOut:
    items = svc.items_of(db, p)
    counts: dict[str, int] = {"total": len(items)}
    for i in items:
        counts[i.decision] = counts.get(i.decision, 0) + 1
    out = ProposalOut(
        id=p.id, kind=p.kind, title=p.title, summary=p.summary, status=p.status,
        status_label=P_STATUS_LABELS.get(p.status, p.status), proposed_by=p.proposed_by,
        template_code=p.template_code, template_version=p.template_version, scoping_id=p.scoping_id,
        reviewed_by=_person(db, p.reviewed_by_id), reviewed_at=p.reviewed_at,
        approved_by=_person(db, p.approved_by_id), approved_at=p.approved_at, closed_reason=p.closed_reason,
        result=p.result, created_at=p.created_at, counts=counts)
    if with_items:
        out.items = [ItemOut(
            id=i.id, sort_order=i.sort_order, account_id=i.account_id, statement_type=i.statement_type,
            account_name=i.account_name, group_label=i.group_label, action=i.action,
            template_account_id=i.template_account_id, template_name=i.template_name, rationale=i.rationale,
            decision=i.decision, decided_by=_person(db, i.decided_by_id), decided_at=i.decided_at,
            decision_note=i.decision_note, final_template_account_id=i.final_template_account_id,
            final_template_name=i.final_template_name) for i in items]
        if user_id is not None:
            c = svc.can(db, p, user_id)
            out.can = CanOut(decide=c.decide, review_done=c.review_done, approve=c.approve, return_=c.return_,
                             why=c.why)
    return out


@router.get("", response_model=list[ProposalOut])
def list_proposals(user: CurrentUser, db: Session = Depends(get_db), kind: str | None = None) -> list[ProposalOut]:
    q = db.query(Proposal).filter(Proposal.is_deleted == False)  # noqa: E712
    if kind:
        q = q.filter(Proposal.kind == kind)
    return [_out(db, p, None, False) for p in q.order_by(Proposal.created_at.desc()).limit(100).all()]


@router.get("/{pid}", response_model=ProposalOut)
def get_proposal(pid: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> ProposalOut:
    return _out(db, _get(db, pid), user.id, True)


def _run(db: Session, fn) -> None:
    try:
        fn()
    except svc.ProposalError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from None
    db.commit()


@router.post("/{pid}/items/{iid}/decide", response_model=ProposalOut)
def decide(pid: UUID, iid: UUID, body: Decide, user: User = Depends(require_icfr_staff),
           db: Session = Depends(get_db)) -> ProposalOut:
    p = _get(db, pid)
    item = db.query(ProposalItem).filter(ProposalItem.id == iid, ProposalItem.proposal_id == p.id,
                                         ProposalItem.is_deleted == False).first()  # noqa: E712
    if item is None:
        raise HTTPException(status_code=404, detail="제안 항목을 찾을 수 없습니다")
    _run(db, lambda: svc.decide_item(db, p, item, user.id, body.decision, body.template_account_id, body.note))
    return _out(db, p, user.id, True)


@router.post("/{pid}/review-done", response_model=ProposalOut)
def review_done(pid: UUID, body: Note, user: User = Depends(require_icfr_staff),
                db: Session = Depends(get_db)) -> ProposalOut:
    p = _get(db, pid)
    _run(db, lambda: svc.review_done(db, p, user.id, body.reason))
    return _out(db, p, user.id, True)


@router.post("/{pid}/approve", response_model=ProposalOut)
def approve(pid: UUID, body: Note, user: User = Depends(require_icfr_staff),
            db: Session = Depends(get_db)) -> ProposalOut:
    p = _get(db, pid)
    _run(db, lambda: svc.approve(db, p, user.id, body.reason))
    return _out(db, p, user.id, True)


@router.post("/{pid}/return", response_model=ProposalOut)
def return_(pid: UUID, body: Note, user: User = Depends(require_icfr_staff),
            db: Session = Depends(get_db)) -> ProposalOut:
    p = _get(db, pid)
    _run(db, lambda: svc.return_(db, p, user.id, body.reason or ""))
    return _out(db, p, user.id, True)


@router.get("/{pid}/events", response_model=list[EventOut])
def events(pid: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> list[EventOut]:
    p = _get(db, pid)
    rows = db.query(GovernanceEvent).filter(GovernanceEvent.entity_type == ENTITY_PROPOSAL,
                                            GovernanceEvent.entity_id == p.id).order_by(
        GovernanceEvent.id.desc()).limit(2000).all()
    return [EventOut(id=e.id, action=e.action, target=e.target, actor=_person(db, e.actor_id), reason=e.reason,
                     before=e.before, after=e.after, created_at=e.created_at) for e in rows]
