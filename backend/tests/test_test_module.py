"""Test 모듈 통합 테스트 — Phase 1 작업3 (RAWC + 워크플로 + 이력)."""
import pytest
from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _create_control(client: TestClient, suffix: str) -> str:
    """Process → SubProcess → Risk → Control 체인 생성 후 control_id 반환."""
    h = _headers(client)
    p = client.post("/api/rcm/processes", json={"code": f"TP-{suffix}", "name": "테스트"}, headers=h)
    sp = client.post("/api/rcm/sub-processes", json={"code": f"TP-{suffix}-010", "name": "SP", "process_id": p.json()["id"]}, headers=h)
    r = client.post("/api/rcm/risks", json={"code": f"TP-{suffix}-010-10", "description": "위험", "assessment_level": "LR", "sub_process_id": sp.json()["id"]}, headers=h)
    c = client.post("/api/rcm/controls", json={"code": f"TP-{suffix}-010-10-10", "name": "통제", "risk_id": r.json()["id"], "frequency": "M"}, headers=h)
    return c.json()["id"]


# ── RAWC CRUD ─────────────────────────────────────────────

def test_rawc_crud(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "RAWC1")

    resp = client.post("/api/test/rawc", json={
        "control_id": control_id,
        "fiscal_year": 2025,
        "frequency_score": 3,
        "overall_assessment": "Higher",
    }, headers=h)
    assert resp.status_code == 201
    rawc_id = resp.json()["id"]
    assert resp.json()["overall_assessment"] == "Higher"

    resp = client.get(f"/api/test/rawc/{rawc_id}", headers=h)
    assert resp.status_code == 200

    resp = client.patch(f"/api/test/rawc/{rawc_id}", json={"overall_assessment": "Not_Higher"}, headers=h)
    assert resp.json()["overall_assessment"] == "Not_Higher"

    resp = client.get("/api/test/rawc/by-control/" + control_id, headers=h, params={"fiscal_year": 2025})
    assert resp.json()["total"] == 1

    resp = client.delete(f"/api/test/rawc/{rawc_id}", headers=h)
    assert resp.status_code == 204


def test_rawc_unique_constraint(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "RAWC2")

    payload = {"control_id": control_id, "fiscal_year": 2024}
    resp = client.post("/api/test/rawc", json=payload, headers=h)
    assert resp.status_code == 201

    # 동일 (control_id, fiscal_year) 중복 → 409
    resp = client.post("/api/test/rawc", json=payload, headers=h)
    assert resp.status_code == 409


# ── TestRun 확장 필드 ─────────────────────────────────────

def test_test_run_extended_fields(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "TR-EXT")

    resp = client.post("/api/test/runs", json={
        "control_id": control_id,
        "fiscal_year": 2025,
        "method_inquiry": True,
        "method_inspection": True,
        "population": "전체 거래 500건",
        "test_frequency": "M",
        "sample_size": 30,
        "procedure": "샘플 30건 검토",
    }, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["fiscal_year"] == 2025
    assert data["status"] == "planned"
    assert data["method_inquiry"] is True
    assert data["sample_size"] == 30


# ── 워크플로 전이 ─────────────────────────────────────────

def test_workflow_planned_to_in_progress(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "WF1")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]
    assert run.json()["status"] == "planned"

    resp = client.post(f"/api/test/runs/{run_id}/transition", json={"to_status": "in_progress"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["test_run"]["status"] == "in_progress"


def test_workflow_full_cycle(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "WF2")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    for to_status in ("in_progress", "completed", "approved"):
        resp = client.post(f"/api/test/runs/{run_id}/transition", json={"to_status": to_status}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["test_run"]["status"] == to_status


def test_workflow_invalid_transition(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "WF3")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    # planned → completed (단계 건너뜀) → 422
    resp = client.post(f"/api/test/runs/{run_id}/transition", json={"to_status": "completed"}, headers=h)
    assert resp.status_code == 422


def test_workflow_no_skip(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "WF4")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    # planned → approved (단계 건너뜀) → 422
    resp = client.post(f"/api/test/runs/{run_id}/transition", json={"to_status": "approved"}, headers=h)
    assert resp.status_code == 422


# ── 상태 이력 ─────────────────────────────────────────────

def test_status_history_immutable(client: TestClient) -> None:
    """이력 API 는 GET(조회)만 있고 DELETE/PATCH 없음 — 불변성 보장."""
    h = _headers(client)
    control_id = _create_control(client, "HIST1")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    # 조회는 가능
    resp = client.get(f"/api/test/runs/{run_id}/history", headers=h)
    assert resp.status_code == 200

    # DELETE·PATCH 엔드포인트가 없으므로 → 404 또는 405
    resp = client.delete(f"/api/test/runs/{run_id}/history", headers=h)
    assert resp.status_code in (404, 405)


def test_status_history_auto_on_create(client: TestClient) -> None:
    """TestRun 생성 시 자동으로 이력 1건 (None → planned) 추가."""
    h = _headers(client)
    control_id = _create_control(client, "HIST2")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    resp = client.get(f"/api/test/runs/{run_id}/history", headers=h)
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["from_status"] is None
    assert items[0]["to_status"] == "planned"


def test_status_history_auto_on_transition(client: TestClient) -> None:
    """전이 시 자동으로 이력 1건 추가 — 총 2건 (생성 + 전이)."""
    h = _headers(client)
    control_id = _create_control(client, "HIST3")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    client.post(f"/api/test/runs/{run_id}/transition", json={"to_status": "in_progress", "reason": "테스트 시작"}, headers=h)

    resp = client.get(f"/api/test/runs/{run_id}/history", headers=h)
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[1]["from_status"] == "planned"
    assert items[1]["to_status"] == "in_progress"
    assert items[1]["reason"] == "테스트 시작"


def test_history_endpoint_returns_chronological_list(client: TestClient) -> None:
    """GET /api/test/runs/{id}/history — 시간순 + changed_by {id, display_name} 포함."""
    h = _headers(client)
    control_id = _create_control(client, "HIST-CHR")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    client.post(f"/api/test/runs/{run_id}/transition", json={"to_status": "in_progress"}, headers=h)

    resp = client.get(f"/api/test/runs/{run_id}/history", headers=h)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2

    # 시간순 (오름차순) 확인
    assert items[0]["changed_at"] <= items[1]["changed_at"]

    # changed_by 중첩 객체: id + display_name 필수 (명세서 5.3절)
    for item in items:
        assert "changed_by" in item
        assert "id" in item["changed_by"]
        assert "display_name" in item["changed_by"]
        assert item["changed_by"]["display_name"]  # 비어있지 않음


def test_history_endpoint_no_post_or_delete(client: TestClient) -> None:
    """history 엔드포인트는 GET 조회만 — POST·DELETE 없음 (ICFR 무결성)."""
    h = _headers(client)
    control_id = _create_control(client, "HIST-IMMUT")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    # GET 은 허용
    resp = client.get(f"/api/test/runs/{run_id}/history", headers=h)
    assert resp.status_code == 200

    # POST·DELETE·PATCH 는 405 (path match, method 없음) 또는 404
    resp_post = client.post(f"/api/test/runs/{run_id}/history", json={}, headers=h)
    assert resp_post.status_code in (404, 405)

    resp_delete = client.delete(f"/api/test/runs/{run_id}/history", headers=h)
    assert resp_delete.status_code in (404, 405)

    resp_patch = client.patch(f"/api/test/runs/{run_id}/history", json={}, headers=h)
    assert resp_patch.status_code in (404, 405)


def test_approved_records_user(client: TestClient) -> None:
    """approved 전이 시 approved_by_id·approved_at 자동 기록."""
    h = _headers(client)
    control_id = _create_control(client, "APPR1")
    run = client.post("/api/test/runs", json={"control_id": control_id, "fiscal_year": 2025}, headers=h)
    run_id = run.json()["id"]

    for ts in ("in_progress", "completed", "approved"):
        client.post(f"/api/test/runs/{run_id}/transition", json={"to_status": ts}, headers=h)

    resp = client.get(f"/api/test/runs/{run_id}", headers=h)
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_by_id"] is not None
    assert data["approved_at"] is not None
