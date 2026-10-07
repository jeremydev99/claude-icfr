"""직원 초대 (2026-10-07, ADR-0041) — 관리자가 비밀번호를 모르게: 설정 링크로 본인이 정한다."""
from fastapi.testclient import TestClient


def _h(client: TestClient, email: str = "admin@acme.example", pw: str = "admin123") -> dict:
    r = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _token(url: str) -> str:
    return url.rsplit("/setup/", 1)[1]


def test_invite_without_password_then_employee_sets_it(client: TestClient) -> None:
    h = _h(client)
    r = client.post("/api/users/", headers={**h, "Origin": "https://icfr.example"},
                    json={"email": "new1@acme.example", "display_name": "신입"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["invite_pending"] is True and d["setup_url"].startswith("https://icfr.example/setup/")
    tok = _token(d["setup_url"])
    # 아직 로그인할 수 없다(아무도 모르는 비밀번호)
    assert client.post("/api/auth/login", data={"username": "new1@acme.example", "password": ""}).status_code in (401, 422)
    info = client.get(f"/api/account-setup/{tok}").json()
    assert info["email"] == "new1@acme.example" and info["purpose"] == "invite"
    assert client.post(f"/api/account-setup/{tok}", json={"password": "short"}).status_code == 422
    assert client.post(f"/api/account-setup/{tok}", json={"password": "My-own-pass-1"}).status_code == 200
    # 한 번만 — 다시 쓰면 404
    assert client.post(f"/api/account-setup/{tok}", json={"password": "Another-pass-1"}).status_code == 404
    uh = _h(client, "new1@acme.example", "My-own-pass-1")
    me = client.get("/api/auth/me", headers=uh).json()
    assert me["must_change_password"] is False
    row = next(u for u in client.get("/api/users/", headers=h).json()["items"] if u["email"] == "new1@acme.example")
    assert row["invite_pending"] is False
    # 감사 로그에 링크 원문이 남지 않는다
    logs = client.get("/api/admin/audit-logs", headers=h, params={"q": "account-setup"}).json()["items"]
    assert logs and all(tok not in x["path"] for x in logs)


def test_reset_link_keeps_old_password_until_used_and_revokes_previous(client: TestClient) -> None:
    h = _h(client)
    uid = client.post("/api/users/", headers=h, json={"email": "new2@acme.example", "display_name": "둘"}).json()["id"]
    first = _token(client.post(f"/api/users/{uid}/setup-link", headers=h).json()["setup_url"])
    second = client.post(f"/api/users/{uid}/setup-link", headers=h).json()
    assert second["purpose"] == "invite"
    assert client.get(f"/api/account-setup/{first}").status_code == 404     # 새로 발급하면 이전 링크 취소
    client.post(f"/api/account-setup/{_token(second['setup_url'])}", json={"password": "Old-pass-123"})
    # 재설정 링크 — 쓰기 전까지 기존 비밀번호 유효
    reset = client.post(f"/api/users/{uid}/setup-link", headers=h).json()
    assert reset["purpose"] == "reset"
    _h(client, "new2@acme.example", "Old-pass-123")
    client.post(f"/api/account-setup/{_token(reset['setup_url'])}", json={"password": "New-pass-456"})
    assert client.post("/api/auth/login", data={"username": "new2@acme.example", "password": "Old-pass-123"}).status_code == 401
    _h(client, "new2@acme.example", "New-pass-456")


def test_emergency_password_forces_change_before_anything_else(client: TestClient) -> None:
    h = _h(client)
    uid = client.post("/api/users/", headers=h, json={"email": "new3@acme.example", "display_name": "셋",
                                                      "password": "Admin-knows-1"}).json()["id"]
    uh = _h(client, "new3@acme.example", "Admin-knows-1")
    assert client.get("/api/auth/me", headers=uh).json()["must_change_password"] is True
    r = client.get("/api/rcm/controls", headers=uh)
    assert r.status_code == 403 and "비밀번호를 먼저 변경" in r.json()["detail"]
    assert client.post("/api/auth/change-password", headers=uh,
                       json={"old_password": "Admin-knows-1", "new_password": "Admin-knows-1"}).status_code == 400
    r = client.post("/api/auth/change-password", headers=uh, json={"old_password": "Admin-knows-1", "new_password": "Mine-only-22"})
    assert r.status_code == 200
    nh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/rcm/controls", headers=nh).status_code == 200
    # 관리자 비상 재설정도 다시 변경을 강제한다
    client.post(f"/api/users/{uid}/reset-password", headers=h, json={"new_password": "Admin-again-1"})
    assert client.get("/api/auth/me", headers=_h(client, "new3@acme.example", "Admin-again-1")).json()["must_change_password"] is True


def test_only_system_admin_issues_links(client: TestClient) -> None:
    h = _h(client)
    uid = client.post("/api/users/", headers=h, json={"email": "new4@acme.example", "display_name": "넷",
                                                      "password": "Temp-pass-11"}).json()["id"]
    uh = _h(client, "new4@acme.example", "Temp-pass-11")
    tok = client.post("/api/auth/change-password", headers=uh,
                      json={"old_password": "Temp-pass-11", "new_password": "Mine-pass-11"}).json()["access_token"]
    assert client.post(f"/api/users/{uid}/setup-link", headers={"Authorization": f"Bearer {tok}"}).status_code == 403
    assert client.get("/api/account-setup/not-a-real-token").status_code == 404
