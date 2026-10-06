"""통제 변경 결재 API (2026-10-06) — 임시저장·상신·조직장 결재·일괄 상신·내부회계관리자 결재 (services/control_changes.py)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_write, tenant_roles
from app.models.control_change import (
    B_REVIEW,
    CH_DEPT_APPROVED,
    CH_DEPT_REVIEW,
    STATUS_LABELS,
    ControlChange,
    ControlChangeBatch,
)
from app.models.role_assignment import ROLE_ICFR_MANAGER
from app.models.user import User
from app.schemas.rcm import ControlUpdate
from app.services import approval
from app.services import control_changes as svc

router = APIRouter(prefix="/api/rcm-changes", tags=["rcm_changes"])
EDITABLE_FIELDS = set(ControlUpdate.model_fields.keys())


class DraftBody(BaseModel):
    changes: dict
    note: str | None = None


class Note(BaseModel):
    note: str | None = None


class BatchBody(BaseModel):
    change_ids: list[UUID] = Field(min_length=1, max_length=500)
    note: str | None = None


class Decision(BaseModel):
    id: UUID
    approve: bool
    note: str | None = None


class DecideBody(BaseModel):
    decisions: list[Decision]
    note: str | None = None


def _run(db: Session, fn):
    try:
        out = fn()
        db.commit()
        return out
    except svc.ChangeError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from None


def _names(db: Session, ids) -> dict:
    ids = {i for i in ids if i}
    return {u.id: u.display_name for u in db.query(User).filter(User.id.in_(ids or {None})).all()}


def _out(db: Session, rows: list[ControlChange], user: User) -> list[dict]:
    names = _names(db, [x for r in rows for x in (r.author_id, r.dept_approver_id, r.admin_decided_by_id)])
    return [{
        "id": r.id, "control_id": r.control_id, "control_code": r.control_code, "control_name": r.control_name,
        "changes": r.changes, "before": r.before, "note": r.note, "status": r.status,
        "status_label": STATUS_LABELS.get(r.status, r.status), "author": names.get(r.author_id),
        "is_mine": r.author_id == user.id, "submitted_at": r.submitted_at,
        "dept_approver": names.get(r.dept_approver_id), "dept_skipped": r.dept_skipped, "dept_note": r.dept_note,
        "dept_decided_at": r.dept_decided_at, "batch_id": r.batch_id, "admin_decided_by": names.get(r.admin_decided_by_id),
        "admin_note": r.admin_note, "rejected_by": r.rejected_by, "updated_at": r.updated_at,
        "can_dept_decide": r.status == CH_DEPT_REVIEW and r.dept_approver_id == user.id,
    } for r in rows]


def _get(db: Session, cid: UUID) -> ControlChange:
    r = db.query(ControlChange).filter(ControlChange.id == cid, ControlChange.is_deleted == False).first()  # noqa: E712
    if r is None:
        raise HTTPException(status_code=404, detail="변경을 찾을 수 없습니다")
    return r


@router.get("")
def overview(user: CurrentUser, db: Session = Depends(get_db),
             include_done: bool = Query(False)) -> dict:
    """화면 한 번에 — 내 변경 · 내가 결재할 조직장 건 · 내부회계 대기함 · 관리자 결재 묶음 · 최근 처리."""
    q = db.query(ControlChange).filter(ControlChange.is_deleted == False)  # noqa: E712
    mine = q.filter(ControlChange.author_id == user.id).order_by(ControlChange.updated_at.desc()).limit(200).all()
    dept = q.filter(ControlChange.status == CH_DEPT_REVIEW, ControlChange.dept_approver_id == user.id).all()
    tier = approval.user_tier(db, user.id)
    queue = q.filter(ControlChange.status == CH_DEPT_APPROVED).order_by(ControlChange.dept_decided_at).all() if tier >= 1 else []
    batches = db.query(ControlChangeBatch).filter(ControlChangeBatch.is_deleted == False).order_by(  # noqa: E712
        ControlChangeBatch.created_at.desc()).limit(30 if include_done else 10).all()
    if not include_done:
        batches = [b for b in batches if b.status == B_REVIEW] or batches[:3]
    bnames = _names(db, [x for b in batches for x in (b.submitted_by_id, b.decided_by_id)])
    is_master = ROLE_ICFR_MANAGER in tenant_roles(db, user.id)
    return {
        "mine": _out(db, mine, user), "dept": _out(db, dept, user), "queue": _out(db, queue, user),
        "batches": [{
            "id": b.id, "status": b.status, "submitted_by": bnames.get(b.submitted_by_id), "created_at": b.created_at,
            "note": b.note, "item_count": b.item_count, "decided_by": bnames.get(b.decided_by_id), "decided_at": b.decided_at,
            "result": b.result,
            "can_decide": b.status == B_REVIEW and is_master and b.submitted_by_id != user.id,
            "items": _out(db, db.query(ControlChange).filter(ControlChange.batch_id == b.id).all(), user),
        } for b in batches],
        "can": {"batch_submit": tier >= 1, "direct_edit": svc.direct_edit_allowed(db, user.id)},
    }


@router.get("/control/{control_id}")
def for_control(control_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    """통제 편집 창용 — 진행 중인 변경(있으면)과 바로 반영 가능 여부."""
    ch = svc.active_for(db, control_id)
    return {"change": _out(db, [ch], user)[0] if ch else None, "direct_edit": svc.direct_edit_allowed(db, user.id)}


@router.put("/control/{control_id}")
def save_draft(control_id: UUID, body: DraftBody, user: User = Depends(require_write), db: Session = Depends(get_db)) -> dict:
    ch = _run(db, lambda: svc.save_draft(db, control_id, user.id, body.changes, body.note, EDITABLE_FIELDS))
    return _out(db, [ch], user)[0]


@router.post("/{cid}/submit")
def submit(cid: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> dict:
    ch = _get(db, cid)
    _run(db, lambda: svc.submit(db, ch, user.id))
    return _out(db, [ch], user)[0]


@router.post("/{cid}/withdraw")
def withdraw(cid: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> dict:
    ch = _get(db, cid)
    _run(db, lambda: svc.withdraw(db, ch, user.id))
    return _out(db, [ch], user)[0]


@router.post("/{cid}/dept-approve")
def dept_approve(cid: UUID, body: Note, user: User = Depends(require_write), db: Session = Depends(get_db)) -> dict:
    ch = _get(db, cid)
    _run(db, lambda: svc.dept_decide(db, ch, user.id, True, body.note))
    return _out(db, [ch], user)[0]


@router.post("/{cid}/dept-reject")
def dept_reject(cid: UUID, body: Note, user: User = Depends(require_write), db: Session = Depends(get_db)) -> dict:
    ch = _get(db, cid)
    _run(db, lambda: svc.dept_decide(db, ch, user.id, False, body.note))
    return _out(db, [ch], user)[0]


@router.post("/batches")
def submit_batch(body: BatchBody, user: User = Depends(require_write), db: Session = Depends(get_db)) -> dict:
    b = _run(db, lambda: svc.submit_batch(db, body.change_ids, user.id, body.note))
    return {"id": b.id, "item_count": b.item_count}


@router.post("/batches/{bid}/decide")
def decide_batch(bid: UUID, body: DecideBody, user: User = Depends(require_write), db: Session = Depends(get_db)) -> dict:
    from app.api.rcm import _apply_control_update
    b = db.query(ControlChangeBatch).filter(ControlChangeBatch.id == bid, ControlChangeBatch.is_deleted == False).first()  # noqa: E712
    if b is None:
        raise HTTPException(status_code=404, detail="묶음을 찾을 수 없습니다")
    decisions = {d.id: (d.approve, d.note) for d in body.decisions}
    return _run(db, lambda: svc.decide_batch(db, b, user.id, decisions, body.note, _apply_control_update))

