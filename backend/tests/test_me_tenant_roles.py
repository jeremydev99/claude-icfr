"""`/me` 제도 운영 역할·쓰기 가능 여부 (Regina 요청, ADR-0031 §2.1).

**FE 가 `external_auditor` 를 판정할 소스가 없었다.** `/me` 는 `UserTenantAccess` 만
조회했고, `require_write` 의 판정 근거인 `user_roles` 는 응답 어디에도 없었다.
`UserProfile.role` 은 `users.role`(시스템 admin)이라 다른 값이다.

**`can_write` 는 `core/permissions.can_write` 를 그대로 쓴다** — 규칙이 백엔드와 FE
두 곳에 존재하면 어긋날 때 어느 쪽이 맞는지 알 수 없다. 여기서는 그 재사용이
실제로 유지되는지도 함께 본다.
"""
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal


def _login(client: TestClient, email: str, pw: str) -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _user_with_roles(email: str, name: str, roles: tuple[str, ...],
                     tenant_id=DEFAULT_TENANT_ID):
    db = TestingSessionLocal()
    tok = set_active_tenant(tenant_id)
    try:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password("pw123456"),
                     display_name=name, role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(
            UserTenantAccess.user_id == u.id,
            UserTenantAccess.tenant_id == tenant_id,
        ).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=tenant_id, role="user"))
            db.commit()
        for r in roles:
            if db.query(UserRole).filter(UserRole.user_id == u.id,
                                         UserRole.role_name == r).first() is None:
                db.add(UserRole(user_id=u.id, role_name=r))
        db.commit()
        return u.id
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §1 external_auditor ───────────────────────────────────

def test_external_auditor_cannot_write(client: TestClient) -> None:
    """§1 — `can_write=false`, `tenant_roles` 에 `external_auditor` 포함.

    FE 는 버튼 숨김에 `can_write`, 안내 문구에 `tenant_roles` 를 쓴다 —
    `can_write` 만으로는 "왜 못 쓰는지"를 사용자에게 설명할 수 없다.
    """
    _user_with_roles("ext-me@acme.example", "외부감사인", ("external_auditor",))
    body = client.get("/api/auth/me",
                      headers=_login(client, "ext-me@acme.example", "pw123456")).json()
    assert body["can_write"] is False
    assert "external_auditor" in body["tenant_roles"]


# ── §2 일반 계정 ──────────────────────────────────────────

def test_plain_user_can_write(client: TestClient) -> None:
    """§2 — 역할이 없어도 쓰기 가능. 제한은 `external_auditor` 에만 걸린다."""
    _user_with_roles("plain-me@acme.example", "일반사용자", ())
    body = client.get("/api/auth/me",
                      headers=_login(client, "plain-me@acme.example", "pw123456")).json()
    assert body["can_write"] is True
    assert body["tenant_roles"] == []


# ── §3 복수 역할 ──────────────────────────────────────────

def test_multiple_roles_all_returned(client: TestClient) -> None:
    """§3 — 여러 역할을 가진 계정은 전부 나온다. 한 사람이 여러 역할을 가질 수 있다."""
    _user_with_roles("multi-me@acme.example", "겸직자",
                     ("icfr_manager", "assessor", "auditor"))
    body = client.get("/api/auth/me",
                      headers=_login(client, "multi-me@acme.example", "pw123456")).json()
    assert set(body["tenant_roles"]) == {"icfr_manager", "assessor", "auditor"}
    assert body["can_write"] is True          # external_auditor 가 아니므로


# ── §4 활성 테넌트 기준 ───────────────────────────────────

def test_roles_follow_active_tenant(client: TestClient) -> None:
    """§4 — 활성 테넌트가 바뀌면 그 테넌트 기준 값이 나온다.

    `user_roles` 는 `AuditedBase` 라 활성 테넌트로 **자동 필터**된다(ADR-0025).
    A사에서 external_auditor 인 사람이 B사에서는 아닐 수 있다.
    """
    db = TestingSessionLocal()
    try:
        other = db.query(Tenant).filter(Tenant.code == "TENANT_ME_B").first()
        if other is None:
            other = Tenant(name="회사B-me", code="TENANT_ME_B", is_active=True)
            db.add(other)
            db.commit()
        other_id = other.id
    finally:
        db.close()

    # A사에서만 external_auditor, B사에는 접근 권한만
    _user_with_roles("dual-me@acme.example", "양사소속", ("external_auditor",))
    _user_with_roles("dual-me@acme.example", "양사소속", (), tenant_id=other_id)

    h = _login(client, "dual-me@acme.example", "pw123456")
    a = client.get("/api/auth/me", headers={**h, "X-Tenant-Id": str(DEFAULT_TENANT_ID)}).json()
    b = client.get("/api/auth/me", headers={**h, "X-Tenant-Id": str(other_id)}).json()

    assert a["active_tenant_id"] == str(DEFAULT_TENANT_ID)
    assert a["can_write"] is False
    assert "external_auditor" in a["tenant_roles"]

    assert b["active_tenant_id"] == str(other_id)     # 헤더대로 따라간다
    assert b["can_write"] is True
    assert b["tenant_roles"] == []


def test_active_tenant_id_follows_header_not_first_tenant(client: TestClient) -> None:
    """`active_tenant_id` 가 헤더의 활성 테넌트를 따른다.

    **이전에는 `tenants[0]`(생성순 첫 번째)를 반환했다.** 테넌트가 1개뿐이라
    드러나지 않았을 뿐, 여러 테넌트 + 헤더 지정 시 실제 활성 테넌트와 다른 값을
    보고했다. `tenant_roles`·`can_write` 가 활성 테넌트 기준이므로 어긋나면
    응답 자체가 모순된다.
    """
    db = TestingSessionLocal()
    try:
        other = db.query(Tenant).filter(Tenant.code == "TENANT_ME_C").first()
        if other is None:
            other = Tenant(name="회사C-me", code="TENANT_ME_C", is_active=True)
            db.add(other)
            db.commit()
        other_id = other.id
    finally:
        db.close()

    _user_with_roles("hdr-me@acme.example", "헤더검증", ())
    _user_with_roles("hdr-me@acme.example", "헤더검증", (), tenant_id=other_id)
    h = _login(client, "hdr-me@acme.example", "pw123456")

    body = client.get("/api/auth/me", headers={**h, "X-Tenant-Id": str(other_id)}).json()
    assert body["active_tenant_id"] == str(other_id)
    # 접근 가능한 테넌트 목록에는 둘 다 있다
    assert {t["id"] for t in body["tenants"]} >= {str(DEFAULT_TENANT_ID), str(other_id)}


def test_can_write_uses_shared_predicate() -> None:
    """`/me` 와 `require_write` 가 **같은 함수**를 쓴다.

    로직을 복제하면 이 작업의 목적이 무너진다 — 규칙이 두 곳에 있으면 어긋날 때
    어느 쪽이 맞는지 알 수 없다. 판정 함수가 한 곳뿐임을 코드 수준에서 고정한다.
    """
    import inspect

    from app.core import permissions

    assert permissions.can_write({"external_auditor"}) is False
    assert permissions.can_write(set()) is True
    # require_write 가 자체 판정을 갖지 않고 can_write 를 호출한다
    assert "can_write(" in inspect.getsource(permissions.require_write)
