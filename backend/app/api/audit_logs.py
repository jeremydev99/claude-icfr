"""감사 로그 조회 API (2026-10-06) — 검색·필터·페이지·CSV 내보내기. 마스터관리자(내부회계관리자)·시스템관리자만.

활성 테넌트의 로그만 보인다. 행은 추가만 되고 수정·삭제 API 는 없다(models/audit_log.py).
"""
import csv
import io
from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import tenant_roles
from app.core.tenant_context import get_active_tenant
from app.models.audit_log import AuditLog
from app.models.role_assignment import ROLE_ICFR_MANAGER
from app.models.user import User

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin"])
PAGE_SIZES = (10, 20, 50, 100)
EXPORT_LIMIT = 20_000


def require_audit_viewer(user: CurrentUser, db: Session = Depends(get_db)) -> User:
    if user.role == "admin" or ROLE_ICFR_MANAGER in tenant_roles(db, user.id):
        return user
    raise HTTPException(status_code=403, detail="감사 로그는 내부회계관리자·시스템관리자만 볼 수 있습니다")


class LogOut(BaseModel):
    id: UUID
    occurred_at: datetime
    user_id: UUID | None
    user_name: str | None
    user_email: str | None
    method: str
    module: str
    action: str
    route: str
    path: str
    target_id: str | None
    status_code: int
    success: bool
    ip: str | None
    user_agent: str | None
    duration_ms: int | None


class PageOut(BaseModel):
    items: list[LogOut]
    total: int
    page: int
    size: int
    modules: list[str]
    actions: list[str]
    users: list[dict]


def _query(db: Session, q: str | None, user_id: UUID | None, module: str | None, action: str | None,
           result: str | None, date_from: date | None, date_to: date | None):
    qs = db.query(AuditLog).filter(AuditLog.tenant_id == get_active_tenant())
    if user_id:
        qs = qs.filter(AuditLog.user_id == user_id)
    if module:
        qs = qs.filter(AuditLog.module == module)
    if action:
        qs = qs.filter(AuditLog.action == action)
    if result == "success":
        qs = qs.filter(AuditLog.success == True)  # noqa: E712
    elif result == "fail":
        qs = qs.filter(AuditLog.success == False)  # noqa: E712
    if date_from:
        qs = qs.filter(AuditLog.occurred_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        qs = qs.filter(AuditLog.occurred_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        qs = qs.filter(or_(func.lower(AuditLog.user_name).like(like), func.lower(AuditLog.user_email).like(like),
                           func.lower(AuditLog.path).like(like), func.lower(AuditLog.module).like(like),
                           func.lower(AuditLog.action).like(like), func.lower(AuditLog.ip).like(like),
                           func.lower(AuditLog.target_id).like(like)))
    return qs


@router.get("", response_model=PageOut)
def list_logs(viewer: User = Depends(require_audit_viewer), db: Session = Depends(get_db),
              q: str | None = None, user_id: UUID | None = None, module: str | None = None,
              action: str | None = None, result: str | None = Query(None, pattern="^(success|fail)$"),
              date_from: date | None = None, date_to: date | None = None,
              page: int = Query(1, ge=1), size: int = Query(20)) -> PageOut:
    if size not in PAGE_SIZES:
        raise HTTPException(status_code=422, detail=f"한 페이지 건수는 {', '.join(map(str, PAGE_SIZES))} 중 하나입니다")
    qs = _query(db, q, user_id, module, action, result, date_from, date_to)
    total = qs.count()
    rows = qs.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).offset((page - 1) * size).limit(size).all()
    base = db.query(AuditLog).filter(AuditLog.tenant_id == get_active_tenant())
    modules = sorted(m for (m,) in base.with_entities(AuditLog.module).distinct().all())
    actions = sorted(a for (a,) in base.with_entities(AuditLog.action).distinct().all())
    users = [{"id": u, "name": n or e or "(알 수 없음)"} for u, n, e in base.with_entities(
        AuditLog.user_id, AuditLog.user_name, AuditLog.user_email).filter(AuditLog.user_id.isnot(None)).distinct().all()]
    seen: dict = {}
    for x in users:
        seen.setdefault(x["id"], x)
    return PageOut(items=[LogOut.model_validate(r, from_attributes=True) for r in rows], total=total, page=page,
                   size=size, modules=modules, actions=actions,
                   users=sorted(seen.values(), key=lambda x: x["name"]))


@router.get("/export")
def export_logs(viewer: User = Depends(require_audit_viewer), db: Session = Depends(get_db),
                q: str | None = None, user_id: UUID | None = None, module: str | None = None,
                action: str | None = None, result: str | None = Query(None, pattern="^(success|fail)$"),
                date_from: date | None = None, date_to: date | None = None) -> StreamingResponse:
    """현재 조건 그대로 CSV(엑셀에서 한글이 깨지지 않게 BOM). 최대 2만 행."""
    rows = _query(db, q, user_id, module, action, result, date_from, date_to).order_by(
        AuditLog.occurred_at.desc()).limit(EXPORT_LIMIT).all()
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(["일시", "사용자", "이메일", "모듈", "동작", "결과", "상태코드", "대상", "경로", "IP", "기기", "처리(ms)"])
    for r in rows:
        w.writerow([r.occurred_at.isoformat(timespec="seconds"), r.user_name or "", r.user_email or "", r.module,
                    r.action, "성공" if r.success else "실패", r.status_code, r.target_id or "", r.path, r.ip or "",
                    r.user_agent or "", r.duration_ms or ""])
    name = f"audit-log-{date.today().isoformat()}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
