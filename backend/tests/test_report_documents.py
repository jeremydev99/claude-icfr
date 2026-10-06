"""보고서 문서 저장·확정·재오픈 (2026-10-06)."""
from fastapi.testclient import TestClient

from tests.test_governance import T, template  # noqa: F401


def test_save_finalize_reopen(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "master": ("icfr_manager",)})
    base = "/api/report/documents/2025"
    assert client.get(base, headers=t.h["staff"]).json() == []
    r = client.put(f"{base}/ops_report", headers=t.h["staff"], json={"content": {"sections": {"opinion": "고친 문단"}}})
    assert r.status_code == 200 and r.json()["content"]["sections"]["opinion"] == "고친 문단"
    assert r.json()["updated_by"]
    assert client.put(f"{base}/unknown", headers=t.h["staff"], json={"content": {}}).status_code == 404
    # 확정은 마스터만, 확정되면 수정 불가
    assert client.post(f"{base}/ops_report/finalize", headers=t.h["staff"], json={}).status_code == 403
    assert client.post(f"{base}/ops_report/finalize", headers=t.h["master"], json={}).json()["status"] == "final"
    assert client.put(f"{base}/ops_report", headers=t.h["staff"], json={"content": {}}).status_code == 409
    assert client.post(f"{base}/ops_report/reopen", headers=t.h["master"], json={}).status_code == 422
    r = client.post(f"{base}/ops_report/reopen", headers=t.h["master"], json={"reason": "이사회 지적 반영"})
    assert r.json()["status"] == "draft" and r.json()["version"] == 2
    # 다른 연도는 따로, 연도 목록에 현황
    assert client.get("/api/report/documents/2024", headers=t.h["staff"]).json() == []
    client.put("/api/report/documents/2026/meta", headers=t.h["staff"], json={"content": {"fields": {"company": "x"}}})
    years = client.get("/api/report/years", headers=t.h["staff"]).json()
    assert [y["fiscal_year"] for y in years] == [2026, 2025]
    assert years[1]["documents"] == 1 and years[0]["documents"] == 0


def test_content_size_limit(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",)})
    big = {"sections": {"x": "가" * 80_000}}
    assert client.put("/api/report/documents/2025/meta", headers=t.h["staff"], json={"content": big}).status_code == 413
