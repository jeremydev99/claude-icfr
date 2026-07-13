"""RCM baseline/instance 병합 테스트 (ADR-0027, 2-A-1).

resolve_controls 의 4 action(adopt/exclude/override/add) + 혼합 case + tenant 격리 검증.
서비스 레벨 직접 검증 (API 전환은 2-A-3)."""
from app.models.tenant import Tenant
from app.models.rcm_baseline import BaselineControl, ControlInstance
from app.services.control_resolver import resolve_controls, CONTROL_FIELDS
from app.core.tenant_context import set_active_tenant, reset_active_tenant, DEFAULT_TENANT_ID
from tests.conftest import TestingSessionLocal


def _make_baseline(db, code, name="표준 통제", **kwargs):
    b = BaselineControl(code=code, name=name, **kwargs)
    db.add(b)
    db.commit()
    return b


def _resolve_codes(db):
    return {r["code"]: r for r in resolve_controls(db)}


def test_resolve_baseline_and_adopt(app):
    """instance 없는 baseline 과 adopt instance 는 baseline 그대로 나온다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        b1 = _make_baseline(db, "BL-ADOPT-1", owner_name="표준담당자")
        _make_baseline(db, "BL-NOINST-1")
        db.add(ControlInstance(baseline_control_id=b1.id, action="adopt"))
        db.commit()

        rows = _resolve_codes(db)
        assert "BL-ADOPT-1" in rows
        assert "BL-NOINST-1" in rows  # instance 없음 = 암묵 adopt
        assert rows["BL-ADOPT-1"]["owner_name"] == "표준담당자"
        assert rows["BL-ADOPT-1"]["id"] == b1.id
        # 응답 형태 = 기존 Control 응답과 동일한 키 구성
        assert set(CONTROL_FIELDS) | {"id", "created_at", "updated_at"} == set(rows["BL-ADOPT-1"].keys())
    finally:
        reset_active_tenant(tok)
        db.close()


def test_resolve_exclude(app):
    """exclude 된 baseline 은 결과에서 빠진다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        b = _make_baseline(db, "BL-EXCL-1")
        db.add(ControlInstance(baseline_control_id=b.id, action="exclude"))
        db.commit()

        assert "BL-EXCL-1" not in _resolve_codes(db)
    finally:
        reset_active_tenant(tok)
        db.close()


def test_resolve_override(app):
    """override 는 non-NULL 필드만 덮고 나머지는 baseline 을 따른다. False 도 유효한 override."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        b = _make_baseline(
            db, "BL-OVR-1", name="표준명", owner_name="표준담당자",
            is_key_control=True, frequency="A",
        )
        db.add(ControlInstance(
            baseline_control_id=b.id, action="override",
            name="회사별 변경명", is_key_control=False,  # 이 둘만 override
        ))
        db.commit()

        row = _resolve_codes(db)["BL-OVR-1"]
        assert row["name"] == "회사별 변경명"          # override 적용
        assert row["is_key_control"] is False          # False override 적용
        assert row["owner_name"] == "표준담당자"       # NULL → baseline 따름
        assert row["frequency"] == "A"                 # NULL → baseline 따름
    finally:
        reset_active_tenant(tok)
        db.close()


def test_resolve_add(app):
    """add instance(baseline 없음)는 자체 값으로 추가된다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        db.add(ControlInstance(
            baseline_control_id=None, action="add",
            code="CI-ADD-1", name="회사 고유 통제", is_key_control=True,
            preventive_detective="D", auto_manual="M", frequency="M", ipe_relevant="N",
        ))
        db.commit()

        row = _resolve_codes(db)["CI-ADD-1"]
        assert row["name"] == "회사 고유 통제"
        assert row["preventive_detective"] == "D"
    finally:
        reset_active_tenant(tok)
        db.close()


def test_resolve_mixed(app):
    """혼합 case: baseline 3개 중 1 exclude·1 override·1 adopt + add 1 → 최종 3개."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        b_adopt = _make_baseline(db, "BL-MIX-A")
        b_over = _make_baseline(db, "BL-MIX-O", name="표준명")
        b_excl = _make_baseline(db, "BL-MIX-X")
        db.add_all([
            ControlInstance(baseline_control_id=b_adopt.id, action="adopt"),
            ControlInstance(baseline_control_id=b_over.id, action="override", name="변경명"),
            ControlInstance(baseline_control_id=b_excl.id, action="exclude"),
            ControlInstance(baseline_control_id=None, action="add", code="CI-MIX-ADD", name="추가 통제"),
        ])
        db.commit()

        rows = _resolve_codes(db)
        mixed = {c: r for c, r in rows.items() if c.startswith(("BL-MIX", "CI-MIX"))}
        assert set(mixed.keys()) == {"BL-MIX-A", "BL-MIX-O", "CI-MIX-ADD"}
        assert mixed["BL-MIX-O"]["name"] == "변경명"
    finally:
        reset_active_tenant(tok)
        db.close()


def test_resolve_tenant_isolation(app):
    """tenant B 의 exclude/add 는 기본 tenant 의 resolve 결과에 영향이 없다."""
    db = TestingSessionLocal()
    try:
        tenant_b = db.query(Tenant).filter(Tenant.code == "TENANT_BL_B").first()
        if not tenant_b:
            tenant_b = Tenant(name="회사B-baseline", code="TENANT_BL_B", is_active=True)
            db.add(tenant_b)
            db.commit()

        tok = set_active_tenant(None)
        reset_active_tenant(tok)
        b = _make_baseline(db, "BL-ISO-1")  # baseline 은 전역 (컨텍스트 무관)

        # tenant B: exclude + 자체 add
        tok = set_active_tenant(tenant_b.id)
        db.add_all([
            ControlInstance(baseline_control_id=b.id, action="exclude"),
            ControlInstance(baseline_control_id=None, action="add", code="CI-ISO-B", name="B사 통제"),
        ])
        db.commit()
        rows_b = _resolve_codes(db)
        assert "BL-ISO-1" not in rows_b   # B 에서는 제외됨
        assert "CI-ISO-B" in rows_b
        reset_active_tenant(tok)

        # 기본 tenant: baseline 그대로 보이고 B 의 add 는 안 보임
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        rows_d = _resolve_codes(db)
        assert "BL-ISO-1" in rows_d
        assert "CI-ISO-B" not in rows_d
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()
