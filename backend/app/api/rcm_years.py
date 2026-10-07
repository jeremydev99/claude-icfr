"""회계연도 RCM 확정 결재 (ADR-0038 2-5) — `/api/rcm-years`.

회계연도 RCM 을 시작(작성 중) → 검토 요청 → (책임관리자 검토) → 마스터 승인 시 **라이브 RCM 전체 스냅샷**.
확정·검토 중이면 라이브 RCM 쓰기가 잠긴다(`api/rcm.require_rcm_editable`). 재오픈은 요청 → 다른 마스터 승인(버전 +1).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import _approval_view as av
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_staff
from app.models.governance import ENTITY_RCM_YEAR
from app.models.rcm_governance import RcmFiscalYear, RcmSnapshot
from app.models.user import User
from app.schemas.scoping import (
    GovernanceEventRead,
    GovernanceInfo,
    ReopenCreate,
    ReopenDecision,
    ReviewRequest,
    TransitionRequest,
)
from app.services import approval_flow
from app.services import rcm_approval as rap

router = APIRouter(prefix="/api/rcm-years", tags=["rcm-years"])


class RcmYearCreate(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2100)


class SnapshotRead(BaseModel):
    version: int
    control_count: int
    confirmed_by: str | None
    confirmed_at: str


class RcmYearRead(BaseModel):
    id: UUID
    fiscal_year: int
    approval_status: str
    version: int
    is_latest: bool
    snapshots: list[SnapshotRead]
    pending_changes: int            # 상신된 통제 변경 결재 — 남아 있으면 검토 요청 불가
    governance: GovernanceInfo


class RcmLock(BaseModel):
    locked: bool
    reason: str | None
    fiscal_year: int | None
    rcm_year_id: UUID | None


def _get(db: Session, rid: UUID) -> RcmFiscalYear:
    y = db.query(RcmFiscalYear).filter(RcmFiscalYear.id == rid, RcmFiscalYear.is_deleted == False).first()  # noqa: E712
    if y is None:
        raise HTTPException(status_code=404, detail="회계연도 RCM 을 찾을 수 없습니다")
    return y


def _read(db: Session, y: RcmFiscalYear, user_id: UUID) -> RcmYearRead:
    st = approval_flow.view_state(db, rap.hooks(db, y))
    snaps = db.query(RcmSnapshot).filter(RcmSnapshot.rcm_year_id == y.id, RcmSnapshot.is_deleted == False).order_by(  # noqa: E712
        RcmSnapshot.version.desc()).all()
    latest = rap.latest_year(db)
    return RcmYearRead(
        id=y.id, fiscal_year=y.fiscal_year, approval_status=st.status, version=st.version or 1,
        is_latest=latest is not None and latest.id == y.id,
        snapshots=[SnapshotRead(version=s.version, control_count=s.control_count,
                                confirmed_by=(av.person(db, s.confirmed_by_id).name if s.confirmed_by_id else None),
                                confirmed_at=s.confirmed_at.isoformat()) for s in snaps],
        pending_changes=rap.pending_changes(db),
        governance=av.governance_info(db, st, user_id))


def _flow(db: Session, fn) -> None:
    try:
        fn()
    except approval_flow.FlowError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    db.commit()


@router.get("/lock", response_model=RcmLock)
def get_lock(user: CurrentUser, db: Session = Depends(get_db)) -> RcmLock:
    """라이브 RCM 이 잠겼는가 — 화면 상단 안내용."""
    y = rap.latest_year(db)
    why = rap.lock_reason(db)
    return RcmLock(locked=why is not None, reason=why, fiscal_year=y.fiscal_year if y else None,
                   rcm_year_id=y.id if y else None)


@router.get("", response_model=list[RcmYearRead])
def list_years(user: CurrentUser, db: Session = Depends(get_db)) -> list[RcmYearRead]:
    rows = db.query(RcmFiscalYear).filter(RcmFiscalYear.is_deleted == False).order_by(  # noqa: E712
        RcmFiscalYear.fiscal_year.desc()).all()
    return [_read(db, y, user.id) for y in rows]


@router.post("", response_model=RcmYearRead, status_code=status.HTTP_201_CREATED)
def start_year(body: RcmYearCreate, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> RcmYearRead:
    """회계연도 RCM 시작(작성 중) — 지금 라이브 RCM 이 출발점이다. 가장 최근 연도보다 뒤여야 하고,
    가장 최근 연도가 검토 중이면 시작할 수 없다(결재를 끝내거나 회수한 뒤)."""
    latest = rap.latest_year(db)
    if latest is not None:
        if body.fiscal_year <= latest.fiscal_year:
            raise HTTPException(status_code=409, detail=f"{latest.fiscal_year} 회계연도보다 뒤의 연도만 시작할 수 있습니다")
        if approval_flow.view_state(db, rap.hooks(db, latest)).status == "review":
            raise HTTPException(status_code=409, detail=f"{latest.fiscal_year} 회계연도 RCM 이 검토 중입니다 — 결재를 끝낸 뒤 시작하세요")
    y = RcmFiscalYear(fiscal_year=body.fiscal_year)
    db.add(y)
    db.commit()
    return _read(db, y, user.id)


@router.get("/{rid}", response_model=RcmYearRead)
def get_year(rid: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> RcmYearRead:
    return _read(db, _get(db, rid), user.id)


@router.post("/{rid}/transition", response_model=RcmYearRead)
def transition(rid: UUID, req: TransitionRequest, user: User = Depends(require_icfr_staff),
               db: Session = Depends(get_db)) -> RcmYearRead:
    """draft→review(검토 요청) / review→draft(회수·반려) / review→confirmed(마스터 승인 — 스냅샷 저장).
    확정 → 작성 중은 재오픈 요청·승인으로만."""
    y = _get(db, rid)
    h = rap.hooks(db, y)
    reason = (req.reason or "").strip() or None
    cur = approval_flow.view_state(db, h).status
    if cur == "draft" and req.to_status == "review":
        _flow(db, lambda: approval_flow.submit(db, h, user.id, reason))
    elif cur == "review" and req.to_status == "draft":
        _flow(db, lambda: approval_flow.back_to_draft(db, h, user.id, reason))
    elif cur == "review" and req.to_status == "confirmed":
        _flow(db, lambda: approval_flow.approve(db, h, user.id, reason))
    elif cur == "confirmed" and req.to_status == "draft":
        raise HTTPException(status_code=409, detail="확정된 RCM 은 재오픈 요청 후 승인을 받아야 작성 중으로 돌아갑니다")
    else:
        raise HTTPException(status_code=409, detail=f"'{cur}' 에서 '{req.to_status}' 로 바꿀 수 없습니다")
    return _read(db, y, user.id)


@router.post("/{rid}/review", response_model=RcmYearRead)
def review(rid: UUID, req: ReviewRequest, user: User = Depends(require_icfr_staff),
           db: Session = Depends(get_db)) -> RcmYearRead:
    y = _get(db, rid)
    h = rap.hooks(db, y)
    _flow(db, lambda: approval_flow.review(db, h, user.id, req.action, (req.reason or "").strip() or None))
    return _read(db, y, user.id)


@router.post("/{rid}/reopen-requests", response_model=RcmYearRead, status_code=status.HTTP_201_CREATED)
def request_reopen(rid: UUID, body: ReopenCreate, user: User = Depends(require_icfr_staff),
                   db: Session = Depends(get_db)) -> RcmYearRead:
    """확정 RCM 재오픈 요청 — 사유 필수. 가장 최근 연도만(지난 연도는 스냅샷으로 고정)."""
    y = _get(db, rid)
    latest = rap.latest_year(db)
    if latest is None or latest.id != y.id:
        raise HTTPException(status_code=409, detail="가장 최근 회계연도 RCM 만 재오픈할 수 있습니다 — 지난 연도는 확정본으로 고정됩니다")
    h = rap.hooks(db, y)
    _flow(db, lambda: approval_flow.request_reopen(db, h, user.id, body.reason))
    return _read(db, y, user.id)


@router.post("/{rid}/reopen-requests/{request_id}/decide", response_model=RcmYearRead)
def decide_reopen(rid: UUID, request_id: UUID, body: ReopenDecision, user: User = Depends(require_icfr_staff),
                  db: Session = Depends(get_db)) -> RcmYearRead:
    y = _get(db, rid)
    h = rap.hooks(db, y)
    _flow(db, lambda: approval_flow.decide_reopen(db, h, user.id, request_id, body.approve,
                                                  (body.reason or "").strip() or None))
    return _read(db, y, user.id)


@router.post("/{rid}/external-approval", response_model=RcmYearRead)
def external_approval(rid: UUID, purpose: str = Form(...), approver_body: str = Form(...),
                      approved_on: str = Form(...), reference: str | None = Form(default=None),
                      files: list[UploadFile] = File(...), user: User = Depends(require_icfr_staff),
                      db: Session = Depends(get_db)) -> RcmYearRead:
    """마스터관리자 작성분의 확정·마스터 요청 재오픈 — 대표이사·이사회 승인 증빙(필수)."""
    y = _get(db, rid)
    h = rap.hooks(db, y)
    ev = [approval_flow.EvidenceFile(filename=f.filename or "", content_type=f.content_type,
                                     data=f.file.read(approval_flow.MAX_EVIDENCE_BYTES + 1)) for f in files]
    _flow(db, lambda: approval_flow.record_external(db, h, user.id, purpose=purpose, approver_body=approver_body,
                                                    approved_on=approved_on, reference=reference, files=ev))
    return _read(db, y, user.id)


@router.get("/{rid}/snapshots/{version}")
def get_snapshot(rid: UUID, version: int, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    """확정본 전체(프로세스·하위·위험·통제·어서션 연결) — 지난 연도의 RCM 을 그대로 본다."""
    s = db.query(RcmSnapshot).filter(RcmSnapshot.rcm_year_id == _get(db, rid).id, RcmSnapshot.version == version,
                                     RcmSnapshot.is_deleted == False).first()  # noqa: E712
    if s is None:
        raise HTTPException(status_code=404, detail="확정본이 없습니다")
    return s.snapshot


@router.get("/{rid}/governance-events", response_model=list[GovernanceEventRead])
def list_events(rid: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> list[GovernanceEventRead]:
    return av.events(db, ENTITY_RCM_YEAR, _get(db, rid).id)
