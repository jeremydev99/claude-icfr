"""보안 1단계 (2026-10-01, 사외 접속 허용 후) — 계정 잠금·로그인 기록·비밀번호 규칙·변경 후 세션 무효화."""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.password_policy import password_problem
from app.core.security import issued_before_password_change


def _h(client: TestClient, email: str = "admin@acme.example", pw: str = "admin123") -> dict:
    r = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_user(client: TestClient, h: dict, email: str, pw: str = "Initial-123") -> str:
    r = client.post("/api/users/", json={"email": email, "password": pw, "display_name": "테스트"}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_password_policy_rules() -> None:
    assert "8자" in password_problem("abc1234")
    assert password_problem("abcdefgh") is None


def test_weak_password_rejected_on_all_three_paths(client: TestClient) -> None:
    h = _h(client)
    assert client.post("/api/users/", json={"email": "w@acme.example", "password": "short", "display_name": "약"},
                       headers=h).status_code == 422
    uid = _make_user(client, h, "w2@acme.example")
    assert client.post(f"/api/users/{uid}/reset-password", json={"new_password": "short"}, headers=h).status_code == 422
    uh = _h(client, "w2@acme.example", "Initial-123")
    assert client.post("/api/auth/change-password", json={"old_password": "Initial-123", "new_password": "seven77"},
                       headers=uh).status_code == 422


def test_lockout_after_five_failures_and_admin_unlock(client: TestClient) -> None:
    h = _h(client)
    uid = _make_user(client, h, "lock@acme.example")
    bad = {"username": "lock@acme.example", "password": "Wrong-pass-1"}
    for _ in range(5):
        assert client.post("/api/auth/login", data=bad).status_code == 401
    # 잠긴 뒤에는 맞는 비밀번호도 423 — 비밀번호를 확인하지 않는다
    r = client.post("/api/auth/login", data={"username": "lock@acme.example", "password": "Initial-123"})
    assert r.status_code == 423 and "잠겼습니다" in r.json()["detail"]
    row = next(u for u in client.get("/api/users/", headers=h).json()["items"] if u["id"] == uid)
    assert row["failed_login_count"] == 5 and row["locked_until"]

    assert client.post(f"/api/users/{uid}/unlock", headers=h).status_code == 200
    assert client.post("/api/auth/login", data={"username": "lock@acme.example", "password": "Initial-123"}).status_code == 200


def test_success_resets_failure_count(client: TestClient) -> None:
    h = _h(client)
    _make_user(client, h, "reset@acme.example")
    for _ in range(4):
        client.post("/api/auth/login", data={"username": "reset@acme.example", "password": "nope"})
    _h(client, "reset@acme.example", "Initial-123")
    for _ in range(4):  # 다시 4회 실패해도 잠기지 않는다(성공으로 0 이 됐으므로)
        client.post("/api/auth/login", data={"username": "reset@acme.example", "password": "nope"})
    assert client.post("/api/auth/login", data={"username": "reset@acme.example", "password": "Initial-123"}).status_code == 200


def test_admin_reset_password_also_unlocks(client: TestClient) -> None:
    h = _h(client)
    uid = _make_user(client, h, "rl@acme.example")
    for _ in range(5):
        client.post("/api/auth/login", data={"username": "rl@acme.example", "password": "nope"})
    assert client.post(f"/api/users/{uid}/reset-password", json={"new_password": "Brand-new-1"}, headers=h).status_code == 200
    assert client.post("/api/auth/login", data={"username": "rl@acme.example", "password": "Brand-new-1"}).status_code == 200


def test_login_events_recorded_admin_only(client: TestClient) -> None:
    h = _h(client)
    _make_user(client, h, "ev@acme.example")
    client.post("/api/auth/login", data={"username": "ev@acme.example", "password": "nope"},
                headers={"X-Real-IP": "203.0.113.7", "User-Agent": "Mozilla/5.0 (iPhone)"})
    client.post("/api/auth/login", data={"username": "ghost@acme.example", "password": "nope"})
    _h(client, "ev@acme.example", "Initial-123")

    events = client.get("/api/users/login-events", headers=h).json()
    reasons = {(e["email"], e["reason"]) for e in events}
    assert ("ev@acme.example", "bad_password") in reasons
    assert ("ghost@acme.example", "unknown_email") in reasons
    assert ("ev@acme.example", "ok") in reasons
    bad = next(e for e in events if e["email"] == "ev@acme.example" and e["reason"] == "bad_password")
    assert bad["ip"] == "203.0.113.7" and "iPhone" in bad["user_agent"]

    failed = client.get("/api/users/login-events", params={"failed_only": True}, headers=h).json()
    assert failed and all(not e["success"] for e in failed)

    uh = _h(client, "ev@acme.example", "Initial-123")
    assert client.get("/api/users/login-events", headers=uh).status_code == 403


def test_change_password_revokes_old_tokens_and_returns_new(client: TestClient) -> None:
    h = _h(client)
    _make_user(client, h, "tok@acme.example")
    login = client.post("/api/auth/login", data={"username": "tok@acme.example", "password": "Initial-123"}).json()
    old_h = {"Authorization": f"Bearer {login['access_token']}"}

    r = client.post("/api/auth/change-password", json={"old_password": "Initial-123", "new_password": "Changed-123"},
                    headers=old_h)
    assert r.status_code == 200
    body = r.json()
    # 이 기기는 새 토큰으로 계속 쓴다
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 200


def test_issued_before_password_change_rule() -> None:
    changed = datetime(2026, 10, 1, 0, 0, 30, 500000, tzinfo=UTC)
    assert issued_before_password_change({"iat": int((changed - timedelta(seconds=5)).timestamp())}, changed)
    assert not issued_before_password_change({"iat": int(changed.timestamp())}, changed)  # 같은 초는 살린다
    assert issued_before_password_change({}, changed)  # iat 없는 옛 토큰
    assert not issued_before_password_change({}, None)  # 변경 이력 없음 → 그대로
    assert issued_before_password_change({"iat": 0}, changed.replace(tzinfo=None))  # sqlite naive
