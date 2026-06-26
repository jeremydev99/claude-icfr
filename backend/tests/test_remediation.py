"""Remediation 모듈 통합 테스트 — Phase 1 작업4 (DesignAssessment + 워크플로 + 이력)."""
import base64
import json
import pytest
from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _current_user_id(client: TestClient) -> str:
    """JWT 토큰에서 현재 사용자 ID(sub) 추출 — owner_id 등 FK에 사용."""
    token = _token(client)
    payload_part = token.split(".")[1]
    padding = 4 - len(payload_part) % 4
    if padding != 4:
        payload_part += "=" * padding
    payload = json.loads(base64.b64decode(payload_part))
    return payload["sub"]


def _create_control(client: TestClient, suffix: str) -> str:
    """Process → SubProcess → Risk → Control 체인 생성 후 control_id 반환."""
    h = _headers(client)
    p = client.post("/api/rcm/processes", json={"code": f"REM-{suffix}", "name": "테스트"}, headers=h)
    sp = client.post("/api/rcm/sub-processes", json={"code": f"REM-{suffix}-010", "name": "SP", "process_id": p.json()["id"]}, headers=h)
    r = client.post("/api/rcm/risks", json={"code": f"REM-{suffix}-R", "description": "위험", "assessment_level": "LR", "sub_process_id": sp.json()["id"]}, headers=h)
    c = client.post("/api/rcm/controls", json={"code": f"REM-{suffix}-CTL", "name": "통제", "risk_id": r.json()["id"], "frequency": "M"}, headers=h)
    return c.json()["id"]


# ── DesignAssessment CRUD ─────────────────────────────────

def test_design_assessment_crud(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "DA1")

    resp = client.post("/api/remediation/design-assessments", json={
        "control_id": control_id,
        "fiscal_year": 2025,
        "design_score_1": 3,
        "overall_design": "Effective",
        "assessment_method": "Walkthrough",
    }, headers=h)
    assert resp.status_code == 201
    da_id = resp.json()["id"]
    assert resp.json()["overall_design"] == "Effective"
    assert resp.json()["design_score_1"] == 3

    resp = client.get(f"/api/remediation/design-assessments/{da_id}", headers=h)
    assert resp.status_code == 200

    resp = client.patch(f"/api/remediation/design-assessments/{da_id}", json={"overall_design": "Not_Effective"}, headers=h)
    assert resp.json()["overall_design"] == "Not_Effective"

    resp = client.get("/api/remediation/design-assessments/by-control/" + control_id, headers=h, params={"fiscal_year": 2025})
    assert resp.json()["total"] == 1

    resp = client.delete(f"/api/remediation/design-assessments/{da_id}", headers=h)
    assert resp.status_code == 204


def test_design_assessment_unique_per_year(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "DA2")

    payload = {"control_id": control_id, "fiscal_year": 2024}
    resp = client.post("/api/remediation/design-assessments", json=payload, headers=h)
    assert resp.status_code == 201

    # 동일 (control_id, fiscal_year) 중복 → 409
    resp = client.post("/api/remediation/design-assessments", json=payload, headers=h)
    assert resp.status_code == 409


# ── Deficiency 확장 필드 ───────────────────────────────────

def test_deficiency_extended_fields(client: TestClient) -> None:
    h = _headers(client)
    control_id = _create_control(client, "DEF1")

    resp = client.post("/api/remediation/deficiencies", json={
        "code": "TEST-DEF-001",
        "severity": "high",
        "description": "테스트 미비점",
        "fiscal_year": 2025,
        "control_id": control_id,
    }, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["fiscal_year"] == 2025
    assert data["control_id"] == control_id
    assert data["final_conclusion"] is None

    def_id = data["id"]
    resp = client.patch(f"/api/remediation/deficiencies/{def_id}", json={
        "final_conclusion": "미비점 확인 완료",
    }, headers=h)
    assert resp.json()["final_conclusion"] == "미비점 확인 완료"


def test_deficiency_multiple_per_control_year(client: TestClient) -> None:
    """같은 통제·연도에 다수 미비점 허용 (Q4 결정)."""
    h = _headers(client)
    control_id = _create_control(client, "DEF2")

    for i in range(3):
        resp = client.post("/api/remediation/deficiencies", json={
            "code": f"MULTI-DEF-{i:03d}",
            "severity": "low",
            "description": f"미비점 {i}",
            "fiscal_year": 2025,
            "control_id": control_id,
        }, headers=h)
        assert resp.status_code == 201

    resp = client.get("/api/remediation/deficiencies", headers=h)
    defs = [d for d in resp.json()["items"] if d["control_id"] == control_id]
    assert len(defs) == 3


# ── RemediationPlan 워크플로 ───────────────────────────────

def _create_deficiency_and_plan(client: TestClient, suffix: str) -> tuple[str, str]:
    """Deficiency + RemediationPlan 생성 후 (def_id, plan_id) 반환."""
    h = _headers(client)
    owner_id = _current_user_id(client)
    control_id = _create_control(client, suffix)
    d = client.post("/api/remediation/deficiencies", json={
        "code": f"WF-DEF-{suffix}",
        "severity": "medium",
        "description": "워크플로 테스트용",
        "fiscal_year": 2025,
    }, headers=h)
    def_id = d.json()["id"]
    p = client.post("/api/remediation/plans", json={
        "deficiency_id": def_id,
        "owner_id": owner_id,
        "target_date": "2026-12-31",
        "action_plan": "개선 계획",
    }, headers=h)
    assert p.status_code == 201, f"create_plan 실패: {p.text}"
    return def_id, p.json()["id"]


def test_remediation_plan_workflow(client: TestClient) -> None:
    h = _headers(client)
    _, plan_id = _create_deficiency_and_plan(client, "WF1")

    # 초기 상태는 planned
    resp = client.get(f"/api/remediation/plans/{plan_id}", headers=h)
    assert resp.json()["status"] == "planned"

    # planned → in_progress
    resp = client.post(f"/api/remediation/plans/{plan_id}/transition", json={"to_status": "in_progress"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    # in_progress → completed
    resp = client.post(f"/api/remediation/plans/{plan_id}/transition", json={"to_status": "completed"}, headers=h)
    assert resp.json()["status"] == "completed"

    # completed → approved
    resp = client.post(f"/api/remediation/plans/{plan_id}/transition", json={"to_status": "approved"}, headers=h)
    assert resp.json()["status"] == "approved"
    assert resp.json()["approved_by_id"] is not None
    assert resp.json()["approved_at"] is not None


def test_remediation_workflow_no_skip(client: TestClient) -> None:
    """단계 건너뛰기 차단 — planned → completed 불가."""
    h = _headers(client)
    _, plan_id = _create_deficiency_and_plan(client, "WF2")

    resp = client.post(f"/api/remediation/plans/{plan_id}/transition", json={"to_status": "completed"}, headers=h)
    assert resp.status_code == 422


def test_remediation_workflow_approved_immutable(client: TestClient) -> None:
    """approved 상태에서는 전이 불가."""
    h = _headers(client)
    _, plan_id = _create_deficiency_and_plan(client, "WF3")

    for s in ["in_progress", "completed", "approved"]:
        client.post(f"/api/remediation/plans/{plan_id}/transition", json={"to_status": s}, headers=h)

    resp = client.post(f"/api/remediation/plans/{plan_id}/transition", json={"to_status": "in_progress"}, headers=h)
    assert resp.status_code == 422


def test_remediation_status_history_auto_create(client: TestClient) -> None:
    """plan 생성 시 자동 이력 (from_status=None, to_status='planned') 생성."""
    h = _headers(client)
    _, plan_id = _create_deficiency_and_plan(client, "HIST1")

    resp = client.get(f"/api/remediation/plans/{plan_id}/history", headers=h)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["from_status"] is None
    assert items[0]["to_status"] == "planned"


def test_remediation_status_history_auto_transition(client: TestClient) -> None:
    """전이 시 자동 이력 추가 확인."""
    h = _headers(client)
    _, plan_id = _create_deficiency_and_plan(client, "HIST2")

    client.post(f"/api/remediation/plans/{plan_id}/transition",
                json={"to_status": "in_progress", "reason": "개선 시작"}, headers=h)

    resp = client.get(f"/api/remediation/plans/{plan_id}/history", headers=h)
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[1]["from_status"] == "planned"
    assert items[1]["to_status"] == "in_progress"
    assert items[1]["reason"] == "개선 시작"


def test_deficiency_delete_blocked_by_active_plan(client: TestClient) -> None:
    """활성 개선계획이 연결된 미비점은 삭제 불가 (409)."""
    h = _headers(client)
    def_id, _ = _create_deficiency_and_plan(client, "FKGUARD")

    resp = client.delete(f"/api/remediation/deficiencies/{def_id}", headers=h)
    assert resp.status_code == 409


def test_remediation_history_changed_by_realname(client: TestClient) -> None:
    """history 응답에 changed_by(id+display_name 실명)가 내려온다 — test_module과 일관."""
    h = _headers(client)
    user_id = _current_user_id(client)
    _, plan_id = _create_deficiency_and_plan(client, "HISTNAME")

    resp = client.get(f"/api/remediation/plans/{plan_id}/history", headers=h)
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["changed_by_id"] == user_id          # 하위 호환 유지
    assert item["changed_by"]["id"] == user_id       # join된 객체
    assert item["changed_by"]["display_name"]        # 실명 비어있지 않음


def test_approved_records_user(client: TestClient) -> None:
    """approved 전이 시 approved_by_id, approved_at 자동 기록."""
    h = _headers(client)
    _, plan_id = _create_deficiency_and_plan(client, "APR1")

    for s in ["in_progress", "completed", "approved"]:
        client.post(f"/api/remediation/plans/{plan_id}/transition", json={"to_status": s}, headers=h)

    resp = client.get(f"/api/remediation/plans/{plan_id}", headers=h)
    data = resp.json()
    assert data["approved_by_id"] is not None
    assert data["approved_at"] is not None
