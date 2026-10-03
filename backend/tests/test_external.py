"""외부 사용자 초대·범위·MFA (ADR-0039 §3)."""
from datetime import date, timedelta

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.core import mfa
from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.external import ExternalProfile, Invitation
from tests.conftest import TestingSessionLocal
from tests.test_governance import T, template  # noqa: F401


@pytest.fixture()
def t(client: TestClient) -> T:
    return T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})


def _invite(client, t: T, user_type="advisor", email="ext@firm.example", **kw) -> str:
    body = {"email": email, "display_name": "외부 담당", "user_type": user_type, "organization": "PA회계법인",
            "valid_until": str(date.today() + timedelta(days=90)), **kw}
    r = client.post("/api/external/invitations", headers=t.h["lead"], json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _approve(client, t: T, iid: str) -> str:
    r = client.post(f"/api/external/invitations/{iid}/approve", headers=t.h["master"])
    assert r.status_code == 200, r.text
    return r.json()["invite_url"].rsplit("/", 1)[1]


def _accept_and_enroll(client, token: str, pw="Ext-pass-1") -> tuple[dict, str]:
    """수락 → MFA 등록 → (헤더, OTP 비밀값)."""
    r = client.post(f"/api/invite/{token}/accept", json={"password": pw, "confidentiality": True})
    assert r.status_code == 200, r.text
    mt = r.json()["mfa_token"]
    s = client.post("/api/auth/mfa/setup", json={"mfa_token": mt}).json()
    e = client.post("/api/auth/mfa/enable", json={"mfa_token": mt, "code": pyotp.TOTP(s["secret"]).now()})
    assert e.status_code == 200, e.text
    body = e.json()
    assert len(body["recovery_codes"]) == 10 and body["access_token"]
    return {"Authorization": "Bearer " + body["access_token"]}, s["secret"]


def test_invite_requires_other_approver_and_link_once(client: TestClient, t: T) -> None:
    iid = _invite(client, t)
    # 요청자(lead)는 승인 불가(마스터 아님), 마스터가 요청하면 본인 승인 불가
    assert client.post(f"/api/external/invitations/{iid}/approve", headers=t.h["lead"]).status_code == 403
    r = client.post("/api/external/invitations", headers=t.h["master"], json={
        "email": "x@f.example", "display_name": "x", "user_type": "auditor", "organization": "감사인",
        "valid_until": str(date.today() + timedelta(days=30))})
    assert client.post(f"/api/external/invitations/{r.json()['id']}/approve", headers=t.h["master"]).status_code == 409
    token = _approve(client, t, iid)
    listed = client.get("/api/external/invitations", headers=t.h["lead"]).json()
    assert all(i["invite_url"] is None for i in listed)   # 링크는 승인 응답에서 한 번만
    info = client.get(f"/api/invite/{token}").json()
    assert info["type_label"].startswith("PA회계법인") and info["existing_account"] is False


def test_expired_link_410_and_confidentiality_required(client: TestClient, t: T) -> None:
    token = _approve(client, t, _invite(client, t))
    assert client.post(f"/api/invite/{token}/accept", json={"password": "Ext-pass-1", "confidentiality": False}).status_code == 422
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        inv = db.query(Invitation).filter(Invitation.email == "ext@firm.example").one()
        from datetime import UTC, datetime
        inv.token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        from app.core.audit_context import system_actor
        with system_actor("system:test"):
            db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()
    assert client.post(f"/api/invite/{token}/accept", json={"password": "Ext-pass-1", "confidentiality": True}).status_code == 410


def test_external_login_requires_mfa_and_window(client: TestClient, t: T) -> None:
    token = _approve(client, t, _invite(client, t, email="mfa@firm.example"))
    h, secret = _accept_and_enroll(client, token)
    hh = {**h, "X-Tenant-Id": str(t.tid)}
    assert client.get("/api/auth/me", headers=hh).status_code == 200
    # 다시 로그인 — 비밀번호만으로는 토큰을 못 받는다
    r = client.post("/api/auth/login", data={"username": "mfa@firm.example", "password": "Ext-pass-1"}).json()
    assert r["mfa_required"] and r["access_token"] is None
    assert client.post("/api/auth/mfa/verify", json={"mfa_token": r["mfa_token"], "code": "000000"}).status_code == 401
    ok = client.post("/api/auth/mfa/verify", json={"mfa_token": r["mfa_token"], "code": pyotp.TOTP(secret).now()})
    assert ok.status_code == 200 and ok.json()["access_token"]
    # 기간 밖이면 403
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        from app.core.audit_context import system_actor
        p = db.query(ExternalProfile).one()
        p.valid_until = date.today() - timedelta(days=1)
        with system_actor("system:test"):
            db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()
    assert client.get("/api/auth/me", headers=hh).status_code == 403


def test_recovery_code_single_use(client: TestClient, t: T) -> None:
    token = _approve(client, t, _invite(client, t, email="rc@firm.example"))
    r = client.post(f"/api/invite/{token}/accept", json={"password": "Ext-pass-1", "confidentiality": True}).json()
    s = client.post("/api/auth/mfa/setup", json={"mfa_token": r["mfa_token"]}).json()
    codes = client.post("/api/auth/mfa/enable", json={"mfa_token": r["mfa_token"],
                                                      "code": pyotp.TOTP(s["secret"]).now()}).json()["recovery_codes"]
    for expect in (200, 401):
        lg = client.post("/api/auth/login", data={"username": "rc@firm.example", "password": "Ext-pass-1"}).json()
        assert client.post("/api/auth/mfa/verify", json={"mfa_token": lg["mfa_token"], "code": codes[0]}).status_code == expect


def test_specialist_writes_fs_only_and_committee_read_only(client: TestClient, t: T) -> None:
    from tests.test_fs_upload import _post, bs_wb
    token = _approve(client, t, _invite(client, t, user_type="specialist", email="tax@firm.example"))
    h, _ = _accept_and_enroll(client, token)
    hh = {**h, "X-Tenant-Id": str(t.tid)}
    r = _post(client, hh, bs_wb(), mode="commit")
    assert r.status_code == 200, r.text
    assert all(s["status"] == "draft" for s in r.json()["statements"])   # 작성까지 — 확정은 하지 않는다
    assert client.post("/api/scoping", headers=hh, json={"fiscal_year": 2031}).status_code == 403
    # 감사위원회(auditor) — 조회 전용
    token2 = _approve(client, t, _invite(client, t, user_type="committee", email="ac@board.example"))
    h2, _ = _accept_and_enroll(client, token2)
    me = client.get("/api/auth/me", headers={**h2, "X-Tenant-Id": str(t.tid)}).json()
    assert me["can_write"] is False and "auditor" in me["tenant_roles"]


def test_advisor_prepares_but_cannot_approve(client: TestClient, t: T) -> None:
    token = _approve(client, t, _invite(client, t, email="pa@firm.example"))
    h, _ = _accept_and_enroll(client, token)
    hh = {**h, "X-Tenant-Id": str(t.tid)}
    r = client.post("/api/scoping", headers=hh, json={"fiscal_year": 2032})
    assert r.status_code == 201, r.text
    base = f"/api/scoping/{r.json()['id']}"
    d = client.post(f"{base}/transition", headers=hh, json={"to_status": "review"}).json()
    assert d["governance"]["review_path"] == "lead_then_master"   # 단계 1(일반관리자)처럼
    assert client.post(f"{base}/review", headers=hh, json={"action": "done"}).status_code == 409


def test_mfa_secret_encrypted_roundtrip() -> None:
    s = mfa.new_secret()
    enc = mfa.encrypt(s)
    assert enc != s and mfa.decrypt(enc) == s
    assert mfa.verify(s, pyotp.TOTP(s).now()) and not mfa.verify(s, "12345")
