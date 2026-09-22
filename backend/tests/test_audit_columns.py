"""감사 컬럼 자동 기록 (ADR-0036, 13.9-51).

`created_by`·`updated_by`·`deleted_by`·`deleted_at` 은 핸들러가 대입하지 않는다 —
`core/audit_context.py` 의 before_flush 가 행위자 ContextVar 로 찍는다.

**이 파일이 고정하는 것.**
① 매핑된 **모든** 감사 대상 모델(믹스인으로 판별 — 테이블명 하드코딩 금지)에서
   insert·update·소프트 삭제·복구 시 네 컬럼 값.
② 행위자가 없으면 flush 가 실패한다(fail-closed). `unknown` 같은 기본값은 없다.
③ `session.info` 행위자는 **테스트 전용**이다 — 운영 `SessionLocal` 과 API 요청 세션에는 없다.
   있으면 API 경로의 행위자 누락이 조용히 `system:test` 로 채워진다.
④ bulk UPDATE/DELETE 는 before_flush 를 거치지 않으므로 막는다.
⑤ bootstrap 은 `system:bootstrap` 으로 기록된다 — lifespan 이 예외를 로그로만 남기므로,
   행위자 지정이 빠지면 운영 admin 생성이 **조용히** 실패한다.

①·④·⑤ 는 격리 sqlite 를 쓴다(공유 test.db 에 더미 행을 남기지 않는다).
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — 모든 모델을 Base.metadata 에 등록
from app.core import database as app_database
from app.core.audit_context import (
    SESSION_INFO_ACTOR_KEY,
    SYSTEM_BOOTSTRAP,
    SYSTEM_SEED_USERS,
    SYSTEM_TEST,
    AuditBypassError,
    MissingActorError,
    reset_current_actor,
    set_user_actor,
    system_actor,
)
from app.core.database import get_db
from app.core.security import hash_password
from app.core.tenant_context import (
    DEFAULT_TENANT_CODE,
    DEFAULT_TENANT_ID,
    DEFAULT_TENANT_NAME,
    reset_active_tenant,
    set_active_tenant,
)
from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.org import Department
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.seeds.bootstrap import bootstrap_admin
from tests.conftest import ApiSessionLocal, TestingSessionLocal

PW = "pw123456"

AUDITED_MODELS = sorted(
    (m.class_ for m in Base.registry.mappers
     if issubclass(m.class_, TimestampMixin | SoftDeleteMixin)),
    key=lambda c: c.__tablename__,
)


# ── 격리 sqlite ───────────────────────────────────────────

@pytest.fixture()
def iso(tmp_path):
    """격리 sqlite 세션 팩토리 — info 없음(운영과 같은 조건). 기본 tenant 행 1개."""
    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with system_actor(SYSTEM_TEST):
        db = factory()
        db.add(Tenant(id=DEFAULT_TENANT_ID, name=DEFAULT_TENANT_NAME,
                      code=DEFAULT_TENANT_CODE, is_active=True))
        db.commit()
        db.close()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        yield factory
    finally:
        reset_active_tenant(tok)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


class _AsUser:
    """get_current_user 가 하는 것과 같은 행위자 설정(요청 사용자 id 문자열)."""

    def __init__(self, user_id: UUID):
        self.user_id = user_id

    def __enter__(self):
        self.tok = set_user_actor(self.user_id)
        return str(self.user_id)

    def __exit__(self, *exc):
        reset_current_actor(self.tok)


def _dummy(col):
    """NOT NULL·기본값 없는 컬럼의 더미 값 — 타입으로만 정한다(sqlite 는 FK 를 강제하지 않는다)."""
    try:
        py = col.type.python_type
    except NotImplementedError:
        py = str
    if hasattr(col.type, "enums") and col.type.enums:
        return col.type.enums[0]
    if py is str:
        n = getattr(col.type, "length", None) or 32
        return uuid4().hex[:n]
    if py is bool:
        return False
    if py is int:
        return 1
    if py is float:
        return 1.0
    if py is Decimal:
        return Decimal("1")
    if py is datetime:
        return datetime(2026, 1, 1)
    if py is date:
        return date(2026, 1, 1)
    if py is UUID:
        return uuid4()
    if py is dict:
        return {}
    if py is list:
        return []
    raise AssertionError(f"더미 값을 만들 수 없는 타입: {col.table.name}.{col.name} {col.type}")


def _build(model):
    kw = {}
    for col in model.__table__.columns:
        if col.nullable or col.default is not None or col.server_default is not None:
            continue
        if issubclass(model, TenantMixin) and col.key == "tenant_id":  # before_flush 가 stamp (ADR-0025)
            continue
        kw[col.key] = _dummy(col)
    return model(**kw)


# ── ① 전 모델 순회 ────────────────────────────────────────

def test_audited_models_cover_every_mapped_table():
    """대상은 매핑 전부다. 새 모델이 믹스인을 빼고 들어오면 여기서 드러난다."""
    assert len(AUDITED_MODELS) == len(Base.registry.mappers) >= 52


@pytest.mark.parametrize("model", AUDITED_MODELS, ids=lambda c: c.__tablename__)
def test_insert_update_soft_delete_restore(iso, model):
    a, b, c = uuid4(), uuid4(), uuid4()
    db = iso()
    try:
        with _AsUser(a) as actor_a:
            obj = _build(model)
            db.add(obj)
            db.commit()
            assert (obj.created_by, obj.updated_by) == (actor_a, actor_a)
            assert obj.deleted_by is None and obj.deleted_at is None
            if isinstance(obj, TenantMixin):
                assert obj.tenant_id == DEFAULT_TENANT_ID  # tenant stamp 회귀 없음

        with _AsUser(b) as actor_b:
            obj.row_version = (obj.row_version or 1) + 1
            db.commit()
            assert obj.updated_by == actor_b
            assert obj.created_by == actor_a, "update 가 created_by 를 바꾸면 안 된다"

            obj.is_deleted = True
            db.commit()
            assert obj.deleted_by == actor_b
            assert obj.deleted_at is not None
            assert obj.created_by == actor_a

        with _AsUser(c) as actor_c:
            obj.is_deleted = False
            db.commit()
            assert obj.deleted_by is None and obj.deleted_at is None
            assert obj.updated_by == actor_c
            assert obj.created_by == actor_a
    finally:
        db.close()


def test_preset_created_by_is_kept_on_insert(iso):
    db = iso()
    try:
        with _AsUser(uuid4()) as actor:
            d = Department(name="기존값", created_by="system:seed-users")
            db.add(d)
            db.commit()
            assert d.created_by == "system:seed-users"
            assert d.updated_by == actor
    finally:
        db.close()


def test_unrelated_flush_does_not_backfill_null_rows(iso):
    """기존 NULL 행은 채우지 않는다 — 모르는 과거를 지어내지 않는다."""
    db = iso()
    try:
        rid = str(uuid4())
        db.execute(text(
            "INSERT INTO departments (id, tenant_id, name, created_at, updated_at, is_deleted, row_version)"
            " VALUES (:id, :t, '과거행', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 1)"
        ), {"id": rid.replace("-", ""), "t": DEFAULT_TENANT_ID.hex})
        db.commit()
        with _AsUser(uuid4()):
            db.add(Department(name="새행"))
            db.commit()
        row = db.execute(text(
            "SELECT created_by, updated_by, deleted_by FROM departments WHERE name = '과거행'"
        )).one()
        assert tuple(row) == (None, None, None)
    finally:
        db.close()


# ── 시스템 행위자 ─────────────────────────────────────────

def test_system_actor_is_recorded(iso):
    db = iso()
    try:
        with system_actor(SYSTEM_SEED_USERS):
            d = Department(name="시드부서")
            db.add(d)
            db.commit()
        assert (d.created_by, d.updated_by) == (SYSTEM_SEED_USERS, SYSTEM_SEED_USERS)
    finally:
        db.close()


@pytest.mark.parametrize("bad", ["unknown", "system:", "system:Seed", "System:seed", "system:seed users"])
def test_system_actor_format_is_enforced(bad):
    with pytest.raises(ValueError):
        with system_actor(bad):
            pass


def test_test_session_records_system_test(app):
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        d = Department(name=f"테스트세션-{uuid4().hex[:8]}")
        db.add(d)
        db.commit()
        assert d.created_by == SYSTEM_TEST
        d.is_deleted = True
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()


def test_bootstrap_records_system_bootstrap(iso):
    db = iso()
    try:
        # 기본 tenant 가 이미 있으므로 새 tenant 경로까지 보려면 한 번 비운다
        with system_actor(SYSTEM_TEST):
            db.delete(  # bulk DELETE 는 막혀 있다 — 객체로 지운다
                db.get(Tenant, DEFAULT_TENANT_ID))
            db.commit()
        bootstrap_admin(db)
        tenant = db.get(Tenant, DEFAULT_TENANT_ID)
        admin = db.query(User).filter(User.role == "admin").one()
        access = db.query(UserTenantAccess).filter(UserTenantAccess.user_id == admin.id).one()
        for obj in (tenant, admin, access):
            assert (obj.created_by, obj.updated_by) == (SYSTEM_BOOTSTRAP, SYSTEM_BOOTSTRAP)
        bootstrap_admin(db)  # 멱등 — 두 번째는 쓰기 없음, 실패 없음
    finally:
        db.close()


# ── ② fail-closed ────────────────────────────────────────

def test_insert_without_actor_fails(iso):
    db = iso()
    try:
        db.add(Department(name="행위자없음"))
        with pytest.raises(MissingActorError, match=r"Department.*system_actor.*ADR-0036"):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_update_and_hard_delete_without_actor_fail(iso):
    db = iso()
    try:
        with _AsUser(uuid4()):
            d = Department(name="수정대상")
            db.add(d)
            db.commit()
        d.name = "수정됨"
        with pytest.raises(MissingActorError):
            db.flush()
        db.rollback()
        db.delete(d)
        with pytest.raises(MissingActorError):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_api_session_without_user_fails(app):
    """API 요청 세션(info 없음)에서 get_current_user 를 거치지 않으면 실패한다."""
    db = ApiSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        db.add(Department(name=f"api-무행위자-{uuid4().hex[:8]}"))
        with pytest.raises(MissingActorError):
            db.flush()
    finally:
        db.rollback()
        reset_active_tenant(tok)
        db.close()


# ── ③ session.info 행위자는 테스트 전용 ──────────────────

def test_production_and_api_sessions_carry_no_info_actor(app):
    for factory in (app_database.SessionLocal, ApiSessionLocal):
        assert SESSION_INFO_ACTOR_KEY not in (factory.kw.get("info") or {})
    prod = app_database.SessionLocal()
    try:
        assert SESSION_INFO_ACTOR_KEY not in prod.info
    finally:
        prod.close()
    gen = app.dependency_overrides[get_db]()
    api_db = next(gen)
    try:
        assert SESSION_INFO_ACTOR_KEY not in api_db.info
    finally:
        gen.close()


# ── ④ bulk DML 차단 ──────────────────────────────────────

def test_bulk_update_and_delete_are_blocked(iso):
    db = iso()
    try:
        with _AsUser(uuid4()):
            with pytest.raises(AuditBypassError):
                db.query(Department).update({"name": "일괄"})
            with pytest.raises(AuditBypassError):
                db.execute(update(Department.__table__).values(name="일괄"))
            with pytest.raises(AuditBypassError):
                db.query(Department).delete()
    finally:
        db.rollback()
        db.close()


# ── API 경로 + tenant 격리 회귀 ──────────────────────────

def _account(email: str, tenant_id: UUID, roles: tuple[str, ...] = ()) -> str:
    db = TestingSessionLocal()
    tok = set_active_tenant(tenant_id)
    try:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password(PW),
                     display_name=email, role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(
            UserTenantAccess.user_id == u.id, UserTenantAccess.tenant_id == tenant_id,
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
        return str(u.id)
    finally:
        reset_active_tenant(tok)
        db.close()


def _headers(client: TestClient, email: str) -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": PW})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _row(dept_id: str) -> Department:
    db = TestingSessionLocal()
    try:
        return db.execute(
            text("SELECT tenant_id, created_by, updated_by, deleted_by, deleted_at, is_deleted"
                 " FROM departments WHERE id = :id"),
            {"id": UUID(dept_id).hex},
        ).one()
    finally:
        db.close()


def test_api_create_update_delete_records_request_user(client: TestClient):
    m1 = _account("audit-m1@acme.example", DEFAULT_TENANT_ID, ("icfr_manager",))
    m2 = _account("audit-m2@acme.example", DEFAULT_TENANT_ID, ("icfr_manager",))
    h1, h2 = _headers(client, "audit-m1@acme.example"), _headers(client, "audit-m2@acme.example")

    r = client.post("/api/org/departments", headers=h1, json={"name": f"감사-{uuid4().hex[:6]}"})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    row = _row(did)
    assert (row.created_by, row.updated_by) == (m1, m1)

    assert client.patch(f"/api/org/departments/{did}", headers=h2,
                        json={"external_code": "X1"}).status_code == 200
    row = _row(did)
    assert (row.created_by, row.updated_by) == (m1, m2)

    assert client.delete(f"/api/org/departments/{did}", headers=h2).status_code == 204
    row = _row(did)
    assert row.is_deleted and row.deleted_by == m2 and row.deleted_at is not None
    assert row.created_by == m1


def test_other_tenant_user_write_is_stamped_and_isolated(client: TestClient):
    db = TestingSessionLocal()
    try:
        t2 = db.query(Tenant).filter(Tenant.code == "AUDIT-T2").first()
        if t2 is None:
            t2 = Tenant(name="감사테넌트2", code="AUDIT-T2", is_active=True)
            db.add(t2)
            db.commit()
        t2_id = t2.id
    finally:
        db.close()
    other = _account("audit-t2@acme.example", t2_id, ("icfr_manager",))
    _account("audit-m1@acme.example", DEFAULT_TENANT_ID, ("icfr_manager",))
    h_other = _headers(client, "audit-t2@acme.example")
    h_default = _headers(client, "audit-m1@acme.example")

    r = client.post("/api/org/departments", headers=h_other, json={"name": f"타사-{uuid4().hex[:6]}"})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    row = _row(did)
    assert UUID(str(row.tenant_id)) == t2_id
    assert (row.created_by, row.updated_by) == (other, other)
    # 기본 테넌트 사용자에게는 보이지 않는다
    assert client.get(f"/api/org/departments/{did}", headers=h_default).status_code == 404
    client.delete(f"/api/org/departments/{did}", headers=h_other)
