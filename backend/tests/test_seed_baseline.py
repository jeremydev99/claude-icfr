"""baseline seed 검증 (ADR-0027, 2-A-2 후속).

seed 는 실 DB 를 재구축하는 경로라 공용 테스트 DB 를 쓰면 다른 테스트를 오염시킨다.
**전용 격리 엔진**을 만들어 파싱→삽입 경로만 검증한다.

건수는 하드코딩하지 않는다(엑셀 개정 시 테스트가 먼저 깨지면 안 됨). 대신 불변식을 본다:
파싱 수 == 삽입 수, 계층 FK 연결, 어서션 7종 마스터, instance 미생성, 재실행 가드.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — 모든 모델을 Base.metadata 에 등록
from app.models.base import Base
from app.models.rcm_baseline import (
    BaselineControl, BaselineControlAssertion, BaselineProcess,
    BaselineRisk, BaselineRiskCategory, BaselineSubProcess,
    ControlInstance, ProcessInstance, RiskInstance,
    SubProcessInstance, ControlAssertionInstance,
)
from seeds.seed_baseline import (
    ASSERTION_MASTER, EXCEL_PATH, _assert_baseline_empty, _load_excel, _seed,
)

pytestmark = pytest.mark.skipif(
    not EXCEL_PATH.exists(), reason=f"원천 엑셀 없음: {EXCEL_PATH}"
)


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    """격리 sqlite 에 엑셀을 시드하고 (session, parsed) 반환."""
    db_path = tmp_path_factory.mktemp("seed") / "seed.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    parsed = _load_excel()
    _seed(db, parsed)
    db.commit()
    try:
        yield db, parsed
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_parse_produces_rows():
    """다중 헤더행 보정이 동작해 데이터가 파싱된다 (보정 없으면 0건)."""
    parsed = _load_excel()
    assert parsed.errors == []
    assert len(parsed.controls) > 0
    assert len(parsed.processes) > 0
    assert len(parsed.risks) > 0
    # 통제활동번호는 4단계 계층 코드, 위험번호는 그 앞 3단계
    for c in parsed.controls:
        assert c["code"], "통제 코드 비어 있음"
        assert c["risk_code"] in parsed.risks


def test_seed_counts_match_parse(seeded):
    """삽입 건수가 파싱 건수와 정확히 일치한다."""
    db, parsed = seeded
    assert db.query(BaselineProcess).count() == len(parsed.processes)
    assert db.query(BaselineSubProcess).count() == len(parsed.sub_processes)
    assert db.query(BaselineRisk).count() == len(parsed.risks)
    assert db.query(BaselineControl).count() == len(parsed.controls)
    assert db.query(BaselineControlAssertion).count() == sum(
        len(c["assertions"]) for c in parsed.controls
    )


def test_assertion_master_is_unique_seven(seeded):
    """어서션은 통제마다 반복 등장하지만 마스터는 유니크 7종만 삽입된다."""
    db, _ = seeded
    rows = db.query(BaselineRiskCategory).all()
    assert len(rows) == len(ASSERTION_MASTER) == 7
    assert {r.code for r in rows} == {code for code, _ in ASSERTION_MASTER}


def test_hierarchy_fk_chain_resolves(seeded):
    """controls → risks → sub_processes → processes FK 가 전부 연결된다."""
    db, parsed = seeded
    for c in db.query(BaselineControl).all():
        assert c.risk_id is not None, f"{c.code}: risk_id 미연결"
        risk = db.get(BaselineRisk, c.risk_id)
        assert risk is not None
        sp = db.get(BaselineSubProcess, risk.sub_process_id)
        assert sp is not None
        assert db.get(BaselineProcess, sp.process_id) is not None

    # 코드 매핑이 엑셀 계층과 일치하는지 (샘플 아닌 전수)
    by_code = {r.code: r for r in db.query(BaselineRisk).all()}
    ctrl_by_code = {c.code: c for c in db.query(BaselineControl).all()}
    for c in parsed.controls:
        assert ctrl_by_code[c["code"]].risk_id == by_code[c["risk_code"]].id


def test_assertion_links_match_excel(seeded):
    """통제별 어서션 연결이 엑셀 플래그와 일치한다."""
    db, parsed = seeded
    rc_code = {r.id: r.code for r in db.query(BaselineRiskCategory).all()}
    linked: dict = {}
    for a in db.query(BaselineControlAssertion).all():
        linked.setdefault(a.baseline_control_id, set()).add(rc_code[a.baseline_risk_category_id])

    ctrl_by_code = {c.code: c for c in db.query(BaselineControl).all()}
    for c in parsed.controls:
        got = linked.get(ctrl_by_code[c["code"]].id, set())
        assert got == set(c["assertions"]), f"{c['code']}: 어서션 불일치 {got} != {c['assertions']}"


def test_baseline_version_defaults_to_one(seeded):
    """baseline_version 은 개정 회차 1 로 시작한다."""
    db, _ = seeded
    assert {c.baseline_version for c in db.query(BaselineControl).all()} == {1}
    assert {p.baseline_version for p in db.query(BaselineProcess).all()} == {1}


def test_no_instances_created(seeded):
    """instance 는 만들지 않는다 (암묵 adopt)."""
    db, _ = seeded
    for model in (
        ProcessInstance, SubProcessInstance, RiskInstance,
        ControlInstance, ControlAssertionInstance,
    ):
        assert db.query(model).count() == 0, f"{model.__tablename__} 가 생성됨"


def test_rerun_guard_blocks_second_seed(seeded):
    """데이터가 있으면 재실행은 중단된다 (덮어쓰기 옵션 없음)."""
    db, _ = seeded
    with pytest.raises(SystemExit):
        _assert_baseline_empty(db)
