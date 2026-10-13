"""AI 제안 ① 규칙형 — 다음 회계연도 일정안 (ADR-0042 §3).

회계연도 종료 30일 전부터, 다음 연도 일정안이 없으면 초안을 만든다. **LLM 을 쓰지 않는다** — 같은 입력이면 항상 같은
결과가 나와야 감사인에게 설명할 수 있다.

- 근거: 올해 승인본 → (없으면) 올해 일정안 → (없으면) 표준 일정
- 방법: 날짜를 1년 뒤로 옮기고, 주말·공휴일(대체공휴일·음력 명절 포함)에 걸린 시작일은 다음 영업일, 종료일은 직전 영업일로
- 결과: 작성 중 일정안(`created_by = system:ai`) + `ai_proposals` 1건. 담당자가 채택해야 상신할 수 있다.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import holidays

from app.core import governance_log as glog
from app.core.audit_context import SYSTEM_AI, system_actor
from app.models.ai_proposal import (
    AI_ADOPTED,
    AI_DISCARDED,
    AI_PROPOSED,
    KIND_SCHEDULE_PLAN,
    AiProposal,
)
from app.models.schedule import ENTITY_SCHEDULE, PLAN_DRAFT, ScheduleItem, SchedulePlan
from app.services import approval
from app.services import schedule as svc
from app.services.assessment_period import current_fiscal_year

ENGINE = "rule:schedule-roll-forward"
LEAD_DAYS = 30


class AiProposalError(ValueError):
    pass


# ── 날짜 ─────────────────────────────────────────────────
def _plus_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:          # 2월 29일 → 다음 해 2월 28일
        return d.replace(year=d.year + 1, day=28)


def _why_closed(d: date, hol: holidays.HolidayBase) -> str | None:
    if d in hol:
        return hol.get(d)
    if d.weekday() >= 5:
        return "토요일" if d.weekday() == 5 else "일요일"
    return None


def _roll(d: date, hol: holidays.HolidayBase, step: int) -> date:
    while _why_closed(d, hol):
        d += timedelta(days=step)
    return d


def roll_forward(items: list[dict], year: int) -> tuple[list[dict], list[dict]]:
    """항목을 1년 뒤로 옮기고 영업일로 맞춘다 — (옮긴 항목, 조정 내역). 순수 함수(테스트 대상)."""
    hol = holidays.country_holidays("KR", years=[year - 1, year, year + 1, year + 2])
    out, adjusted = [], []
    for it in items:
        s0, e0 = _plus_year(date.fromisoformat(str(it["start_date"]))), _plus_year(date.fromisoformat(str(it["end_date"])))
        s, e = _roll(s0, hol, 1), _roll(e0, hol, -1)
        if e < s:
            e = s
        for label, before, after in (("시작", s0, s), ("종료", e0, e)):
            if before != after:
                adjusted.append({"title": it["title"], "which": label, "from": before.isoformat(),
                                 "to": after.isoformat(), "reason": _why_closed(before, hol)})
        out.append({**{k: it.get(k) for k in ("kind", "template_code", "title", "category", "description", "tasks")},
                    "start_date": s.isoformat(), "end_date": e.isoformat()})
    return out, adjusted


# ── 제안 ─────────────────────────────────────────────────
def _source(db, fy: int, sm: int) -> tuple[list[dict], str]:
    p = svc.get_plan(db, fy)
    if p is not None and p.approved_items:
        return p.approved_items, f"{fy} 회계연도 승인본 v{p.approved_version}"
    if p is not None:
        return [svc.item_dict(i) for i in svc.items_of(db, p)], f"{fy} 회계연도 일정안(작성 중 v{p.version})"
    tpls, _ = svc.templates(db)
    items = []
    for t in tpls:
        s, e = svc.offset_range(fy, sm, t["start_offset"], t["end_offset"])
        items.append({"kind": svc.KIND_STANDARD, "template_code": t["code"], "title": t["name"], "category": t["category"],
                      "description": t.get("description"), "tasks": t.get("tasks") or [],
                      "start_date": s.isoformat(), "end_date": e.isoformat()})
    return items, f"표준 일정({fy} 회계연도 기준)"


def due_year(db, today: date) -> int | None:
    """제안할 회계연도 — 올해 회계연도 종료 30일 전부터 다음 연도. 아직 이르면 None."""
    sm = svc.fiscal_start_month(db)
    cur = current_fiscal_year(today, sm)
    fy_end = svc.offset_range(cur, sm, 12, 12)[1]
    return cur + 1 if today >= fy_end - timedelta(days=LEAD_DAYS) else None


def propose_schedule(db, today: date) -> AiProposal | None:
    """계기가 됐고, 다음 연도 일정안·제안이 없으면 초안을 만든다. 한 연도에 한 번만(폐기돼도 다시 만들지 않는다)."""
    nxt = due_year(db, today)
    if nxt is None or svc.get_plan(db, nxt) is not None:
        return None
    if db.query(AiProposal).filter(AiProposal.kind == KIND_SCHEDULE_PLAN, AiProposal.fiscal_year == nxt,
                                   AiProposal.is_deleted == False).first() is not None:  # noqa: E712
        return None
    sm = svc.fiscal_start_month(db)
    src, label = _source(db, nxt - 1, sm)
    items, adjusted = roll_forward(src, nxt)
    fy_end = svc.offset_range(nxt - 1, sm, 12, 12)[1]
    with system_actor(SYSTEM_AI):
        p = SchedulePlan(fiscal_year=nxt, status=PLAN_DRAFT, approval_line=[], approvals=[])
        db.add(p)
        db.flush()
        for n, it in enumerate(items):
            db.add(ScheduleItem(plan_id=p.id, kind=it.get("kind") or svc.KIND_STANDARD, template_code=it.get("template_code"),
                                title=it["title"], category=it.get("category") or "other",
                                start_date=date.fromisoformat(it["start_date"]), end_date=date.fromisoformat(it["end_date"]),
                                description=it.get("description"), tasks=it.get("tasks") or [], sort_order=n))
        prop = AiProposal(
            kind=KIND_SCHEDULE_PLAN, target_type="schedule_plan", target_id=p.id, fiscal_year=nxt, status=AI_PROPOSED,
            engine=ENGINE,
            trigger=f"{nxt - 1} 회계연도 종료일({fy_end.isoformat()}) {LEAD_DAYS}일 전 — {nxt} 회계연도 일정안이 없음",
            summary=f"{label}을 {nxt} 회계연도로 옮김 · 일정 {len(items)}개 · 주말·공휴일 조정 {len(adjusted)}건",
            basis={"source": label, "adjusted": adjusted}, proposed=items)
        db.add(prop)
        db.flush()
        glog.record(db, p.id, "ai_propose", version=p.version, entity_type=ENTITY_SCHEDULE,
                    target=f"{nxt} 일정안", after={"AI 제안": prop.summary})
    return prop


# ── 채택·폐기 ─────────────────────────────────────────────
def pending_for(db, target_id) -> AiProposal | None:
    return db.query(AiProposal).filter(AiProposal.target_id == target_id, AiProposal.status == AI_PROPOSED,
                                       AiProposal.is_deleted == False).first()  # noqa: E712


def latest_for(db, target_id) -> AiProposal | None:
    return db.query(AiProposal).filter(AiProposal.target_id == target_id, AiProposal.is_deleted == False).order_by(  # noqa: E712
        AiProposal.created_at.desc()).first()


def _changes(proposed: list[dict], current: list[dict]) -> list[dict]:
    """채택 시점에 담당자가 고친 것 — 제목 기준으로 기간 변경·추가·삭제."""
    before = {i["title"]: i for i in proposed}
    after = {i["title"]: i for i in current}
    out = []
    for t, a in after.items():
        b = before.get(t)
        if b is None:
            out.append({"title": t, "change": "추가", "to": [a["start_date"], a["end_date"]]})
        elif (b["start_date"], b["end_date"]) != (a["start_date"], a["end_date"]):
            out.append({"title": t, "change": "기간 변경", "from": [b["start_date"], b["end_date"]],
                        "to": [a["start_date"], a["end_date"]]})
    out += [{"title": t, "change": "삭제"} for t in before if t not in after]
    return out


def _need_staff(db, user_id) -> None:
    if approval.user_tier(db, user_id) < 1:
        raise AiProposalError("AI 제안의 채택·폐기는 내부회계 관리자(일반·책임·마스터)가 합니다")


def adopt(db, prop: AiProposal, user_id, note: str | None) -> None:
    _need_staff(db, user_id)
    if prop.status != AI_PROPOSED:
        raise AiProposalError("이미 처리된 제안입니다")
    p = db.get(SchedulePlan, prop.target_id)
    current = [svc.item_dict(i) for i in svc.items_of(db, p)] if p is not None else []
    prop.status, prop.adopted_by_id, prop.adopted_at = AI_ADOPTED, user_id, datetime.now(UTC)
    prop.adopted_changes, prop.decision_note = _changes(prop.proposed, current), (note or "").strip() or None
    glog.record(db, prop.target_id, "ai_adopt", version=p.version if p else None, entity_type=ENTITY_SCHEDULE,
                target=f"{prop.fiscal_year} 일정안", reason=prop.decision_note,
                after={"채택": "변경 없이" if not prop.adopted_changes else f"{len(prop.adopted_changes)}건 수정 후"})


def discard(db, prop: AiProposal, user_id, reason: str) -> None:
    _need_staff(db, user_id)
    if prop.status != AI_PROPOSED:
        raise AiProposalError("이미 처리된 제안입니다")
    if not (reason or "").strip():
        raise AiProposalError("폐기 사유를 입력하세요")
    prop.status, prop.decision_note = AI_DISCARDED, reason.strip()
    p = db.get(SchedulePlan, prop.target_id)
    # 아직 한 번도 상신하지 않은 AI 초안이면 함께 지운다 — 표준 일정으로 새로 만들 수 있게
    if p is not None and p.status == PLAN_DRAFT and p.requested_by_id is None and p.approved_version is None:
        for i in svc.items_of(db, p):
            i.is_deleted = True
        p.is_deleted = True
    glog.record(db, prop.target_id, "ai_discard", version=None, entity_type=ENTITY_SCHEDULE,
                target=f"{prop.fiscal_year} 일정안", reason=prop.decision_note)
