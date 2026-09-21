"""`/api/users/roles` 권한 가드·값 검증 (13.9-35, ADR-0031 §3.3).

**이 파일이 없었던 것이 결함의 원인이다.** 역할 관련 테스트가 전부
`db.add(UserRole(...))` 직접 삽입이라 API 경로가 한 번도 검증되지 않았고,
그 사이 생성·수정·삭제 세 엔드포인트가 로그인만 확인한 채로 남았다.
`require_write`·`require_icfr_manager` 가 판정 근거로 삼는 테이블을 누구나
고칠 수 있어 두 가드가 통째로 무력화되는 상태였다.

**그래서 여기서는 DB 직접 삽입으로 검증하지 않는다** — 사전 상태를 만들 때만
직접 삽입하고, 검증 대상 동작은 반드시 HTTP 로 호출한다.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal

PW = "pw123456"


def _login(client: TestClient, email: str) -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": PW})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _user(email: str, name: str, roles: tuple[str, ...] = (), tenant_id=DEFAULT_TENANT_ID):
    """계정 + 테넌트 접근 + (사전 상태로서의) 역할 행을 만든다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(tenant_id)
    try:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password(PW),
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
            if db.query(UserRole).filter(
                UserRole.user_id == u.id, UserRole.role_name == r,
                UserRole.is_deleted == False,  # noqa: E712
            ).first() is None:
                db.add(UserRole(user_id=u.id, role_name=r))
        db.commit()
        return u.id
    finally:
        reset_active_tenant(tok)
        db.close()


def _role_row_id(user_id, role_name: str, tenant_id=DEFAULT_TENANT_ID):
    db = TestingSessionLocal()
    tok = set_active_tenant(tenant_id)
    try:
        row = db.query(UserRole).filter(
            UserRole.user_id == user_id, UserRole.role_name == role_name,
            UserRole.is_deleted == False,  # noqa: E712
        ).first()
        assert row is not None
        return row.id
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §4-1·9-1: 배정·수정 권한 ──────────────────────────────

def test_normal_user_cannot_self_promote(client: TestClient) -> None:
    """§4-1 — 일반 사용자가 자기에게 `icfr_manager` 를 부여할 수 없다.

    **이 작업의 목적이다.** 이게 뚫리면 `require_icfr_manager`(정책 변경)가
    아무것도 막지 못한다 — 실측으로 `PUT /api/org/policies` 200 까지 갔었다.
    """
    uid = _user("rg-plain@acme.example", "일반사용자")
    headers = _login(client, "rg-plain@acme.example")
    resp = client.post("/api/users/roles", headers=headers,
                       json={"user_id": str(uid), "role_name": "icfr_manager"})
    assert resp.status_code == 403, resp.text

    me = client.get("/api/auth/me", headers=headers).json()
    assert "icfr_manager" not in me["tenant_roles"]


def test_non_manager_cannot_update_others_role(client: TestClient) -> None:
    """§4-9-1 — 남의 역할 행을 고치는 것도 막힌다. 수정도 실질적 배정이다."""
    victim = _user("rg-victim@acme.example", "대상자", ("auditor",))
    _user("rg-plain2@acme.example", "일반사용자2")
    row_id = _role_row_id(victim, "auditor")

    resp = client.patch(f"/api/users/roles/{row_id}",
                        headers=_login(client, "rg-plain2@acme.example"),
                        json={"role_name": "icfr_manager"})
    assert resp.status_code == 403, resp.text


# ── §4-2·9-2: 삭제 권한 ───────────────────────────────────

def test_external_auditor_cannot_delete_own_role(client: TestClient) -> None:
    """§4-2 — `external_auditor` 가 자기 역할 행을 지워 조회 전용을 벗어날 수 없다.

    **배정만 막으면 남는 구멍이 이것이다**(13.9-35 ②). 실측으로 204 → `can_write=true`
    였다. 삭제 가드가 없으면 §4-1 을 막아도 권한 체계는 여전히 뚫려 있다.
    """
    uid = _user("rg-ext@acme.example", "외부감사인", ("external_auditor",))
    row_id = _role_row_id(uid, "external_auditor")
    headers = _login(client, "rg-ext@acme.example")

    assert client.delete(f"/api/users/roles/{row_id}", headers=headers).status_code == 403
    assert client.get("/api/auth/me", headers=headers).json()["can_write"] is False


def test_self_delete_denied_regardless_of_role(client: TestClient) -> None:
    """§4-9-2 — 역할 종류와 무관하게 자기 역할 행 삭제는 막힌다.

    `external_auditor` 만 막으면 "누가 자기 역할을 지울 수 있는가"가 역할별
    예외 목록이 된다. 가드는 하나이며 대상은 배정자다.
    """
    uid = _user("rg-self@acme.example", "감사", ("auditor",))
    row_id = _role_row_id(uid, "auditor")
    resp = client.delete(f"/api/users/roles/{row_id}",
                         headers=_login(client, "rg-self@acme.example"))
    assert resp.status_code == 403, resp.text


# ── §4-3: 정상 경로 ───────────────────────────────────────

def test_icfr_manager_can_assign(client: TestClient) -> None:
    """§4-3 — `icfr_manager` 는 다른 사용자에게 역할을 배정한다."""
    _user("rg-mgr@acme.example", "내부회계관리자", ("icfr_manager",))
    target = _user("rg-target@acme.example", "대상")

    resp = client.post("/api/users/roles", headers=_login(client, "rg-mgr@acme.example"),
                       json={"user_id": str(target), "role_name": "auditor"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["role_name"] == "auditor"


# ── §4-6·7·8: 값 검증 ─────────────────────────────────────

@pytest.mark.parametrize("bad", ["icfr_mananger", "Administrator"])
def test_invalid_role_name_rejected(client: TestClient, bad: str) -> None:
    """§4-6·7 — 오타와 구 역할명은 신규 배정되지 않는다(422).

    오타가 201 로 저장되면 어떤 판정에도 걸리지 않아 **조용히 무효**가 된다.
    구 3역할은 읽기만 허용하고 확산을 막는다(13.9-24).
    """
    _user("rg-mgr@acme.example", "내부회계관리자", ("icfr_manager",))
    target = _user("rg-target2@acme.example", "대상2")

    resp = client.post("/api/users/roles", headers=_login(client, "rg-mgr@acme.example"),
                       json={"user_id": str(target), "role_name": bad})
    assert resp.status_code == 422, resp.text


def test_legacy_role_row_is_still_readable(client: TestClient) -> None:
    """§4-8 — 구 역할명이 이미 있는 계정은 그대로 동작한다.

    검증을 `UserRoleRead` 에 걸면 기존 행 조회가 깨진다 — 신규 배정만 막는다.
    """
    _user("rg-legacy@acme.example", "구역할보유", ("Administrator",))
    headers = _login(client, "rg-legacy@acme.example")

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert "Administrator" in me.json()["tenant_roles"]
    assert me.json()["can_write"] is True

    listed = client.get("/api/users/roles/list", headers=headers)
    assert listed.status_code == 200, listed.text


# ── §4-9: 중복 ────────────────────────────────────────────

def test_duplicate_assignment_rejected_and_reassign_allowed(client: TestClient) -> None:
    """§4-9 — 중복 배정은 409. **해제 후 재배정은 정상 동작해야 한다.**

    후자를 함께 보는 이유: 유니크를 부분 인덱스가 아니라 평범한 제약으로 걸면
    해제 행이 남아 재배정이 500 으로 터진다. 중복 금지와 재배정 가능은 한 쌍이다.
    """
    _user("rg-mgr@acme.example", "내부회계관리자", ("icfr_manager",))
    headers = _login(client, "rg-mgr@acme.example")
    target = _user("rg-dup@acme.example", "중복대상")

    first = client.post("/api/users/roles", headers=headers,
                        json={"user_id": str(target), "role_name": "ceo"})
    assert first.status_code == 201, first.text
    dup = client.post("/api/users/roles", headers=headers,
                      json={"user_id": str(target), "role_name": "ceo"})
    assert dup.status_code == 409, dup.text

    assert client.delete(f"/api/users/roles/{first.json()['id']}",
                         headers=headers).status_code == 204
    again = client.post("/api/users/roles", headers=headers,
                        json={"user_id": str(target), "role_name": "ceo"})
    assert again.status_code == 201, again.text


def test_duplicate_is_blocked_by_db_not_only_by_handler() -> None:
    """앱 검증을 우회해도 DB 가 막는다 — 판별은 구조로 둔다.

    핸들러 검증만 두면 경로 하나만 빠뜨려도 뚫린다. 그게 13.9-35 의 원인이었다.
    """
    uid = _user("rg-dbdup@acme.example", "DB중복")
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        db.add(UserRole(user_id=uid, role_name="auditor"))
        db.commit()
        db.add(UserRole(user_id=uid, role_name="auditor"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §4-4·5: 부트스트랩 ────────────────────────────────────

def test_sys_admin_bootstrap_closes_after_first_icfr_manager(client: TestClient) -> None:
    """§4-4·5 — `icfr_manager` 0명일 때만 `sys_admin` 이 배정한다.

    5번이 이 테스트의 핵심이다 — 없으면 `sys_admin` 상시 배정 구현으로도
    통과한다. 별도 테넌트를 쓰는 이유는 기본 테넌트에 다른 테스트가 만든
    `icfr_manager` 가 이미 있어 "0명" 상태를 만들 수 없기 때문이다.
    """
    db = TestingSessionLocal()
    try:
        t = db.query(Tenant).filter(Tenant.code == "ROLEGUARD_B").first()
        if t is None:
            t = Tenant(name="회사B-역할가드", code="ROLEGUARD_B", is_active=True)
            db.add(t)
            db.commit()
        tenant_id = t.id
    finally:
        db.close()

    _user("rg-sysadmin@b.example", "시스템관리자", ("sys_admin",), tenant_id=tenant_id)
    first = _user("rg-b-first@b.example", "첫관리자", tenant_id=tenant_id)
    second = _user("rg-b-second@b.example", "두번째", tenant_id=tenant_id)
    headers = _login(client, "rg-sysadmin@b.example")

    # §4-4: icfr_manager 0명 → 허용
    ok = client.post("/api/users/roles", headers=headers,
                     json={"user_id": str(first), "role_name": "icfr_manager"})
    assert ok.status_code == 201, ok.text

    # §4-5: 1명 생긴 뒤 → 거부. 초기 셋업만 하고 손을 뗀다
    closed = client.post("/api/users/roles", headers=headers,
                         json={"user_id": str(second), "role_name": "auditor"})
    assert closed.status_code == 403, closed.text
