"""AI 제안 (ADR-0042) — 목록·채택·폐기·지금 실행.

제안 자체는 매일 서버 작업(`app.jobs.ai_daily`)이 계기를 보고 만든다. 화면에서는 채택·폐기만 하고,
시스템관리자는 계기 확인을 바로 돌려 볼 수 있다(`POST /run`).
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_admin
from app.models.ai_proposal import AI_STATUS_LABELS, KIND_LABELS, AiProposal
from app.models.user import User
from app.services import ai_schedule

router = APIRouter(prefix="/api/ai-proposals", tags=["ai-proposals"])


class Note(BaseModel):
    note: str | None = None


class Reason(BaseModel):
    reason: str = ""


def _name(db: Session, uid) -> str | None:
    u = db.get(User, uid) if uid else None
    return u.display_name if u else None


def out(db: Session, p: AiProposal | None) -> dict | None:
    if p is None:
        return None
    return {"id": p.id, "kind": p.kind, "kind_label": KIND_LABELS.get(p.kind, p.kind), "target_id": p.target_id,
            "fiscal_year": p.fiscal_year, "status": p.status, "status_label": AI_STATUS_LABELS.get(p.status, p.status),
            "engine": p.engine, "trigger": p.trigger, "summary": p.summary, "basis": p.basis,
            "created_at": p.created_at, "adopted_by": _name(db, p.adopted_by_id), "adopted_at": p.adopted_at,
            "adopted_changes": p.adopted_changes, "decision_note": p.decision_note}


def _get(db: Session, pid: UUID) -> AiProposal:
    p = db.query(AiProposal).filter(AiProposal.id == pid, AiProposal.is_deleted == False).first()  # noqa: E712
    if p is None:
        raise HTTPException(status_code=404, detail="AI 제안을 찾을 수 없습니다")
    return p


def _run(db: Session, fn) -> None:
    try:
        fn()
    except ai_schedule.AiProposalError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()


@router.get("")
def list_proposals(user: CurrentUser, db: Session = Depends(get_db), status: str | None = None) -> list[dict]:
    q = db.query(AiProposal).filter(AiProposal.is_deleted == False)  # noqa: E712
    if status:
        q = q.filter(AiProposal.status == status)
    return [out(db, p) for p in q.order_by(AiProposal.created_at.desc()).limit(100).all()]


@router.post("/{pid}/adopt")
def adopt(pid: UUID, body: Note, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    p = _get(db, pid)
    _run(db, lambda: ai_schedule.adopt(db, p, user.id, body.note))
    return out(db, p)


@router.post("/{pid}/discard")
def discard(pid: UUID, body: Reason, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    p = _get(db, pid)
    _run(db, lambda: ai_schedule.discard(db, p, user.id, body.reason))
    return out(db, p)


@router.post("/run")
def run_now(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """계기 확인을 지금 돌린다(매일 서버 작업과 같은 것). 만든 제안이 없으면 이유를 돌려준다."""
    created = ai_schedule.propose_schedule(db, date.today())
    db.commit()
    if created is None:
        due = ai_schedule.due_year(db, date.today())
        why = "아직 계기가 아닙니다(회계연도 종료 30일 전부터)" if due is None else f"{due} 회계연도 일정안·제안이 이미 있습니다"
        return {"created": [], "message": why}
    return {"created": [out(db, created)], "message": "제안을 만들었습니다"}
