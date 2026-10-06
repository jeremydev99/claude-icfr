"""일정관리 (2026-10-06) — 표준 일정 편집(마스터), 일정안 만들기·항목 편집(담당자), 전결라인 결재."""
from fastapi.testclient import TestClient

from tests.test_governance import T, template  # noqa: F401


def _t(client):
    return T(client, {"staff": ("icfr_staff",), "lead": ("icfr_lead",), "master": ("icfr_manager",)})


def test_templates_builtin_and_master_edit(client: TestClient) -> None:
    t = _t(client)
    d = client.get("/api/schedule/templates", headers=t.h["staff"]).json()
    assert d["builtin"] is True and len(d["items"]) == 8
    new = [{"code": "plan", "name": "연간 계획", "category": "planning", "start_offset": 1, "end_offset": 1,
            "tasks": ["계획 수립"]}]
    assert client.put("/api/schedule/templates", headers=t.h["staff"], json=new).status_code == 403
    r = client.put("/api/schedule/templates", headers=t.h["master"], json=new)
    assert r.status_code == 200 and r.json()["builtin"] is False and r.json()["items"][0]["name"] == "연간 계획"
    bad = [{**new[0], "start_offset": 5, "end_offset": 2}]
    assert client.put("/api/schedule/templates", headers=t.h["master"], json=bad).status_code == 409


def test_plan_items_and_two_step_approval(client: TestClient) -> None:
    t = _t(client)
    base = "/api/schedule/plans/2026"
    assert client.get(base, headers=t.h["staff"]).json()["plan"] is None
    d = client.post(f"{base}/init", headers=t.h["staff"]).json()
    assert d["plan"]["status"] == "draft" and len(d["items"]) == 8
    first = next(i for i in d["items"] if i["template_code"] == "scoping")
    assert first["kind"] == "standard" and first["start_date"] == "2026-01-01" and first["end_date"] == "2026-02-28"
    # 사용자 지정 추가 · 표준 항목 날짜 수정
    custom = {"kind": "custom", "title": "감사인 킥오프", "start_date": "2026-02-10", "end_date": "2026-02-10"}
    d = client.post(f"{base}/items", headers=t.h["staff"], json=custom).json()
    assert any(i["title"] == "감사인 킥오프" for i in d["items"])
    assert client.post(f"{base}/items", headers=t.h["staff"], json={**custom, "title": ""}).status_code == 422
    upd = {"kind": "standard", "template_code": "scoping", "start_date": "2026-01-05", "end_date": "2026-02-20"}
    assert client.put(f"{base}/items/{first['id']}", headers=t.h["staff"], json=upd).status_code == 200
    # 결재 요청 → 책임 1차 → 마스터 2차
    d = client.post(f"{base}/submit", headers=t.h["staff"], json={"note": "2026 일정안"}).json()
    assert d["plan"]["status"] == "in_review" and [s["step"] for s in d["plan"]["approval_line"]] == ["lead", "master"]
    assert client.put(f"{base}/items/{first['id']}", headers=t.h["staff"], json=upd).status_code == 409
    assert client.post(f"{base}/approve", headers=t.h["master"], json={}).status_code == 409   # 지금은 책임 단계
    assert client.post(f"{base}/approve", headers=t.h["lead"], json={}).json()["plan"]["current_step"] == 1
    d = client.post(f"{base}/approve", headers=t.h["master"], json={"note": "승인"}).json()
    assert d["plan"]["status"] == "approved" and len(d["plan"]["approvals"]) == 2
    # 승인된 일정안을 고치면 새 판(작성 중)
    d = client.delete(f"{base}/items/{first['id']}", headers=t.h["staff"]).json()
    assert d["plan"]["status"] == "draft" and d["plan"]["version"] == 2


def test_requester_cannot_approve_and_policy_line(client: TestClient) -> None:
    t = _t(client)
    base = "/api/schedule/plans/2027"
    client.post(f"{base}/init", headers=t.h["lead"])
    client.post(f"{base}/submit", headers=t.h["lead"], json={})
    d = client.get(base, headers=t.h["lead"]).json()
    assert d["can"]["approve"] is False and "자기 승인" in d["can"]["why"]["approve"]
    assert client.post(f"{base}/return", headers=t.h["master"], json={"note": "x"}).status_code == 409   # 지금은 책임 단계
    # 결재선 정책: 마스터만
    pol = "/api/org/policies"
    assert client.put(pol, headers=t.h["master"], json={"policy_key": "schedule_approval_line", "policy_value": "bad"}).status_code == 422
    client.put(pol, headers=t.h["master"], json={"policy_key": "schedule_approval_line", "policy_value": "master"})
    client.post("/api/schedule/plans/2028/init", headers=t.h["staff"])
    d = client.post("/api/schedule/plans/2028/submit", headers=t.h["staff"], json={}).json()
    assert [s["step"] for s in d["plan"]["approval_line"]] == ["master"]
    r = client.post("/api/schedule/plans/2028/return", headers=t.h["master"], json={"note": "기간 조정"})
    assert r.json()["plan"]["status"] == "draft" and r.json()["plan"]["returned_reason"] == "기간 조정"
