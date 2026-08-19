"""RCM baseline/instance 병합 테스트 (ADR-0027, 2-A-1 + 2-B-1 + 2-B-2).

resolve_controls 의 4 action(adopt/exclude/override/add) + 혼합 case + tenant 격리 검증.
서비스 레벨 직접 검증 (API 전환은 2-A-3).
2-B-1: baseline 상위 계층 FK 체인 조인 + 전역성(tenant 컨텍스트 무관) 검증.
2-B-2: instance 상위 계층 — 4 action 데이터 규칙, 이중 FK check, 상위 참조, tenant 격리."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineControlAssertion,
    BaselineProcess,
    BaselineRisk,
    BaselineRiskCategory,
    BaselineSubProcess,
    ControlAssertionInstance,
    ControlInstance,
    ProcessInstance,
    RiskInstance,
    SubProcessInstance,
)
from app.models.tenant import Tenant
from app.services.control_resolver import (
    CONTROL_FIELDS,
    resolve_controls,
    resolve_processes,
    resolve_risks,
    resolve_sub_processes,
)
from tests.conftest import TestingSessionLocal

# ControlInstance 규약(models/rcm_baseline.py): add 는 baseline 이 없으므로 **자체 필드를 전부 채운다**.
# 비워두면 resolver 가 None 을 그대로 내보내 ControlSearchOut/ControlRead 검증이 깨진다
# (adopt/override 는 baseline 이 NOT NULL 이라 문제가 없고, add 만 해당).
# 값은 API 경로가 실제로 만드는 형태 = ControlBase 기본값과 동일하게 둔다.
_ADD_ACTIVITIES = {
    "activity_approval": False,
    "activity_verification": False,
    "activity_physical": False,
    "activity_master_data": False,
    "activity_reconciliation": False,
    "activity_supervision": False,
}
_ADD_ATTRS = {
    "is_key_control": True,
    "preventive_detective": "P",
    "auto_manual": "M",
    "frequency": "A",
    "ipe_relevant": "N/A",
}


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
        # 응답 형태 = 기존 Control 응답 + source envelope + 관계 필드 (2-B-4)
        expected = set(CONTROL_FIELDS) | {
            "id", "created_at", "updated_at",
            "source", "baseline_id", "is_overridden",
            "risk_level", "sub_process_code", "process_code", "assertions",
        }
        assert expected == set(rows["BL-ADOPT-1"].keys())
        # adopt → source envelope
        assert rows["BL-ADOPT-1"]["source"] == "baseline"
        assert rows["BL-ADOPT-1"]["baseline_id"] == b1.id
        assert rows["BL-ADOPT-1"]["is_overridden"] is False
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
            **_ADD_ACTIVITIES,
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
            ControlInstance(baseline_control_id=None, action="add", code="CI-MIX-ADD", name="추가 통제",
                            **_ADD_ACTIVITIES, **_ADD_ATTRS),
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
            ControlInstance(baseline_control_id=None, action="add", code="CI-ISO-B", name="B사 통제",
                            **_ADD_ACTIVITIES, **_ADD_ATTRS),
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


# ── 2-B-1: baseline 상위 계층 ──────────────────────────────────────────


def _make_baseline_chain(db, suffix):
    """baseline_processes→sub_processes→risks→controls 4단 체인 생성."""
    p = BaselineProcess(code=f"BP-{suffix}", name="표준 프로세스")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"BSP-{suffix}", name="표준 하위프로세스", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"BR-{suffix}", description="표준 위험", sub_process_id=sp.id)
    db.add(r)
    db.flush()
    c = BaselineControl(code=f"BC-{suffix}", name="표준 통제", risk_id=r.id)
    db.add(c)
    db.commit()
    return p, sp, r, c


def test_baseline_fk_chain_join(app):
    """baseline_control → risk → sub_process → process 관계 경로로 code 를 조회한다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, c = _make_baseline_chain(db, "CHAIN1")

        found = db.query(BaselineControl).filter(BaselineControl.code == "BC-CHAIN1").one()
        assert found.risk.code == "BR-CHAIN1"
        assert found.risk.sub_process.code == "BSP-CHAIN1"
        assert found.risk.sub_process.process.code == "BP-CHAIN1"

        # 조인 쿼리로도 같은 체인이 성립 (2-A-3 검색 필터가 쓸 경로)
        row = (
            db.query(BaselineControl.code, BaselineProcess.code)
            .join(BaselineRisk, BaselineControl.risk_id == BaselineRisk.id)
            .join(BaselineSubProcess, BaselineRisk.sub_process_id == BaselineSubProcess.id)
            .join(BaselineProcess, BaselineSubProcess.process_id == BaselineProcess.id)
            .filter(BaselineControl.code == "BC-CHAIN1")
            .one()
        )
        assert row == ("BC-CHAIN1", "BP-CHAIN1")
    finally:
        reset_active_tenant(tok)
        db.close()


def test_baseline_hierarchy_is_global(app):
    """baseline 계층은 전역 — tenant 컨텍스트가 무엇이든(없든) 동일하게 조회된다."""
    db = TestingSessionLocal()
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        _make_baseline_chain(db, "GLOB1")
        reset_active_tenant(tok)

        tenant_b = db.query(Tenant).filter(Tenant.code == "TENANT_BL_G").first()
        if not tenant_b:
            tenant_b = Tenant(name="회사B-global", code="TENANT_BL_G", is_active=True)
            db.add(tenant_b)
            db.commit()

        # 다른 tenant 컨텍스트에서도 체인 전체가 보인다
        tok = set_active_tenant(tenant_b.id)
        assert db.query(BaselineProcess).filter(BaselineProcess.code == "BP-GLOB1").count() == 1
        assert db.query(BaselineSubProcess).filter(BaselineSubProcess.code == "BSP-GLOB1").count() == 1
        assert db.query(BaselineRisk).filter(BaselineRisk.code == "BR-GLOB1").count() == 1
        assert db.query(BaselineControl).filter(BaselineControl.code == "BC-GLOB1").count() == 1
        reset_active_tenant(tok)

        # tenant 컨텍스트가 아예 없어도 조회된다
        assert db.query(BaselineRisk).filter(BaselineRisk.code == "BR-GLOB1").count() == 1
    finally:
        set_active_tenant(None)
        db.close()


# ── 2-B-2: instance 상위 계층 ──────────────────────────────────────────


def test_instance_four_actions_per_layer(app):
    """3개 instance 계층 각각에서 4 action 데이터 규칙대로 행이 생성된다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, _ = _make_baseline_chain(db, "ACT1")
        p2, sp2, r2, _ = _make_baseline_chain(db, "ACT2")
        p3, sp3, r3, _ = _make_baseline_chain(db, "ACT3")

        db.add_all([
            # process 계층: adopt / exclude / override / add
            ProcessInstance(baseline_process_id=p.id, action="adopt"),
            ProcessInstance(baseline_process_id=p2.id, action="exclude"),
            ProcessInstance(baseline_process_id=p3.id, action="override", name="회사별 프로세스명"),
            ProcessInstance(baseline_process_id=None, action="add", code="PI-ADD-1", name="회사 고유 프로세스"),
            # sub_process 계층
            SubProcessInstance(baseline_sub_process_id=sp.id, action="adopt"),
            SubProcessInstance(baseline_sub_process_id=sp2.id, action="exclude"),
            SubProcessInstance(baseline_sub_process_id=sp3.id, action="override", name="회사별 하위명"),
            # risk 계층
            RiskInstance(baseline_risk_id=r.id, action="adopt"),
            RiskInstance(baseline_risk_id=r2.id, action="exclude"),
            RiskInstance(baseline_risk_id=r3.id, action="override", assessment_level="HR"),
        ])
        db.commit()

        assert db.query(ProcessInstance).filter(ProcessInstance.code == "PI-ADD-1").one().action == "add"
        ovr = db.query(ProcessInstance).filter(ProcessInstance.baseline_process_id == p3.id).one()
        assert ovr.name == "회사별 프로세스명" and ovr.code is None  # 변경 필드만 값
        assert db.query(RiskInstance).filter(RiskInstance.baseline_risk_id == r3.id).one().assessment_level == "HR"
    finally:
        reset_active_tenant(tok)
        db.close()


def test_instance_parent_refs(app):
    """baseline 상위 참조와 instance 상위 참조가 각각 정상 동작한다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, _ = _make_baseline_chain(db, "PREF1")

        # add sub_process — baseline 상위(process) 밑
        sp_under_baseline = SubProcessInstance(
            action="add", code="SPI-B-1", name="baseline 상위 밑 추가",
            process_baseline_id=p.id,
        )
        # add process → 그 밑에 add sub_process (instance 상위)
        pi = ProcessInstance(baseline_process_id=None, action="add", code="PI-PREF-1", name="회사 프로세스")
        db.add_all([sp_under_baseline, pi])
        db.flush()
        sp_under_instance = SubProcessInstance(
            action="add", code="SPI-I-1", name="instance 상위 밑 추가",
            process_instance_id=pi.id,
        )
        db.add(sp_under_instance)
        db.flush()
        # risk 계층도 동일 — instance 상위(sub_process) 밑 + control 의 이중 FK
        ri = RiskInstance(
            action="add", code="RI-I-1", description="회사 위험",
            sub_process_instance_id=sp_under_instance.id,
        )
        db.add(ri)
        db.flush()
        db.add_all([
            ControlInstance(action="add", code="CI-B-1", name="baseline risk 밑", risk_baseline_id=r.id,
                            **_ADD_ACTIVITIES, **_ADD_ATTRS),
            ControlInstance(action="add", code="CI-I-1", name="instance risk 밑", risk_instance_id=ri.id,
                            **_ADD_ACTIVITIES, **_ADD_ATTRS),
        ])
        db.commit()

        assert db.query(SubProcessInstance).filter(
            SubProcessInstance.code == "SPI-B-1").one().process_baseline_id == p.id
        assert db.query(SubProcessInstance).filter(
            SubProcessInstance.code == "SPI-I-1").one().process_instance_id == pi.id
        assert db.query(ControlInstance).filter(
            ControlInstance.code == "CI-B-1").one().risk_baseline_id == r.id
        assert db.query(ControlInstance).filter(
            ControlInstance.code == "CI-I-1").one().risk_instance_id == ri.id
    finally:
        reset_active_tenant(tok)
        db.close()


@pytest.mark.parametrize("layer", ["sub_process", "risk", "control"])
def test_instance_dual_fk_check_violation(app, layer):
    """이중 FK 를 둘 다 채우면 CheckConstraint 가 차단한다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, _ = _make_baseline_chain(db, f"CHK-{layer.upper()}")
        pi = ProcessInstance(baseline_process_id=None, action="add", code=f"PI-CHK-{layer}", name="x")
        db.add(pi)
        db.flush()
        spi = SubProcessInstance(action="add", code=f"SPI-CHK-{layer}", name="x", process_instance_id=pi.id)
        db.add(spi)
        db.flush()
        ri = RiskInstance(action="add", code=f"RI-CHK-{layer}", description="x", sub_process_instance_id=spi.id)
        db.add(ri)
        db.flush()

        if layer == "sub_process":
            bad = SubProcessInstance(
                action="add", code="SPI-BAD", name="x",
                process_baseline_id=p.id, process_instance_id=pi.id,
            )
        elif layer == "risk":
            bad = RiskInstance(
                action="add", code="RI-BAD", description="x",
                sub_process_baseline_id=sp.id, sub_process_instance_id=spi.id,
            )
        else:
            bad = ControlInstance(
                action="add", code="CI-BAD", name="x",
                risk_baseline_id=r.id, risk_instance_id=ri.id,
            )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        reset_active_tenant(tok)
        db.close()


def test_instance_hierarchy_tenant_isolation(app):
    """tenant B 의 상위 계층 instance 는 기본 tenant 조회에 보이지 않는다."""
    db = TestingSessionLocal()
    try:
        tenant_b = db.query(Tenant).filter(Tenant.code == "TENANT_HI_B").first()
        if not tenant_b:
            tenant_b = Tenant(name="회사B-hierarchy", code="TENANT_HI_B", is_active=True)
            db.add(tenant_b)
            db.commit()

        tok = set_active_tenant(tenant_b.id)
        db.add(ProcessInstance(baseline_process_id=None, action="add", code="PI-ISO-B", name="B사 프로세스"))
        db.commit()
        assert db.query(ProcessInstance).filter(ProcessInstance.code == "PI-ISO-B").count() == 1
        reset_active_tenant(tok)

        tok = set_active_tenant(DEFAULT_TENANT_ID)
        assert db.query(ProcessInstance).filter(ProcessInstance.code == "PI-ISO-B").count() == 0
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


# ── 2-B-3: 어서션 junction baseline/overlay ────────────────────────────


def _make_category(db, code, name="어서션"):
    cat = db.query(BaselineRiskCategory).filter(BaselineRiskCategory.code == code).first()
    if not cat:
        cat = BaselineRiskCategory(code=code, name=name)
        db.add(cat)
        db.commit()
    return cat


def test_assertion_baseline_junction_and_dup_block(app):
    """표준 연결이 생성되고, 같은 (통제, 어서션) 중복 연결은 unique 가 차단한다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        b = _make_baseline(db, "BL-AST-1")
        cat = _make_category(db, "AST-E")
        db.add(BaselineControlAssertion(baseline_control_id=b.id, baseline_risk_category_id=cat.id))
        db.commit()

        found = db.query(BaselineControl).filter(BaselineControl.code == "BL-AST-1").one()
        assert [a.baseline_risk_category.code for a in found.assertions] == ["AST-E"]

        db.add(BaselineControlAssertion(baseline_control_id=b.id, baseline_risk_category_id=cat.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        reset_active_tenant(tok)
        db.close()


def test_assertion_instance_add_remove(app):
    """baseline 통제에 대한 add/remove 결정 행이 각각 생성된다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        b = _make_baseline(db, "BL-AST-2")
        cat_e = _make_category(db, "AST2-E")
        cat_c = _make_category(db, "AST2-C")
        # 표준 연결: E. 회사 결정: E 를 remove, C 를 add.
        db.add_all([
            BaselineControlAssertion(baseline_control_id=b.id, baseline_risk_category_id=cat_e.id),
            ControlAssertionInstance(action="remove", control_baseline_id=b.id, baseline_risk_category_id=cat_e.id),
            ControlAssertionInstance(action="add", control_baseline_id=b.id, baseline_risk_category_id=cat_c.id),
        ])
        db.commit()

        rows = db.query(ControlAssertionInstance).filter(
            ControlAssertionInstance.control_baseline_id == b.id).all()
        assert {(r.action, r.baseline_risk_category.code) for r in rows} == {
            ("remove", "AST2-E"), ("add", "AST2-C"),
        }
    finally:
        reset_active_tenant(tok)
        db.close()


def test_assertion_instance_add_control_target(app):
    """회사가 add 한 통제(control_instance_id 참조)의 어서션 연결도 정상 생성된다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        ci = ControlInstance(action="add", code="CI-AST-1", name="회사 통제", **_ADD_ACTIVITIES, **_ADD_ATTRS)
        cat = _make_category(db, "AST3-V")
        db.add(ci)
        db.flush()
        db.add(ControlAssertionInstance(
            action="add", control_instance_id=ci.id, baseline_risk_category_id=cat.id,
        ))
        db.commit()

        row = db.query(ControlAssertionInstance).filter(
            ControlAssertionInstance.control_instance_id == ci.id).one()
        assert row.action == "add" and row.control_baseline_id is None
    finally:
        reset_active_tenant(tok)
        db.close()


def test_assertion_instance_dual_fk_check_violation(app):
    """대상 통제 이중 FK 를 둘 다 채우면 CheckConstraint 가 차단한다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        b = _make_baseline(db, "BL-AST-4")
        ci = ControlInstance(action="add", code="CI-AST-4", name="회사 통제", **_ADD_ACTIVITIES, **_ADD_ATTRS)
        cat = _make_category(db, "AST4-R")
        db.add(ci)
        db.flush()
        db.add(ControlAssertionInstance(
            action="add", control_baseline_id=b.id, control_instance_id=ci.id,
            baseline_risk_category_id=cat.id,
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        reset_active_tenant(tok)
        db.close()


def test_assertion_instance_tenant_isolation(app):
    """tenant B 의 어서션 결정은 기본 tenant 조회에 보이지 않는다 (baseline 연결은 전역)."""
    db = TestingSessionLocal()
    try:
        tenant_b = db.query(Tenant).filter(Tenant.code == "TENANT_AST_B").first()
        if not tenant_b:
            tenant_b = Tenant(name="회사B-assertion", code="TENANT_AST_B", is_active=True)
            db.add(tenant_b)
            db.commit()

        tok = set_active_tenant(DEFAULT_TENANT_ID)
        b = _make_baseline(db, "BL-AST-5")
        cat = _make_category(db, "AST5-P")
        db.add(BaselineControlAssertion(baseline_control_id=b.id, baseline_risk_category_id=cat.id))
        db.commit()
        reset_active_tenant(tok)

        # tenant B 가 표준 연결을 remove
        tok = set_active_tenant(tenant_b.id)
        db.add(ControlAssertionInstance(
            action="remove", control_baseline_id=b.id, baseline_risk_category_id=cat.id,
        ))
        db.commit()
        assert db.query(ControlAssertionInstance).filter(
            ControlAssertionInstance.control_baseline_id == b.id).count() == 1
        reset_active_tenant(tok)

        # 기본 tenant: B 의 remove 결정이 안 보이고, 전역 baseline 연결은 보인다
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        assert db.query(ControlAssertionInstance).filter(
            ControlAssertionInstance.control_baseline_id == b.id).count() == 0
        assert db.query(BaselineControlAssertion).filter(
            BaselineControlAssertion.baseline_control_id == b.id).count() == 1
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


# ── 2-B-3.5: baseline_version 컬럼 ─────────────────────────────────────


def test_baseline_version_defaults_to_one(app):
    """baseline 5테이블 행 생성 시 baseline_version 이 1 로 기본 설정된다 (현재 baseline=v1)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, c = _make_baseline_chain(db, "VER1")
        cat = _make_category(db, "VER-E")
        for obj in (p, sp, r, cat, c):
            db.refresh(obj)
            assert obj.baseline_version == 1
    finally:
        reset_active_tenant(tok)
        db.close()


def test_baseline_version_explicit(app):
    """개정 트랙 대비 — 바뀐 행만 baseline_version 을 명시적으로 올릴 수 있다 (행 단위)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p = BaselineProcess(code="BP-VER2", name="개정 프로세스", baseline_version=3)
        c = BaselineControl(code="BC-VER2", name="개정 통제", baseline_version=2)
        db.add_all([p, c])
        db.commit()
        db.refresh(p)
        db.refresh(c)
        assert p.baseline_version == 3
        assert c.baseline_version == 2
    finally:
        reset_active_tenant(tok)
        db.close()


# ── 2-B-4: resolver 계층 확장 + source envelope ────────────────────────


def _get_tenant(db, code, name):
    t = db.query(Tenant).filter(Tenant.code == code).first()
    if not t:
        t = Tenant(name=name, code=code, is_active=True)
        db.add(t)
        db.commit()
    return t


def test_resolve_upper_layers_actions(app):
    """process resolve 가 4 action(adopt/exclude/override/add) + envelope 를 반영한다."""
    db = TestingSessionLocal()
    t = _get_tenant(db, "TENANT_2B4_L", "회사-layers")
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        pa = BaselineProcess(code="B4P-A", name="채택")
        px = BaselineProcess(code="B4P-X", name="제외")
        po = BaselineProcess(code="B4P-O", name="표준명")
        db.add_all([pa, px, po])
        db.commit()
        reset_active_tenant(tok)

        tok = set_active_tenant(t.id)
        db.add_all([
            ProcessInstance(baseline_process_id=pa.id, action="adopt"),
            ProcessInstance(baseline_process_id=px.id, action="exclude"),
            ProcessInstance(baseline_process_id=po.id, action="override", name="회사명"),
            ProcessInstance(baseline_process_id=None, action="add", code="B4P-ADD", name="회사 프로세스"),
        ])
        db.commit()

        procs = {p["code"]: p for p in resolve_processes(db)}
        assert procs["B4P-A"]["is_overridden"] is False and procs["B4P-A"]["source"] == "baseline"
        assert "B4P-X" not in procs                               # exclude
        assert procs["B4P-O"]["name"] == "회사명" and procs["B4P-O"]["is_overridden"] is True
        assert procs["B4P-O"]["baseline_id"] == po.id
        assert procs["B4P-ADD"]["source"] == "tenant" and procs["B4P-ADD"]["baseline_id"] is None
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


def test_resolve_cascade_process_exclude(app):
    """process exclude → 그 아래 sub/risk/control 이 resolve 결과에서 사라진다.
    단, risk_id NULL 통제는 cascade 영향을 받지 않는다."""
    db = TestingSessionLocal()
    t = _get_tenant(db, "TENANT_2B4_C", "회사-cascade")
    try:
        tok = set_active_tenant(t.id)
        p, sp, r, c = _make_baseline_chain(db, "2B4CAS")  # BC-2B4CAS: risk_id=r
        _make_baseline(db, "BC-2B4NULL")                  # risk_id NULL
        codes_before = {x["code"] for x in resolve_controls(db)}
        assert "BC-2B4CAS" in codes_before and "BC-2B4NULL" in codes_before

        db.add(ProcessInstance(baseline_process_id=p.id, action="exclude"))
        db.commit()
        codes_after = {x["code"] for x in resolve_controls(db)}
        assert "BC-2B4CAS" not in codes_after             # cascade 전파(상위 exclude)
        assert "BC-2B4NULL" in codes_after                # risk NULL 은 유지
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


def test_resolve_add_chain_identity(app):
    """add process→sub→risk→control 체인: control.risk_id 가 add risk 의 instance id 로
    resolve(2-B-2 부채 정리) + 관계 필드가 add 체인 코드로 채워진다."""
    db = TestingSessionLocal()
    t = _get_tenant(db, "TENANT_2B4_ADD", "회사-addchain")
    try:
        tok = set_active_tenant(t.id)
        pi = ProcessInstance(baseline_process_id=None, action="add", code="B4-PI", name="회사P")
        db.add(pi)
        db.flush()
        spi = SubProcessInstance(action="add", code="B4-SPI", name="회사SP", process_instance_id=pi.id)
        db.add(spi)
        db.flush()
        ri = RiskInstance(action="add", code="B4-RI", description="회사R", assessment_level="HR",
                          sub_process_instance_id=spi.id)
        db.add(ri)
        db.flush()
        db.add(ControlInstance(action="add", code="B4-CI", name="회사C", risk_instance_id=ri.id,
                               **_ADD_ACTIVITIES, **_ADD_ATTRS))
        db.commit()

        row = {x["code"]: x for x in resolve_controls(db)}["B4-CI"]
        assert row["risk_id"] == ri.id                    # instance id 로 resolve
        assert row["risk_level"] == "HR"
        assert row["sub_process_code"] == "B4-SPI"
        assert row["process_code"] == "B4-PI"
        assert row["source"] == "tenant" and row["baseline_id"] is None
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


def test_resolve_assertions_merge(app):
    """통제별 어서션 = baseline − remove + add, 코드 배열(sorted)."""
    db = TestingSessionLocal()
    t = _get_tenant(db, "TENANT_2B4_AST", "회사-ast")
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        b = _make_baseline(db, "BC-2B4AST")   # risk NULL → cascade 통과
        ce = _make_category(db, "2B4-E")
        cc = _make_category(db, "2B4-C")
        cv = _make_category(db, "2B4-V")
        db.add_all([
            BaselineControlAssertion(baseline_control_id=b.id, baseline_risk_category_id=ce.id),
            BaselineControlAssertion(baseline_control_id=b.id, baseline_risk_category_id=cc.id),
        ])
        db.commit()
        reset_active_tenant(tok)

        # 회사: E remove, V add → {C, V}
        tok = set_active_tenant(t.id)
        db.add_all([
            ControlAssertionInstance(action="remove", control_baseline_id=b.id, baseline_risk_category_id=ce.id),
            ControlAssertionInstance(action="add", control_baseline_id=b.id, baseline_risk_category_id=cv.id),
        ])
        db.commit()
        row = {x["code"]: x for x in resolve_controls(db)}["BC-2B4AST"]
        assert row["assertions"] == ["2B4-C", "2B4-V"]
        reset_active_tenant(tok)

        # DEFAULT: 표준 그대로 {C, E}
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        row_d = {x["code"]: x for x in resolve_controls(db)}["BC-2B4AST"]
        assert row_d["assertions"] == ["2B4-C", "2B4-E"]
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


def test_resolve_relationship_fields_baseline(app):
    """baseline 체인 통제의 관계 필드(risk_level/sub_process_code/process_code)가 상위 코드로 채워진다."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        p, sp, r, c = _make_baseline_chain(db, "2B4REL")
        row = {x["code"]: x for x in resolve_controls(db)}["BC-2B4REL"]
        assert row["risk_id"] == r.id
        assert row["risk_level"] == r.assessment_level
        assert row["sub_process_code"] == "BSP-2B4REL"
        assert row["process_code"] == "BP-2B4REL"
    finally:
        reset_active_tenant(tok)
        db.close()


def test_resolve_overridden_parent_keeps_baseline_identity(app):
    """상위(sub_process) 필드 override 시에도 정체성 id 는 baseline 을 유지하고,
    하위 risk 의 상위 참조도 baseline id 를 가리킨다."""
    db = TestingSessionLocal()
    t = _get_tenant(db, "TENANT_2B4_OVR", "회사-ovr")
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        p, sp, r, c = _make_baseline_chain(db, "2B4OVR")
        reset_active_tenant(tok)

        tok = set_active_tenant(t.id)
        db.add(SubProcessInstance(baseline_sub_process_id=sp.id, action="override", name="회사 하위명"))
        db.commit()

        subs = {s["code"]: s for s in resolve_sub_processes(db)}
        assert subs["BSP-2B4OVR"]["id"] == sp.id             # 정체성 = baseline
        assert subs["BSP-2B4OVR"]["is_overridden"] is True
        assert subs["BSP-2B4OVR"]["name"] == "회사 하위명"

        risks = {rr["code"]: rr for rr in resolve_risks(db)}
        assert risks["BR-2B4OVR"]["sub_process_id"] == sp.id  # 상위 참조 = baseline id

        ctrl = {x["code"]: x for x in resolve_controls(db)}["BC-2B4OVR"]
        assert ctrl["sub_process_code"] == "BSP-2B4OVR"
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()


def test_resolve_control_source_envelope(app):
    """control envelope: adopt/override/add 각각 source/baseline_id/is_overridden 정확."""
    db = TestingSessionLocal()
    t = _get_tenant(db, "TENANT_2B4_ENV", "회사-env")
    try:
        tok = set_active_tenant(DEFAULT_TENANT_ID)
        b_ad = _make_baseline(db, "BC-2B4-AD")
        b_ov = _make_baseline(db, "BC-2B4-OV", name="표준명")
        reset_active_tenant(tok)

        tok = set_active_tenant(t.id)
        db.add_all([
            ControlInstance(baseline_control_id=b_ad.id, action="adopt"),
            ControlInstance(baseline_control_id=b_ov.id, action="override", name="회사명"),
            ControlInstance(baseline_control_id=None, action="add", code="CI-2B4-ADD", name="회사 통제",
                            **_ADD_ACTIVITIES, **_ADD_ATTRS),
        ])
        db.commit()
        rows = {x["code"]: x for x in resolve_controls(db)}
        assert rows["BC-2B4-AD"]["source"] == "baseline"
        assert rows["BC-2B4-AD"]["baseline_id"] == b_ad.id and rows["BC-2B4-AD"]["is_overridden"] is False
        assert rows["BC-2B4-OV"]["source"] == "baseline" and rows["BC-2B4-OV"]["is_overridden"] is True
        assert rows["BC-2B4-OV"]["name"] == "회사명"
        assert rows["CI-2B4-ADD"]["source"] == "tenant"
        assert rows["CI-2B4-ADD"]["baseline_id"] is None and rows["CI-2B4-ADD"]["is_overridden"] is False
        reset_active_tenant(tok)
    finally:
        set_active_tenant(None)
        db.close()
