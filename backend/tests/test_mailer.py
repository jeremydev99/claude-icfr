"""메일 발송(2026-10-08) — 사내 메일서버 위임(STARTTLS). 실제 서버 대신 가짜 SMTP 로 검증한다."""
import smtplib

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import mailer


def _h(client: TestClient, email: str = "admin@acme.example", pw: str = "admin123") -> dict:
    r = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class FakeSMTP:
    sent: list = []
    fail_login = False

    def __init__(self, host, port, timeout=None):
        self.calls = [("connect", host, port)]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        self.calls.append(("starttls",))

    def login(self, user, pw):
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"auth failed")
        self.calls.append(("login", user))

    def send_message(self, msg):
        FakeSMTP.sent.append((msg, self.calls))


@pytest.fixture
def smtp(monkeypatch):
    s = get_settings()
    for k, v in {"smtp_host": "smail.example", "smtp_port": 9006, "smtp_user": "icfr@example.com",
                 "smtp_password": "pw", "smtp_from": "icfr@example.com"}.items():
        monkeypatch.setattr(s, k, v)
    FakeSMTP.sent, FakeSMTP.fail_login = [], False
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def test_not_configured_returns_none() -> None:
    assert get_settings().smtp_host == ""
    assert mailer.send("a@b.c", "s", "b").sent is None


def test_send_uses_starttls_and_login(smtp) -> None:
    r = mailer.test_mail("to@example.com")
    assert r.sent is True and r.error is None
    msg, calls = smtp.sent[0]
    assert msg["To"] == "to@example.com" and "icfr@example.com" in msg["From"]
    assert calls == [("connect", "smail.example", 9006), ("starttls",), ("login", "icfr@example.com")]


def test_auth_failure_is_reported_not_raised(smtp) -> None:
    smtp.fail_login = True
    r = mailer.test_mail("to@example.com")
    assert r.sent is False and "인증 실패" in r.error


def test_invite_mails_setup_link(client: TestClient, smtp) -> None:
    h = _h(client)
    r = client.post("/api/users/", headers={**h, "Origin": "https://icfr.example"},
                    json={"email": "mail1@acme.example", "display_name": "메일신입"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["mail_sent"] is True and d["mail_error"] is None
    msg, _ = smtp.sent[-1]
    assert msg["To"] == "mail1@acme.example" and d["setup_url"] in msg.get_content()
    # 재발급도 메일로 — 실패해도 링크는 응답에 남는다
    smtp.fail_login = True
    uid = d["id"]
    r2 = client.post(f"/api/users/{uid}/setup-link", headers={**h, "Origin": "https://icfr.example"}).json()
    assert r2["setup_url"] and r2["mail_sent"] is False and r2["mail_error"]


def test_invite_without_mail_config_keeps_link(client: TestClient) -> None:
    h = _h(client)
    d = client.post("/api/users/", headers=h, json={"email": "mail2@acme.example", "display_name": "설정없음"}).json()
    assert d["setup_url"] and d["mail_sent"] is None


def test_mail_test_endpoint_admin_only(client: TestClient, smtp) -> None:
    h = _h(client)
    assert client.get("/api/notification/mail/status", headers=h).json() == {"configured": True}
    r = client.post("/api/notification/mail/test", headers=h).json()
    assert r == {"to": "admin@acme.example", "sent": True, "error": None}
