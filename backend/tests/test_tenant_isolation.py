"""baseline 테넌트 격리 검증 (ADR-0030).

**이 파일이 존재하는 이유** — 격리는 코드에 흔적이 남지 않는다. `control_resolver.py` 어디에도
`tenant_id` 필터가 없고, ADR-0025 의 `with_loader_criteria` 이벤트가 뒤에서 건다. 즉 격리가
깨져도 diff 에는 아무것도 안 보인다. 그래서 여기서 계약으로 고정한다.

sqlite 에서 유효한 것과 아닌 것을 구분해 둔다.

- **ORM 이벤트 레벨**(자동 필터·자동 stamp) — sqlite 에서 그대로 유효하다. 아래 대부분.
- **DB 제약 레벨**(복합 FK 로 교차 테넌트 참조 거부, ADR-0030 §2.3) — **sqlite 는 FK 를
  강제하지 않는다**(`PRAGMA foreign_keys` 미설정). 그래서 그 검증은 여기서 할 수 없고
  postgres 에서만 성립한다. 아래 `test_cross_tenant_reference_is_not_guarded_by_sqlite` 가
  그 사실 자체를 고정한다 — "로컬에서 통과했으니 안전하다"는 오해를 막기 위해서다.
"""
import pytest

from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.rcm_baseline import (
    ACTION_ADD,
    ACTION_EXCLUDE,
    BaselineControl,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
    ControlInstance,
)
from app.models.tenant import Tenant
from app.services.control_resolver import resolve_controls, resolve_processes
from tests.conftest import TestingSessionLocal, engine

_ADD_ATTRS = {   # add 는 baseline 이 없으므로 자체 필드를 채운다 (models 규약, 13.5 교훈)
    "is_key_control": True, "preventive_detective": "P", "auto_manual": "M",
    "frequency": "A", "ipe_relevant": "N/A",
    "activity_approval": False, "activity_verification": False, "activity_physical": False,
    "activity_master_data": False, "activity_reconciliation": False, "activity_supervision": False,
}


def _tenant(db, code: str, name: str):
    t = db.query(Tenant).filter(Tenant.code == code).first()
    if not t:
        t = Tenant(name=name, code=code, is_active=True)
        db.add(t)
        db.commit()
    return t


def _chain(db, suffix: str):
    """baseline 4단 체인. 활성 tenant 가 걸린 상태에서 호출할 것 — before_flush 가 stamp 한다."""
    p = BaselineProcess(code=f"TI{suffix}-P", name="P")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"TI{suffix}-SP", name="SP", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"TI{suffix}-R", description="R", assessment_level="LR", sub_process_id=sp.id)
    db.add(r)
    db.flush()
    c = BaselineControl(code=f"TI{suffix}-C", name="C", risk_id=r.id)
    db.add(c)
    db.commit()
    return p, sp, r, c


# ── ADR-0030 §4-5: resolver 는 자기 테넌트 것만 반환한다 ──────────────

def test_resolver_returns_only_own_tenant_baseline(app):
    """두 테넌트가 각각 baseline 을 가질 때, resolver 조회가 자기 것만 반환한다.

    ADR-0030 의 실질 목적이 이것이다 — 전환 전에는 A 사 화면에 B 사 통제가 나온다.
    """
    db = TestingSessionLocal()
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        _chain(db, "A")
        reset_active_tenant(tok)

        b = _tenant(db, "TENANT_ISO_B", "회사B-격리")
        tok = set_active_tenant(b.id)
        _chain(db, "B")
        reset_active_tenant(tok)

        tok = set_active_tenant(DEFAULT_TENANT_ID)
        codes_a = {c["code"] for c in resolve_controls(db)}
        procs_a = {p["code"] for p in resolve_processes(db)}
        reset_active_tenant(tok)

        tok = set_active_tenant(b.id)
        codes_b = {c["code"] for c in resolve_controls(db)}
        procs_b = {p["code"] for p in resolve_processes(db)}
        reset_active_tenant(tok)

        assert "TIA-C" in codes_a and "TIB-C" not in codes_a
        assert "TIB-C" in codes_b and "TIA-C" not in codes_b
        assert "TIA-P" in procs_a and "TIB-P" not in procs_a
        assert "TIB-P" in procs_b and "TIA-P" not in procs_b
    finally:
        set_active_tenant(None)
        db.close()


def test_same_code_allowed_across_tenants(app):
    """ADR-0030 §4-3 — 두 회사가 **같은 code** 로 baseline 을 가질 수 있다.

    전환 전에는 code 유니크가 전역이라 여기서 IntegrityError 가 났다. 이것이 곧
    "두 번째 테넌트가 온보딩되지 않는다"의 실체다.
    """
    db = TestingSessionLocal()
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        a = BaselineControl(code="TI-SAME", name="A사 통제")
        db.add(a)
        db.commit()
        a_id = a.id
        reset_active_tenant(tok)

        t_b = _tenant(db, "TENANT_ISO_SAME", "회사B-동일코드")
        tok = set_active_tenant(t_b.id)
        b = BaselineControl(code="TI-SAME", name="B사 통제")
        db.add(b)
        db.commit()
        assert b.id != a_id
        reset_active_tenant(tok)

        # 각자 자기 것만 본다 — 같은 code 라도 섞이지 않는다
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        rows = [c for c in resolve_controls(db) if c["code"] == "TI-SAME"]
        assert len(rows) == 1 and rows[0]["name"] == "A사 통제"
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


def test_tenant_id_is_stamped_automatically(app):
    """baseline 행에 tenant_id 를 수동 지정하지 않는다 — before_flush 가 stamp 한다(ADR-0025).

    수동 지정 경로가 생기면 한 곳만 빠뜨려도 누출이므로, 자동 stamp 가 실제로 동작하는지 본다.
    """
    db = TestingSessionLocal()
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        c = BaselineControl(code="TI-STAMP", name="stamp 검증")   # tenant_id 미지정
        db.add(c)
        db.commit()
        assert c.tenant_id == DEFAULT_TENANT_ID
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


def test_other_tenant_exclusion_does_not_leak(app):
    """B 사의 exclude 결정이 A 사 조회에 영향을 주지 않는다 (overlay 격리)."""
    db = TestingSessionLocal()
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        a = BaselineControl(code="TI-LEAK", name="A사 통제")
        db.add(a)
        db.commit()
        reset_active_tenant(tok)

        t_b = _tenant(db, "TENANT_ISO_LEAK", "회사B-누출")
        tok = set_active_tenant(t_b.id)
        b = BaselineControl(code="TI-LEAK", name="B사 통제")
        db.add(b)
        db.commit()
        db.add_all([
            ControlInstance(baseline_control_id=b.id, action=ACTION_EXCLUDE),
            ControlInstance(baseline_control_id=None, action=ACTION_ADD,
                            code="TI-LEAK-ADD", name="B사 신규", **_ADD_ATTRS),
        ])
        db.commit()
        codes_b = {c["code"] for c in resolve_controls(db)}
        assert "TI-LEAK" not in codes_b and "TI-LEAK-ADD" in codes_b
        reset_active_tenant(tok)

        tok = set_active_tenant(DEFAULT_TENANT_ID)
        codes_a = {c["code"] for c in resolve_controls(db)}
        assert "TI-LEAK" in codes_a          # B 의 exclude 가 전파되지 않는다
        assert "TI-LEAK-ADD" not in codes_a  # B 의 add 도 보이지 않는다
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


# ── sqlite 의 한계를 사실로 고정한다 ────────────────────────────────

def test_composite_fk_is_declared_on_models():
    """복합 FK 8개가 모델에 선언돼 있다 (ADR-0030 §2.3).

    sqlite 가 FK 를 강제하지 않으므로 **거부 동작 자체는 여기서 검증할 수 없다.**
    선언 여부만이라도 고정해 두면, 누군가 단순 FK 로 되돌렸을 때 이 테스트가 깨진다.
    실제 거부는 postgres 에서 확인한다(ADR-0030 §4-4, 운영 적용 절차 §6.4).
    """
    from app.models.rcm_baseline import (
        ControlAssertionInstance,
        ProcessInstance,
        RiskInstance,
        SubProcessInstance,
    )

    expected = {
        ProcessInstance: 1,
        SubProcessInstance: 2,
        RiskInstance: 2,
        ControlInstance: 2,
        ControlAssertionInstance: 1,
    }
    for model, count in expected.items():
        composite = [
            fk for fk in model.__table__.foreign_key_constraints
            if "tenant_id" in {c.name for c in fk.columns} and len(fk.columns) == 2
        ]
        assert len(composite) == count, f"{model.__tablename__}: 복합 FK {len(composite)}개 (기대 {count})"
        for fk in composite:
            refs = {e.target_fullname for e in fk.elements}
            assert any(r.endswith(".tenant_id") for r in refs), fk.name


def test_cross_tenant_reference_is_not_guarded_by_sqlite(app):
    """**sqlite 는 FK 를 강제하지 않는다** — 이 사실을 테스트로 남긴다.

    로컬 스위트가 전부 통과해도 §2.3 격리가 검증된 것이 아니다. 누군가 이 프로젝트의
    로컬 통과를 근거로 "격리 확인됨"이라고 판단하는 것을 막기 위한 표식이다.
    postgres 에서는 fk_control_instances_baseline_tenant 가 아래 삽입을 거부한다.
    """
    with engine.connect() as conn:
        enforced = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
    assert enforced == 0, (
        "sqlite FK 강제가 켜졌다. 이 테스트의 전제가 바뀌었으니 교차 테넌트 거부를 "
        "여기서 직접 검증하도록 바꿀 것."
    )


@pytest.mark.skip(reason="postgres 전용 — sqlite 는 FK 미강제(위 테스트 참조). ADR-0030 §6.4 에서 수동 확인")
def test_cross_tenant_reference_rejected_postgres():
    """A 테넌트 baseline 을 B 테넌트 instance 가 참조 → DB 가 거부 (ADR-0030 §4-4).

    2026-09-01 로컬 postgres 실측 결과(에러 원문):
        ERROR: insert or update on table "control_instances" violates foreign key
        constraint "fk_control_instances_baseline_tenant"
    """
