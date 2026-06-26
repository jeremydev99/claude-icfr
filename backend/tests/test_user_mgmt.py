"""사용자 모듈 통합 테스트 — 사용자 CRUD + 비밀번호 변경/리셋 (관리자 가드)."""
from fastapi.testclient import TestClient


def _token(client: TestClient, email: str = "admin@acme.example", password: str = "admin123") -> str:
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _headers(client: TestClient, email: str = "admin@acme.example", password: str = "admin123") -> dict:
    return {"Authorization": f"Bearer {_token(client, email, password)}"}


# ── 사용자 CRUD ────────────────────────────────────────────

def test_user_create_update_delete(client: TestClient) -> None:
    h = _headers(client)

    # create
    resp = client.post("/api/users/", json={
        "email": "alice@acme.example",
        "password": "secret123",
        "display_name": "김앨리스",
        "role": "user",
    }, headers=h)
    assert resp.status_code == 201, resp.text
    user = resp.json()
    assert user["display_name"] == "김앨리스"
    assert user["email"] == "alice@acme.example"
    uid = user["id"]

    # email 중복 → 409
    resp = client.post("/api/users/", json={
        "email": "alice@acme.example", "password": "secret123", "display_name": "중복",
    }, headers=h)
    assert resp.status_code == 409

    # update (실명·역할)
    resp = client.patch(f"/api/users/{uid}", json={"display_name": "김앨리스2"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "김앨리스2"

    # delete (일반 사용자)
    resp = client.delete(f"/api/users/{uid}", headers=h)
    assert resp.status_code == 204


def test_user_cannot_delete_self(client: TestClient) -> None:
    """본인 계정 삭제 차단 (409)."""
    h = _headers(client)
    me = client.get("/api/auth/me", headers=h).json()
    resp = client.delete(f"/api/users/{me['id']}", headers=h)
    assert resp.status_code == 409


def test_user_crud_requires_admin(client: TestClient) -> None:
    """일반 사용자는 사용자 생성 불가 (403)."""
    h = _headers(client)
    # 일반 사용자 생성 후 그 토큰으로 시도
    client.post("/api/users/", json={
        "email": "bob@acme.example", "password": "secret123", "display_name": "박밥",
    }, headers=h)
    bob_h = _headers(client, "bob@acme.example", "secret123")
    resp = client.post("/api/users/", json={
        "email": "carol@acme.example", "password": "secret123", "display_name": "최캐롤",
    }, headers=bob_h)
    assert resp.status_code == 403


# ── 비밀번호 변경/리셋 ──────────────────────────────────────

def test_change_password_self(client: TestClient) -> None:
    h = _headers(client)
    client.post("/api/users/", json={
        "email": "dave@acme.example", "password": "oldpass123", "display_name": "정데이브",
    }, headers=h)

    dave_h = _headers(client, "dave@acme.example", "oldpass123")
    # 잘못된 old → 400
    resp = client.post("/api/auth/change-password",
                       json={"old_password": "wrong", "new_password": "newpass123"}, headers=dave_h)
    assert resp.status_code == 400

    # 정상 변경
    resp = client.post("/api/auth/change-password",
                       json={"old_password": "oldpass123", "new_password": "newpass123"}, headers=dave_h)
    assert resp.status_code == 200

    # 새 비번으로 로그인 성공
    assert client.post("/api/auth/login",
                       data={"username": "dave@acme.example", "password": "newpass123"}).status_code == 200


def test_admin_reset_password(client: TestClient) -> None:
    h = _headers(client)
    resp = client.post("/api/users/", json={
        "email": "erin@acme.example", "password": "initpass123", "display_name": "한에린",
    }, headers=h)
    uid = resp.json()["id"]

    # 관리자 리셋 (old 검증 없음)
    resp = client.post(f"/api/users/{uid}/reset-password",
                       json={"new_password": "resetpass123"}, headers=h)
    assert resp.status_code == 200

    assert client.post("/api/auth/login",
                       data={"username": "erin@acme.example", "password": "resetpass123"}).status_code == 200
