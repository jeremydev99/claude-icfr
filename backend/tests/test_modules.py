"""11개 모듈 라우터 등록 + /info 엔드포인트 동작 검증."""
import pytest
from fastapi.testclient import TestClient

MODULE_PREFIXES = [
    "/api/schedule",
    "/api/rcm",
    "/api/scoping",
    "/api/euc",
    "/api/iuc",
    "/api/remediation",
    "/api/evidence",
    "/api/users",
    "/api/notification",
    "/api/report",
    "/api/test",
]


def _get_admin_token(client: TestClient) -> str:
    """admin 로그인 후 access token 반환. OAuth2PasswordRequestForm = form data."""
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@acme.example", "password": "admin123"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.mark.parametrize("prefix", MODULE_PREFIXES)
def test_module_info_requires_auth(client: TestClient, prefix: str) -> None:
    """인증 없이는 401."""
    response = client.get(f"{prefix}/info")
    assert response.status_code == 401


@pytest.mark.parametrize("prefix", MODULE_PREFIXES)
def test_module_info_with_auth(client: TestClient, prefix: str) -> None:
    """admin 인증 후 정상 응답 + 필수 필드 확인."""
    token = _get_admin_token(client)
    response = client.get(
        f"{prefix}/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "module" in data
    assert "name_kr" in data
    assert "available_in_phase_1" in data


def test_system_modules_list(client: TestClient) -> None:
    """/api/system/modules가 11개 모듈 반환."""
    token = _get_admin_token(client)
    response = client.get(
        "/api/system/modules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    modules = response.json()
    assert len(modules) == 11
    # Phase 1 A-1안: rcm, remediation, evidence, user_mgmt, test_module = 5개
    phase_1_active = [m for m in modules if m["available_in_phase_1"]]
    assert len(phase_1_active) == 5


def test_system_info(client: TestClient) -> None:
    """/api/system/info 응답 확인."""
    token = _get_admin_token(client)
    response = client.get(
        "/api/system/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["module_count"] == 11
    assert data["active_in_phase_1"] == 5


def test_request_id_header(client: TestClient) -> None:
    """모든 응답에 X-Request-ID 헤더 포함."""
    response = client.get("/")
    assert "x-request-id" in {k.lower() for k in response.headers}
