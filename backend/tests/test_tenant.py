"""멀티테넌시 자동 격리 테스트 (ADR-0025).

before_flush 자동 stamp + do_orm_execute 자동 필터가 회사 간 데이터 누출을
원천 차단하는지 검증한다. ORM 레벨에서 직접 검증 (이벤트 리스너 동작 확인)."""
from app.models.tenant import Tenant
from app.models.rcm import Process
from app.core.tenant_context import (
    set_active_tenant, reset_active_tenant, get_active_tenant, DEFAULT_TENANT_ID,
)
from tests.conftest import TestingSessionLocal


def test_auto_stamp_and_isolation(app):
    """tenant A 컨텍스트로 만든 데이터는 tenant B 컨텍스트에서 보이지 않는다."""
    db = TestingSessionLocal()
    try:
        # 두 번째 회사(tenant B) 준비 (전역 테이블 — 컨텍스트 무관)
        tenant_b = db.query(Tenant).filter(Tenant.code == "TENANT_B").first()
        if not tenant_b:
            tenant_b = Tenant(name="회사B", code="TENANT_B", is_active=True)
            db.add(tenant_b)
            db.commit()
        tb_id = tenant_b.id

        # 기본 tenant 컨텍스트에서 Process 생성 → tenant_id 자동 stamp
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        p_default = Process(code="ISO-DEFAULT", name="기본회사 통제")
        db.add(p_default)
        db.commit()
        assert p_default.tenant_id == DEFAULT_TENANT_ID  # 자동 stamp 확인
        reset_active_tenant(tok)

        # tenant B 컨텍스트에서 Process 생성
        tok = set_active_tenant(tb_id)
        p_b = Process(code="ISO-B", name="회사B 통제")
        db.add(p_b)
        db.commit()
        assert p_b.tenant_id == tb_id

        # tenant B 컨텍스트에서 조회 → B 데이터만, 기본회사 데이터는 안 보임
        codes_b = {p.code for p in db.query(Process).all()}
        assert "ISO-B" in codes_b
        assert "ISO-DEFAULT" not in codes_b
        reset_active_tenant(tok)

        # 기본 tenant 컨텍스트에서 조회 → 기본회사 데이터만
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        codes_d = {p.code for p in db.query(Process).all()}
        assert "ISO-DEFAULT" in codes_d
        assert "ISO-B" not in codes_d
        reset_active_tenant(tok)

        # 컨텍스트 미설정 → 필터 비활성(시스템 맥락): 둘 다 보임
        assert get_active_tenant() is None
        codes_all = {p.code for p in db.query(Process).all()}
        assert {"ISO-DEFAULT", "ISO-B"} <= codes_all
    finally:
        set_active_tenant(None)
        db.close()


def test_api_requires_tenant_access(client):
    """admin 은 기본 tenant 접근 권한이 있어 단일 수렴으로 정상 동작."""
    resp = client.post(
        "/api/auth/login",
        data={"username": "admin@acme.example", "password": "admin123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    # 헤더 없이도 단일 권한 자동 수렴 → 200
    r = client.get("/api/rcm/info", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    # 권한 없는 tenant 헤더 → 403
    r2 = client.get(
        "/api/rcm/info",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": "00000000-0000-0000-0000-0000000000ff",
        },
    )
    assert r2.status_code == 403
