"""일정관리 API (2026-10-06) — 표준 일정(마스터 편집) · 회계연도 일정안·항목(내부회계 담당자) · 전결라인 결재.

규칙은 services/schedule.py 하나 — 버튼은 화면이 서버의 `can` 을 보고 그린다.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_manager, require_icfr_staff
from app.models.schedule import (
    CATEGORIES,
    ENTITY_SCHEDULE,
    KIND_CUSTOM,
    KIND_STANDARD,
    PLAN_STATUS_LABELS,
    STEP_LABELS,
    ScheduleItem,
)
from app.models.user import User
from app.services import schedule as svc

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {"module": "schedule", "name_kr": "일정관리", "available_in_phase_1": False,
            "features": ["표준 일정(관리자 편집)", "회계연도 일정안(표준·사용자 지정)", "전결라인 결재"]}


# ── 표준 일정 ─────────────────────────────────────────────
class TemplateIn(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=200)
    category: str = "other"
    start_offset: int = Field(ge=1, le=15)
    end_offset: int = Field(ge=1, le=15)
    description: str | None = None
    tasks: list[str] = []


def _run(db: Session, fn):
    try:
        out = fn()
        db.commit()
        return out
    except svc.ScheduleError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from None


@router.get("/templates")
def get_templates(user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    items, builtin = svc.templates(db)
    return {"items": items, "builtin": builtin, "categories": list(CATEGORIES)}


@router.put("/templates")
def put_templates(body: list[TemplateIn], user: User = Depends(require_icfr_manager), db: Session = Depends(get_db)) -> dict:
    """표준 일정 전체 교체 — 마스터관리자. 이미 만든 회계연도 일정안에는 영향이 없다(새로 만들 때 쓰인다)."""
    if not body:
        raise HTTPException(status_code=422, detail="표준 일정이 하나 이상 있어야 합니다")
    for t in body:
        if t.category not in CATEGORIES:
            raise HTTPException(status_code=422, detail=f"분류가 올바르지 않습니다: {t.category}")
    _run(db, lambda: svc.replace_templates(db, [t.model_dump() for t in body]))
    items, builtin = svc.templates(db)
    return {"items": items, "builtin": builtin, "categories": list(CATEGORIES)}


# ── 일정안 ────────────────────────────────────────────────
class ItemIn(BaseModel):
    kind: str = Field(pattern="^(standard|custom)$")
    template_code: str | None = None
    title: str | None = Field(None, max_length=200)
    start_date: date
    end_date: date
    description: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일이 시작일보다 빠릅니다")
        if self.kind == KIND_CUSTOM and not (self.title or "").strip():
            raise ValueError("사용자 지정 일정은 제목이 필요합니다")
        if self.kind == KIND_STANDARD and not self.template_code:
            raise ValueError("표준 일정을 고르세요")
        return self


class Note(BaseModel):
    note: str | None = None


def _name(db: Session, uid) -> str | None:
    if uid is None:
        return None
    u = db.get(User, uid)
    return u.display_name if u else None


def _plan_out(db: Session, fy: int, user: User) -> dict:
    p = svc.get_plan(db, fy)
    c = svc.can(db, p, user.id)
    can = {"edit": c.edit, "submit": c.submit, "approve": c.approve, "return": c.return_, "why": c.why}
    if p is None:
        return {"fiscal_year": fy, "plan": None, "items": [], "can": can, "policy_line": svc.approval_line(db),
                "start_month": svc.fiscal_start_month(db)}
    items = svc.items_of(db, p)
    return {
        "fiscal_year": fy,
        "plan": {"id": p.id, "status": p.status, "status_label": PLAN_STATUS_LABELS.get(p.status, p.status),
                 "version": p.version, "approval_line": [{"step": s, "label": STEP_LABELS.get(s, s)} for s in p.approval_line],
                 "current_step": p.current_step, "approvals": p.approvals, "requested_by": _name(db, p.requested_by_id),
                 "requested_at": p.requested_at, "request_note": p.request_note, "approved_at": p.approved_at,
                 "returned_reason": p.returned_reason},
        "items": [{"id": i.id, "kind": i.kind, "template_code": i.template_code, "title": i.title, "category": i.category,
                   "start_date": i.start_date, "end_date": i.end_date, "description": i.description, "tasks": i.tasks or []}
                  for i in items],
        "can": can, "policy_line": svc.approval_line(db), "start_month": svc.fiscal_start_month(db),
    }


@router.get("/plans/{fiscal_year}")
def get_plan(fiscal_year: int, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    return _plan_out(db, fiscal_year, user)


@router.post("/plans/{fiscal_year}/init")
def init_plan(fiscal_year: int, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    _run(db, lambda: svc.init_plan(db, fiscal_year))
    return _plan_out(db, fiscal_year, user)


def _plan_or_404(db: Session, fy: int):
    p = svc.get_plan(db, fy)
    if p is None:
        raise HTTPException(status_code=404, detail="일정안이 없습니다 — 먼저 표준 일정으로 일정안을 만드세요")
    return p


def _apply_item(db: Session, it: ScheduleItem, body: ItemIn) -> None:
    it.kind, it.start_date, it.end_date, it.description = body.kind, body.start_date, body.end_date, body.description
    if body.kind == KIND_STANDARD:
        tpls, _ = svc.templates(db)
        t = next((x for x in tpls if x["code"] == body.template_code), None)
        if t is None:
            raise svc.ScheduleError("표준 일정을 찾을 수 없습니다")
        it.template_code, it.title, it.category, it.tasks = t["code"], t["name"], t["category"], t.get("tasks") or []
        if body.description is None:
            it.description = t.get("description")
    else:
        it.template_code, it.title = None, (body.title or "").strip()
        it.category = it.category if it.category else "other"


@router.post("/plans/{fiscal_year}/items")
def add_item(fiscal_year: int, body: ItemIn, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    p = _plan_or_404(db, fiscal_year)

    def go():
        svc.ensure_editable(db, p)
        it = ScheduleItem(plan_id=p.id, kind=body.kind, title="", category="other", start_date=body.start_date,
                          end_date=body.end_date, tasks=[], sort_order=len(svc.items_of(db, p)))
        _apply_item(db, it, body)
        db.add(it)
        glog.record(db, p.id, "schedule_item_add", version=p.version, entity_type=ENTITY_SCHEDULE, target=it.title,
                    after={"기간": f"{it.start_date} ~ {it.end_date}", "구분": "표준" if it.kind == KIND_STANDARD else "사용자 지정"})
    _run(db, go)
    return _plan_out(db, fiscal_year, user)


def _item_or_404(db: Session, p, iid: UUID) -> ScheduleItem:
    it = db.query(ScheduleItem).filter(ScheduleItem.id == iid, ScheduleItem.plan_id == p.id,
                                       ScheduleItem.is_deleted == False).first()  # noqa: E712
    if it is None:
        raise HTTPException(status_code=404, detail="일정 항목을 찾을 수 없습니다")
    return it


@router.put("/plans/{fiscal_year}/items/{iid}")
def update_item(fiscal_year: int, iid: UUID, body: ItemIn, user: User = Depends(require_icfr_staff),
                db: Session = Depends(get_db)) -> dict:
    p = _plan_or_404(db, fiscal_year)
    it = _item_or_404(db, p, iid)

    def go():
        svc.ensure_editable(db, p)
        before = {"제목": it.title, "기간": f"{it.start_date} ~ {it.end_date}"}
        _apply_item(db, it, body)
        glog.record(db, p.id, "schedule_item_update", version=p.version, entity_type=ENTITY_SCHEDULE, target=it.title,
                    before=before, after={"제목": it.title, "기간": f"{it.start_date} ~ {it.end_date}"})
    _run(db, go)
    return _plan_out(db, fiscal_year, user)


@router.delete("/plans/{fiscal_year}/items/{iid}")
def delete_item(fiscal_year: int, iid: UUID, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    p = _plan_or_404(db, fiscal_year)
    it = _item_or_404(db, p, iid)

    def go():
        svc.ensure_editable(db, p)
        it.is_deleted = True
        glog.record(db, p.id, "schedule_item_delete", version=p.version, entity_type=ENTITY_SCHEDULE, target=it.title)
    _run(db, go)
    return _plan_out(db, fiscal_year, user)


@router.post("/plans/{fiscal_year}/submit")
def submit(fiscal_year: int, body: Note, user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> dict:
    p = _plan_or_404(db, fiscal_year)
    _run(db, lambda: svc.submit(db, p, user.id, body.note))
    return _plan_out(db, fiscal_year, user)


@router.post("/plans/{fiscal_year}/approve")
def approve(fiscal_year: int, body: Note, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    p = _plan_or_404(db, fiscal_year)
    _run(db, lambda: svc.approve(db, p, user, body.note))
    return _plan_out(db, fiscal_year, user)


@router.post("/plans/{fiscal_year}/return")
def return_(fiscal_year: int, body: Note, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    p = _plan_or_404(db, fiscal_year)
    _run(db, lambda: svc.return_(db, p, user, body.note or ""))
    return _plan_out(db, fiscal_year, user)

