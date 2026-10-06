"""
Report 모듈 API.

- `/info` — 모듈 정보(초기 placeholder 유지).
- `/documents/{fiscal_year}` — 이사회 보고 패키지 문서(2026-10-06). **사람이 고친 부분만 저장**하고 기본 문구는
  화면 템플릿이 데이터로 만든다(`models/report_document.py`). 작성·수정은 내부회계 관리자(1~3단계),
  확정·재오픈은 마스터관리자. 확정된 문서는 수정할 수 없다.
"""
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_manager, require_icfr_staff
from app.models.report_document import (
    DOC_DRAFT,
    DOC_FINAL,
    DOC_KEYS,
    ENTITY_REPORT_DOCUMENT,
    ReportDocument,
)
from app.models.user import User

router = APIRouter(prefix="/api/report", tags=["report"])
MAX_CONTENT_BYTES = 200_000   # 문서 하나의 고친 내용 상한 — 표·긴 문단을 넉넉히, 실수로 큰 덩어리를 넣는 것은 막는다


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """Report 모듈 정보."""
    return {
        "module": "report",
        "name_kr": "Report",
        "features": ["이사회 보고 패키지(운영실태보고서·감사위원회 평가보고서·보고 자료·의사록(안))",
                     "고친 문단만 저장 · 기본 문구로 되돌리기", "확정·재오픈"],
        "available_in_phase_1": False,   # 모듈 정보 공통 계약(test_modules) — /api/system/modules 집계와 맞춘다
    }


class DocOut(BaseModel):
    doc_key: str
    content: dict
    status: str
    version: int
    updated_at: datetime | None
    updated_by: str | None
    finalized_at: datetime | None
    finalized_by: str | None


class DocSave(BaseModel):
    content: dict = Field(default_factory=dict)


class Reason(BaseModel):
    reason: str | None = None


def _name(db: Session, uid) -> str | None:
    if uid is None:
        return None
    u = db.get(User, uid)
    return u.display_name if u else None


def _actor_name(db: Session, actor: str | None) -> str | None:
    """감사 컬럼 행위자(`user:<uuid>` 등) → 사람 이름. 시스템 행위자는 그대로."""
    if not actor:
        return None
    if actor.startswith("user:"):
        try:
            return _name(db, UUID(actor[5:]))
        except ValueError:
            return actor
    return actor


def _out(db: Session, d: ReportDocument) -> DocOut:
    return DocOut(doc_key=d.doc_key, content=d.content or {}, status=d.status, version=d.version,
                  updated_at=d.updated_at, updated_by=_actor_name(db, d.updated_by), finalized_at=d.finalized_at,
                  finalized_by=_name(db, d.finalized_by_id))


def _get(db: Session, fy: int, key: str) -> ReportDocument | None:
    if key not in DOC_KEYS:
        raise HTTPException(status_code=404, detail="알 수 없는 문서입니다")
    return db.query(ReportDocument).filter(ReportDocument.fiscal_year == fy, ReportDocument.doc_key == key,
                                           ReportDocument.is_deleted == False).first()  # noqa: E712


class YearOut(BaseModel):
    fiscal_year: int
    documents: int     # 작성(저장)된 문서 수 — 기본 정보 제외
    final: int         # 확정된 문서 수
    updated_at: datetime | None


@router.get("/years", response_model=list[YearOut])
def list_years(user: CurrentUser, db: Session = Depends(get_db)) -> list[YearOut]:
    """평가 대상 연도(회계연도)별 보고 패키지 현황 — 최신 연도부터."""
    by: dict[int, YearOut] = {}
    for d in db.query(ReportDocument).filter(ReportDocument.is_deleted == False).all():  # noqa: E712
        y = by.setdefault(d.fiscal_year, YearOut(fiscal_year=d.fiscal_year, documents=0, final=0, updated_at=None))
        if d.doc_key != "meta":
            y.documents += 1
            y.final += d.status == DOC_FINAL
        if d.updated_at and (y.updated_at is None or d.updated_at > y.updated_at):
            y.updated_at = d.updated_at
    return sorted(by.values(), key=lambda y: -y.fiscal_year)


@router.get("/documents/{fiscal_year}", response_model=list[DocOut])
def list_documents(fiscal_year: int, user: CurrentUser, db: Session = Depends(get_db)) -> list[DocOut]:
    rows = db.query(ReportDocument).filter(ReportDocument.fiscal_year == fiscal_year,
                                           ReportDocument.is_deleted == False).all()  # noqa: E712
    return [_out(db, d) for d in rows]


@router.put("/documents/{fiscal_year}/{doc_key}", response_model=DocOut)
def save_document(fiscal_year: int, doc_key: str, body: DocSave, user: User = Depends(require_icfr_staff),
                  db: Session = Depends(get_db)) -> DocOut:
    """고친 내용 저장(전체 교체). 빈 `content` 면 전부 기본 문구로 돌아간다."""
    if len(json.dumps(body.content, ensure_ascii=False).encode()) > MAX_CONTENT_BYTES:
        raise HTTPException(status_code=413, detail="문서 내용이 너무 큽니다")
    d = _get(db, fiscal_year, doc_key)
    if d is not None and d.status == DOC_FINAL:
        raise HTTPException(status_code=409, detail="확정된 문서입니다 — 마스터관리자가 재오픈한 뒤 수정하세요")
    if d is None:
        d = ReportDocument(fiscal_year=fiscal_year, doc_key=doc_key, content=body.content, status=DOC_DRAFT)
        db.add(d)
    else:
        d.content = body.content
    db.commit()
    db.refresh(d)
    return _out(db, d)


@router.post("/documents/{fiscal_year}/{doc_key}/finalize", response_model=DocOut)
def finalize(fiscal_year: int, doc_key: str, body: Reason, user: User = Depends(require_icfr_manager),
             db: Session = Depends(get_db)) -> DocOut:
    d = _get(db, fiscal_year, doc_key)
    if d is None:
        d = ReportDocument(fiscal_year=fiscal_year, doc_key=doc_key, content={}, status=DOC_DRAFT)
        db.add(d)
        db.flush()
    if d.status == DOC_FINAL:
        raise HTTPException(status_code=409, detail="이미 확정된 문서입니다")
    d.status, d.finalized_at, d.finalized_by_id = DOC_FINAL, datetime.now(UTC), user.id
    glog.record(db, d.id, "report_finalize", version=d.version, entity_type=ENTITY_REPORT_DOCUMENT,
                target=f"{fiscal_year} {doc_key}", reason=(body.reason or "").strip() or None)
    db.commit()
    db.refresh(d)
    return _out(db, d)


@router.post("/documents/{fiscal_year}/{doc_key}/reopen", response_model=DocOut)
def reopen(fiscal_year: int, doc_key: str, body: Reason, user: User = Depends(require_icfr_manager),
           db: Session = Depends(get_db)) -> DocOut:
    d = _get(db, fiscal_year, doc_key)
    if d is None or d.status != DOC_FINAL:
        raise HTTPException(status_code=409, detail="확정된 문서가 아닙니다")
    if not (body.reason or "").strip():
        raise HTTPException(status_code=422, detail="재오픈 사유가 필요합니다")
    d.status, d.version = DOC_DRAFT, d.version + 1
    glog.record(db, d.id, "report_reopen", version=d.version, entity_type=ENTITY_REPORT_DOCUMENT,
                target=f"{fiscal_year} {doc_key}", reason=body.reason.strip())
    db.commit()
    db.refresh(d)
    return _out(db, d)
