"""RCM 모듈 최소 CRUD 통합 테스트."""
import pytest
from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_process_crud(client: TestClient) -> None:
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    resp = client.post("/api/rcm/processes", json={"code": "P-TEST", "name": "테스트 프로세스"}, headers=headers)
    assert resp.status_code == 201
    pid = resp.json()["id"]
    assert resp.json()["code"] == "P-TEST"

    # Get
    resp = client.get(f"/api/rcm/processes/{pid}", headers=headers)
    assert resp.status_code == 200

    # List
    resp = client.get("/api/rcm/processes", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Update
    resp = client.patch(f"/api/rcm/processes/{pid}", json={"name": "수정된 프로세스"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "수정된 프로세스"

    # Delete
    resp = client.delete(f"/api/rcm/processes/{pid}", headers=headers)
    assert resp.status_code == 204

    # Confirm deleted
    resp = client.get(f"/api/rcm/processes/{pid}", headers=headers)
    assert resp.status_code == 404


def test_control_crud(client: TestClient) -> None:
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Prerequisite: create process
    p = client.post("/api/rcm/processes", json={"code": "P-CTL-TEST", "name": "통제 테스트 프로세스"}, headers=headers)
    process_id = p.json()["id"]

    # Create control
    resp = client.post("/api/rcm/controls", json={
        "code": "C-TEST-001", "name": "테스트 통제", "process_id": process_id, "frequency": "monthly"
    }, headers=headers)
    assert resp.status_code == 201
    cid = resp.json()["id"]

    # Get
    resp = client.get(f"/api/rcm/controls/{cid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == "C-TEST-001"

    # List
    resp = client.get("/api/rcm/controls", headers=headers)
    assert resp.json()["total"] >= 1
