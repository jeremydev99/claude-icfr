"""Test 모듈 — RAWC 만 남았다. 테스트 기록은 평가 회차(test_my_assessment.py)로 옮겼다(2026-10-15)."""
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
