"""평가 영역(테스트·미비점·개선계획·설계평가·RAWC) 쓰기 가드 — EVAL-01 R2.

`external_auditor` 는 조회 전용이다(ADR-0031 §2.1). 이 20개 엔드포인트는 `CurrentUser` 만
받아 외부감사인도 평가 데이터를 만들고 승인할 수 있었다 — 독립성 훼손.

**엔드포인트 목록을 여기 고정해 둔다.** 새 쓰기 엔드포인트가 가드 없이 추가되면
`test_every_write_route_is_listed` 가 잡는다 — 목록만 늘리고 가드를 빼먹는 일을 막는다.

`require_write` 는 경로 인자·본문 검증보다 먼저 풀리므로 빈 본문·없는 id 로도 403 이 나와야 한다.
404/422 가 나오면 가드가 빠진 것이다.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.tenant import UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal

EXT_EMAIL = "ext-eval@acme.example"
EXT_PW = "pw123456"

_ID = str(uuid4())

WRITE_ROUTES = [
    # test_module — RAWC
    ("POST", "/api/test/rawc"),
    ("PATCH", f"/api/test/rawc/{_ID}"),
    ("DELETE", f"/api/test/rawc/{_ID}"),
    # test_module — 테스트 실행
    ("POST", "/api/test/runs"),
    ("POST", f"/api/test/runs/{_ID}/transition"),
    ("PATCH", f"/api/test/runs/{_ID}"),
    ("DELETE", f"/api/test/runs/{_ID}"),
    # test_module — 테스트 단계
    ("POST", "/api/test/steps"),
    ("PATCH", f"/api/test/steps/{_ID}"),
    ("DELETE", f"/api/test/steps/{_ID}"),
    # remediation — 미비점
    ("POST", "/api/remediation/deficiencies"),
    ("PATCH", f"/api/remediation/deficiencies/{_ID}"),
    ("DELETE", f"/api/remediation/deficiencies/{_ID}"),
    # remediation — 개선계획
    ("POST", "/api/remediation/plans"),
    ("PATCH", f"/api/remediation/plans/{_ID}"),
    ("DELETE", f"/api/remediation/plans/{_ID}"),
    ("POST", f"/api/remediation/plans/{_ID}/transition"),
    # remediation — 설계평가
    ("POST", "/api/remediation/design-assessments"),
    ("PATCH", f"/api/remediation/design-assessments/{_ID}"),
    ("DELETE", f"/api/remediation/design-assessments/{_ID}"),
]

# 결재 엔드포인트(ADR-0038 2-3) — `require_icfr_staff`(일반관리자 이상). 외부감사인은 단계가 없어 403(문구는 다르다)
GOVERNANCE_ROUTES = [
    ("POST", f"/api/remediation/deficiencies/{_ID}/transition"),
    ("POST", f"/api/remediation/deficiencies/{_ID}/review"),
    ("POST", f"/api/remediation/deficiencies/{_ID}/external-approval"),
]


def _external_auditor_headers(client: TestClient) -> dict:
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        u = db.query(User).filter(User.email == EXT_EMAIL).first()
        if u is None:
            u = User(email=EXT_EMAIL, hashed_password=hash_password(EXT_PW),
                     display_name="외부감사인(평가)", role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(UserTenantAccess.user_id == u.id,
                                             UserTenantAccess.tenant_id == DEFAULT_TENANT_ID).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
            db.commit()
        if db.query(UserRole).filter(UserRole.user_id == u.id,
                                     UserRole.role_name == "external_auditor").first() is None:
            db.add(UserRole(user_id=u.id, role_name="external_auditor"))
            db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()
    resp = client.post("/api/auth/login", data={"username": EXT_EMAIL, "password": EXT_PW})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


@pytest.mark.parametrize(("method", "path"), WRITE_ROUTES)
def test_external_auditor_cannot_write(client: TestClient, method: str, path: str) -> None:
    h = _external_auditor_headers(client)
    kwargs = {} if method == "DELETE" else {"json": {}}
    resp = client.request(method, path, headers=h, **kwargs)
    assert resp.status_code == 403, f"{method} {path} → {resp.status_code} {resp.text}"
    assert "외부감사인" in resp.json()["detail"]


@pytest.mark.parametrize(("method", "path"), GOVERNANCE_ROUTES)
def test_external_auditor_cannot_use_approval_routes(client: TestClient, method: str, path: str) -> None:
    resp = client.request(method, path, headers=_external_auditor_headers(client), json={})
    assert resp.status_code == 403, f"{method} {path} → {resp.status_code} {resp.text}"


def test_external_auditor_can_still_read(client: TestClient) -> None:
    h = _external_auditor_headers(client)
    for path in ("/api/test/runs", "/api/test/rawc", "/api/remediation/deficiencies",
                 "/api/remediation/plans", "/api/remediation/design-assessments"):
        assert client.get(path, headers=h).status_code == 200, path


def test_every_write_route_is_listed() -> None:
    """test·remediation 라우터의 쓰기 엔드포인트가 전부 WRITE_ROUTES 에 있다."""
    from app.api import remediation, test_module

    listed = {(m, p.replace(_ID, "{id}")) for m, p in WRITE_ROUTES + GOVERNANCE_ROUTES}
    actual = set()
    for router in (test_module.router, remediation.router):
        for r in router.routes:
            for m in r.methods - {"GET", "HEAD", "OPTIONS"}:
                path = r.path
                for name in ("rawc_id", "run_id", "step_id", "deficiency_id", "plan_id", "assessment_id"):
                    path = path.replace("{" + name + "}", "{id}")
                actual.add((m, path))
    assert actual == listed, f"누락: {actual - listed} / 초과: {listed - actual}"
