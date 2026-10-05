"""통제 ↔ 계정 연결 보드 API (ADR-0040) — 보드 조회·자동 매칭·연결 추가/해제(초안)·검토 요청."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_staff
from app.models.control_link import ControlAccountLink
from app.models.user import User
from app.services import control_links as svc

router = APIRouter(prefix="/api/control-links", tags=["control_links"])


class AddBody(BaseModel):
    control_id: UUID
    account_key: str


class SubmitBody(BaseModel):
    note: str | None = None


def _run(db: Session, fn):
    try:
        out = fn()
        db.commit()
        return out
    except svc.LinkError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from None


@router.get("/board")
def get_board(user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    """왼쪽 통제·오른쪽 계정·연결(초안·검토 중·활성)·결재 중 묶음. 조회는 로그인 사용자 누구나."""
    return svc.board(db)


@router.post("/auto")
def auto(user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    return _run(db, lambda: svc.run_auto(db))


@router.post("/links")
def add(body: AddBody, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    row = _run(db, lambda: svc.add_manual(db, body.control_id, body.account_key))
    return {"id": row.id, "state": row.state, "remove_state": row.remove_state}


@router.delete("/links/{lid}")
def remove(lid: UUID, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    row = db.query(ControlAccountLink).filter(ControlAccountLink.id == lid,
                                              ControlAccountLink.is_deleted == False).first()  # noqa: E712
    if row is None:
        raise HTTPException(status_code=404, detail="연결을 찾을 수 없습니다")
    return {"result": _run(db, lambda: svc.remove(db, row))}


@router.post("/submit")
def submit(body: SubmitBody, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    p = _run(db, lambda: svc.submit(db, user.id, user.display_name, body.note))
    return {"proposal_id": p.id}
