"""일정관리 서비스 — 표준 일정·일정안·결재선 판정 (models/schedule.py). API 와 화면(`can`)이 같은 규칙을 본다."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.models.role_assignment import ROLE_CEO, TenantPolicy
from app.models.schedule import (
    APPROVAL_LINES,
    BUILTIN_TEMPLATES,
    DEFAULT_APPROVAL_LINE,
    ENTITY_SCHEDULE,
    KIND_STANDARD,
    PLAN_APPROVED,
    PLAN_DRAFT,
    PLAN_REVIEW,
    POLICY_SCHEDULE_APPROVAL_LINE,
    STEP_LABELS,
    ScheduleItem,
    SchedulePlan,
    ScheduleTemplate,
)
from app.models.user import User
from app.services import approval


class ScheduleError(ValueError):
    """규칙 위반 — API 409."""


# ── 표준 일정 ─────────────────────────────────────────────
def templates(db: Session) -> tuple[list[dict], bool]:
    """(표준 일정, 내장값 여부). 회사가 저장한 것이 없으면 내장 표준 8개."""
    rows = db.query(ScheduleTemplate).filter(ScheduleTemplate.is_deleted == False).order_by(  # noqa: E712
        ScheduleTemplate.sort_order).all()
    if not rows:
        return [dict(t, sort_order=i) for i, t in enumerate(BUILTIN_TEMPLATES)], True
    return [{"code": r.code, "name": r.name, "category": r.category, "start_offset": r.start_offset,
             "end_offset": r.end_offset, "description": r.description, "tasks": r.tasks or [],
             "sort_order": r.sort_order} for r in rows], False


def replace_templates(db: Session, items: list[dict]) -> None:
    codes = [i["code"] for i in items]
    if len(set(codes)) != len(codes):
        raise ScheduleError("표준 일정 코드가 겹칩니다")
    for i in items:
        if not (1 <= i["start_offset"] <= i["end_offset"] <= 15):
            raise ScheduleError(f"'{i['name']}' 의 기간이 올바르지 않습니다(1~15월, 시작 ≤ 종료)")
    for r in db.query(ScheduleTemplate).filter(ScheduleTemplate.is_deleted == False).all():  # noqa: E712
        r.is_deleted = True
    for n, i in enumerate(items):
        db.add(ScheduleTemplate(code=i["code"], name=i["name"], category=i.get("category") or "other",
                                start_offset=i["start_offset"], end_offset=i["end_offset"],
                                description=i.get("description"), tasks=i.get("tasks") or [], sort_order=n))


# ── 날짜 ─────────────────────────────────────────────────
def offset_month(fy: int, start_month: int, offset: int) -> tuple[int, int]:
    idx = start_month - 1 + (offset - 1)
    return fy + idx // 12, idx % 12 + 1


def offset_range(fy: int, start_month: int, s: int, e: int) -> tuple[date, date]:
    y1, m1 = offset_month(fy, start_month, s)
    y2, m2 = offset_month(fy, start_month, e)
    return date(y1, m1, 1), date(y2, m2, calendar.monthrange(y2, m2)[1])


def fiscal_start_month(db: Session) -> int:
    p = db.query(TenantPolicy).filter(TenantPolicy.policy_key == "fiscal_year_start_month",
                                      TenantPolicy.is_deleted == False).first()  # noqa: E712
    try:
        v = int(p.policy_value) if p else 1
    except ValueError:
        v = 1
    return v if 1 <= v <= 12 else 1


def approval_line(db: Session) -> list[str]:
    p = db.query(TenantPolicy).filter(TenantPolicy.policy_key == POLICY_SCHEDULE_APPROVAL_LINE,
                                      TenantPolicy.is_deleted == False).first()  # noqa: E712
    v = p.policy_value if p and p.policy_value in APPROVAL_LINES else DEFAULT_APPROVAL_LINE
    return [] if v == "none" else v.split(",")


# ── 일정안 ────────────────────────────────────────────────
def get_plan(db: Session, fy: int) -> SchedulePlan | None:
    return db.query(SchedulePlan).filter(SchedulePlan.fiscal_year == fy,
                                         SchedulePlan.is_deleted == False).first()  # noqa: E712


def items_of(db: Session, p: SchedulePlan) -> list[ScheduleItem]:
    return db.query(ScheduleItem).filter(ScheduleItem.plan_id == p.id, ScheduleItem.is_deleted == False).order_by(  # noqa: E712
        ScheduleItem.start_date, ScheduleItem.sort_order).all()


def init_plan(db: Session, fy: int) -> SchedulePlan:
    """표준 일정으로 일정안 초안을 만든다."""
    if get_plan(db, fy) is not None:
        raise ScheduleError("이 회계연도에는 이미 일정안이 있습니다")
    sm = fiscal_start_month(db)
    p = SchedulePlan(fiscal_year=fy, status=PLAN_DRAFT, approval_line=[], approvals=[])
    db.add(p)
    db.flush()
    tpls, _ = templates(db)
    for n, t in enumerate(tpls):
        s, e = offset_range(fy, sm, t["start_offset"], t["end_offset"])
        db.add(ScheduleItem(plan_id=p.id, kind=KIND_STANDARD, template_code=t["code"], title=t["name"],
                            category=t["category"], start_date=s, end_date=e, description=t.get("description"),
                            tasks=t.get("tasks") or [], sort_order=n))
    glog.record(db, p.id, "schedule_init", version=p.version, entity_type=ENTITY_SCHEDULE,
                target=f"{fy} 일정안", after={"표준 일정": len(tpls)})
    return p


def ensure_editable(db: Session, p: SchedulePlan) -> None:
    """결재 중이면 막고, 승인된 일정안을 고치면 새 판(작성 중)으로 돌린다 — 변경도 결재를 받는다."""
    if p.status == PLAN_REVIEW:
        raise ScheduleError("결재 중인 일정안은 고칠 수 없습니다 — 반려되거나 승인된 뒤 고치세요")
    if p.status == PLAN_APPROVED:
        p.status, p.version = PLAN_DRAFT, p.version + 1
        p.approvals, p.current_step, p.approval_line = [], 0, []
        glog.record(db, p.id, "schedule_revise", version=p.version, entity_type=ENTITY_SCHEDULE,
                    target=f"{p.fiscal_year} 일정안", reason="승인된 일정안 변경 — 다시 결재 필요")


@dataclass
class SCan:
    edit: bool = False
    submit: bool = False
    approve: bool = False
    return_: bool = False
    why: dict[str, str] = field(default_factory=dict)


def _step_ok(db: Session, step: str, user_id: UUID) -> bool:
    if step == "ceo":
        from app.core.permissions import tenant_roles
        return ROLE_CEO in tenant_roles(db, user_id)
    t = approval.user_tier(db, user_id)
    return (step == "lead" and t == 2) or (step == "master" and t == 3)


def can(db: Session, p: SchedulePlan | None, user_id: UUID) -> SCan:
    c = SCan()
    tier = approval.user_tier(db, user_id)
    c.edit = tier >= 1 and (p is None or p.status != PLAN_REVIEW)
    if p is None:
        return c
    if p.status == PLAN_DRAFT:
        c.submit = tier >= 1
        if not c.submit:
            c.why["submit"] = "결재 요청은 내부회계 담당자가 합니다"
    if p.status == PLAN_REVIEW and p.current_step < len(p.approval_line):
        step = p.approval_line[p.current_step]
        prior = {a.get("user_id") for a in p.approvals}
        own = p.requested_by_id == user_id or str(user_id) in prior
        ok = _step_ok(db, step, user_id)
        c.approve = c.return_ = ok and not own
        if not ok:
            c.why["approve"] = f"지금 단계는 {STEP_LABELS.get(step, step)} 승인입니다"
        elif own:
            c.why["approve"] = "요청자·앞 단계 승인자는 승인할 수 없습니다 — 자기 승인 금지"
    return c


def submit(db: Session, p: SchedulePlan, user_id: UUID, note: str | None) -> None:
    if not can(db, p, user_id).submit:
        raise ScheduleError("지금은 결재를 요청할 수 없습니다")
    if not items_of(db, p):
        raise ScheduleError("일정 항목이 없습니다")
    line = approval_line(db)
    p.requested_by_id, p.requested_at, p.request_note = user_id, datetime.now(UTC), (note or "").strip() or None
    p.approval_line, p.current_step, p.approvals, p.returned_reason = line, 0, [], None
    if not line:   # 정책상 결재 없음 — 요청과 동시에 승인
        p.status, p.approved_at = PLAN_APPROVED, datetime.now(UTC)
    else:
        p.status = PLAN_REVIEW
    glog.record(db, p.id, "schedule_submit", version=p.version, entity_type=ENTITY_SCHEDULE,
                target=f"{p.fiscal_year} 일정안", reason=p.request_note,
                after={"결재선": " → ".join(STEP_LABELS[s] for s in line) or "결재 없음"})


def approve(db: Session, p: SchedulePlan, user: User, note: str | None) -> None:
    c = can(db, p, user.id)
    if not c.approve:
        raise ScheduleError(c.why.get("approve", "승인할 수 없습니다"))
    step = p.approval_line[p.current_step]
    p.approvals = [*p.approvals, {"step": step, "user_id": str(user.id), "name": user.display_name,
                                  "at": datetime.now(UTC).isoformat(), "note": (note or "").strip() or None}]
    p.current_step += 1
    if p.current_step >= len(p.approval_line):
        p.status, p.approved_at = PLAN_APPROVED, datetime.now(UTC)
    glog.record(db, p.id, "schedule_approve", version=p.version, entity_type=ENTITY_SCHEDULE,
                target=f"{p.fiscal_year} 일정안 · {STEP_LABELS.get(step, step)}", reason=(note or "").strip() or None)


def return_(db: Session, p: SchedulePlan, user: User, reason: str) -> None:
    if not can(db, p, user.id).return_:
        raise ScheduleError("지금은 반려할 수 없습니다")
    if not reason.strip():
        raise ScheduleError("반려 사유가 필요합니다")
    p.status, p.returned_reason, p.current_step, p.approvals = PLAN_DRAFT, reason.strip(), 0, []
    glog.record(db, p.id, "schedule_return", version=p.version, entity_type=ENTITY_SCHEDULE,
                target=f"{p.fiscal_year} 일정안", reason=reason.strip())
