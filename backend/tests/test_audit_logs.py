"""감사 로그 (2026-10-06) — 상태 변경 요청이 기록되고, 관리자만 검색·페이지·CSV 로 본다."""
from fastapi.testclient import TestClient

from app.services import audit_log as al
from tests.test_governance import T, template  # noqa: F401


def test_rules() -> None:
    assert al.should_log("POST", "/api/scoping") and al.should_log("DELETE", "/api/users/x")
    assert not al.should_log("GET", "/api/scoping") and al.should_log("GET", "/api/evidence/files/x/download")
    assert not al.should_log("GET", "/api/admin/audit-logs/export") and not al.should_log("POST", "/api/health")
    assert al.module_of("/api/control-links/auto") == "통제↔계정 연결"
    assert al.action_of("POST", "/api/report/documents/{fiscal_year}/{doc_key}/finalize") == "확정"
    assert al.action_of("PUT", "/api/report/documents/{fiscal_year}/{doc_key}") == "수정"
    assert al.action_of("POST", "/api/auth/login") == "로그인"
    assert al.target_of("/api/x/aaaaaaaa-0000-7000-8000-000000000001/y") == "aaaaaaaa-0000-7000-8000-000000000001"


def test_logged_and_viewed_by_manager_only(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "master": ("icfr_manager",)})
    client.put("/api/report/documents/2025/meta", headers=t.h["staff"], json={"content": {"fields": {"company": "x"}}})
    client.put("/api/report/documents/2025/bogus", headers=t.h["staff"], json={"content": {}})   # 404 → 실패 기록
    assert client.get("/api/admin/audit-logs", headers=t.h["staff"]).status_code == 403
    r = client.get("/api/admin/audit-logs", headers=t.h["master"], params={"module": "보고서"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total"] == 2 and d["items"][0]["user_name"] and "보고서" in d["modules"]
    assert {i["success"] for i in d["items"]} == {True, False}
    assert client.get("/api/admin/audit-logs", headers=t.h["master"], params={"result": "fail", "module": "보고서"}).json()["total"] == 1
    assert client.get("/api/admin/audit-logs", headers=t.h["master"], params={"q": "bogus"}).json()["total"] == 1
    p = client.get("/api/admin/audit-logs", headers=t.h["master"], params={"size": 10, "page": 99}).json()
    assert p["items"] == [] and p["page"] == 99
    assert client.get("/api/admin/audit-logs", headers=t.h["master"], params={"size": 7}).status_code == 422
    csv = client.get("/api/admin/audit-logs/export", headers=t.h["master"], params={"module": "보고서"})
    assert csv.status_code == 200 and "일시" in csv.text and csv.text.count("\n") == 3
