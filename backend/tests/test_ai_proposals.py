"""AI 제안·채택 (ADR-0042) ① 규칙형 — 다음 회계연도 일정안."""
from datetime import date

from fastapi.testclient import TestClient

from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.services import ai_schedule
from tests.conftest import TestingSessionLocal
from tests.test_governance import T, template  # noqa: F401


def test_roll_forward_moves_to_business_days() -> None:
    items = [
        {"title": "신정 시작", "start_date": "2026-01-01", "end_date": "2026-01-30"},   # 2027-01-01(금) 신정
        {"title": "주말 끝", "start_date": "2026-03-02", "end_date": "2026-03-28"},    # 2027-03-28(일)
        {"title": "평일", "start_date": "2026-06-10", "end_date": "2026-06-16"},
        {"title": "윤일", "start_date": "2028-02-29", "end_date": "2028-02-29"},
    ]
    out, adj = ai_schedule.roll_forward(items, 2027)
    by = {o["title"]: o for o in out}
    assert by["신정 시작"]["start_date"] == "2027-01-04"
    assert by["주말 끝"]["end_date"] == "2027-03-26"
    assert (by["평일"]["start_date"], by["평일"]["end_date"]) == ("2027-06-10", "2027-06-16")
    assert by["윤일"]["start_date"] == "2029-02-28"
    reasons = {(a["title"], a["which"]): a["reason"] for a in adj}
    assert reasons[("주말 끝", "종료")] == "일요일" and reasons[("신정 시작", "시작")]


def test_propose_adopt_then_submit(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "lead": ("icfr_lead",), "master": ("icfr_manager",)})
    h = t.h
    # 올해 일정안을 표준으로 만들어 두면 그것이 근거가 된다
    assert client.post("/api/schedule/plans/2026/init", headers=h["staff"]).status_code == 200
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        assert ai_schedule.propose_schedule(db, date(2026, 11, 20)) is None      # 아직 계기 아님(12/1 부터)
        prop = ai_schedule.propose_schedule(db, date(2026, 12, 5))
        db.commit()
        assert prop is not None and prop.fiscal_year == 2027 and "2026 회계연도 일정안" in prop.summary
        assert ai_schedule.propose_schedule(db, date(2026, 12, 6)) is None       # 한 연도에 한 번
        pid = str(prop.id)
    finally:
        db.close()
        reset_active_tenant(tok)

    plan = client.get("/api/schedule/plans/2027", headers=h["staff"]).json()
    assert plan["plan"]["status"] == "draft" and plan["ai_proposal"]["status"] == "proposed"
    assert any(i["action"] == "ai_adopt" for i in client.get("/api/governance/inbox", headers=h["staff"]).json())
    # 채택 전에는 상신 불가
    r = client.post("/api/schedule/plans/2027/submit", headers=h["staff"], json={})
    assert r.status_code == 409 and "채택" in r.json()["detail"]
    # 담당자가 한 줄 고친 뒤 채택 → 변경 내역이 남는다
    item = plan["items"][0]
    r = client.patch(f"/api/schedule/plans/2027/items/{item['id']}/dates", headers=h["staff"],
                     json={"start_date": item["start_date"], "end_date": item["start_date"]})
    assert r.status_code == 200, r.text
    a = client.post(f"/api/ai-proposals/{pid}/adopt", headers=h["staff"], json={"note": "검토함"}).json()
    assert a["status"] == "adopted" and a["adopted_by"] == "staff"
    assert a["adopted_changes"] and a["adopted_changes"][0]["change"] == "기간 변경"
    assert client.post(f"/api/ai-proposals/{pid}/adopt", headers=h["staff"], json={}).status_code == 409
    assert client.post("/api/schedule/plans/2027/submit", headers=h["staff"], json={}).status_code == 200


def test_discard_removes_unsubmitted_ai_draft(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "owner": ()})
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        prop = ai_schedule.propose_schedule(db, date(2026, 12, 10))   # 올해 일정안 없음 → 표준 일정 근거
        db.commit()
        assert "표준 일정" in prop.summary
        pid = str(prop.id)
    finally:
        db.close()
        reset_active_tenant(tok)
    assert client.post(f"/api/ai-proposals/{pid}/discard", headers=t.h["owner"], json={"reason": "x"}).status_code == 409
    assert client.post(f"/api/ai-proposals/{pid}/discard", headers=t.h["staff"], json={"reason": ""}).status_code == 409
    d = client.post(f"/api/ai-proposals/{pid}/discard", headers=t.h["staff"], json={"reason": "직접 만들기로"}).json()
    assert d["status"] == "discarded"
    assert client.get("/api/schedule/plans/2027", headers=t.h["staff"]).json()["plan"] is None
