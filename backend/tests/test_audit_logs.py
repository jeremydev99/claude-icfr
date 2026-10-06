"""감사 로그 (2026-10-06) — 상태 변경 요청이 기록되고, 관리자만 검색·페이지·CSV 로 본다."""
from fastapi.testclient import TestClient

from app.services import audit_log as al
from tests.test_control_changes import env  # noqa: F401
from tests.test_governance import T, template  # noqa: F401


def test_rules() -> None:
    assert al.should_log("POST", "/api/scoping") and al.should_log("DELETE", "/api/users/x")
    assert not al.should_log("GET", "/api/scoping") and al.should_log("GET", "/api/evidence/files/x/download")
    assert not al.should_log("GET", "/api/admin/audit-logs/export") and not al.should_log("POST", "/api/health")
    assert al.module_of("/api/control-links/auto") == "통제↔계정 연결"
    assert al.action_of("POST", "/api/report/documents/{fiscal_year}/{doc_key}/finalize") == "확정"
    assert al.action_of("PUT", "/api/report/documents/{fiscal_year}/{doc_key}") == "수정"
    assert al.module_of("/api/rcm-changes/bulk") == "RCM 변경 결재"
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


def test_every_write_route_has_a_name() -> None:
    """상태를 바꾸는 API 는 모두 경로 표에 동작 이름이 있어야 한다 — 새 API 를 만들면 audit_routes 에 한 줄."""
    from app.main import app
    from app.services import audit_routes, audit_target
    missing = [f"{m} {r.path}" for r in app.routes for m in (getattr(r, "methods", None) or ())
               if m in ("POST", "PUT", "PATCH", "DELETE") and r.path.startswith("/api/")
               and audit_routes.lookup(m, r.path) is None]
    assert missing == []
    kinds = {k for (_m, _a, k, _p) in audit_routes.ROUTES.values() if k}
    assert kinds <= set(audit_target.RESOLVERS)


def test_control_change_steps_are_named_with_control(client: TestClient, env) -> None:  # noqa: F811
    """통제 변경 결재 각 단계가 '통제 CC-C1 원래 통제명' 과 함께 남는다(마스터 "모든 단계가 다 나와야")."""
    t, cid = env
    ch = client.put(f"/api/rcm-changes/control/{cid}", headers=t.h["owner"], json={"changes": {"name": "새 통제명"}}).json()["id"]
    client.post(f"/api/rcm-changes/{ch}/submit", headers=t.h["owner"])
    client.post(f"/api/rcm-changes/{ch}/dept-approve", headers=t.h["head"], json={})
    bid = client.post("/api/rcm-changes/batches", headers=t.h["staff"], json={"change_ids": [ch]}).json()["id"]
    client.post(f"/api/rcm-changes/batches/{bid}/decide", headers=t.h["master"],
                json={"decisions": [{"id": ch, "approve": True}]})
    items = client.get("/api/admin/audit-logs", headers=t.h["master"], params={"module": "RCM 변경 결재"}).json()["items"]
    got = [(i["action"], i["target_label"]) for i in reversed(items)]
    assert got == [("통제 변경 임시저장", "통제 CC-C1 원래 통제명"), ("통제 변경 상신", "통제 CC-C1 원래 통제명"),
                   ("조직장 승인", "통제 CC-C1 원래 통제명"), ("내부회계 일괄 상신", "일괄 상신 1건"),
                   ("내부회계관리자 결재", "일괄 상신 1건")]
    # 이름으로 찾기
    assert client.get("/api/admin/audit-logs", headers=t.h["master"], params={"q": "cc-c1"}).json()["total"] == 3


def test_create_and_edit_name_target(client: TestClient) -> None:
    t = T(client, {"master": ("icfr_manager",)})
    fid = client.post("/api/euc/files", headers=t.h["master"], json={"name": "매출 집계표"}).json()["id"]
    client.patch(f"/api/euc/files/{fid}", headers=t.h["master"], json={"description": "월별"})
    items = client.get("/api/admin/audit-logs", headers=t.h["master"], params={"module": "EUC"}).json()["items"]
    assert [(i["action"], i["target_label"], i["target_id"]) for i in reversed(items)] == [
        ("EUC 등록", "EUC 매출 집계표", fid), ("EUC 수정 저장", "EUC 매출 집계표", fid)]
