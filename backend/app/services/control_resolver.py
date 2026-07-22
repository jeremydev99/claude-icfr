"""RCM baseline/instance 병합 (ADR-0027, 2-A-1 → 2-B-4 확장).

resolve_controls 가 "모든 회사의 통제 = 표준(baseline) ± 회사결정(instance)" 을 계산하는
단일 지점. 후속 단계(2-A-3)에서 모든 RCM 조회 API 가 이 함수를 거친다.

tenant 는 인자로 받지 않는다 — ADR-0025 자동 격리(활성 tenant ContextVar)가
instance 조회를 이미 필터하며, 수동 tenant 필터는 금지(한 곳만 빠뜨려도 누출).
baseline 은 전역(IdentityBase)이라 격리 대상이 아님.

── 2-B-4 확장 ────────────────────────────────────────────────────────────
1. 상위 계층 resolve: resolve_processes / resolve_sub_processes / resolve_risks.
2. 정체성 id 규칙 계층 통일 — resolved 항목 id·상위 참조 id 는 "정체성 id":
   <상위>_instance_id 있으면 그것(add 상위), 없고 <상위>_baseline_id 있으면 그것,
   둘 다 NULL 이면 baseline 항목의 원래 상위 id. (models/rcm_baseline.py 이중 FK 규약)
3. source envelope — 전 계층 공통 메타 4필드(id/source/baseline_id/is_overridden).
   프론트가 단일 라우팅으로 편집·삭제 대상(baseline vs instance)을 판별. (2-A-4 기반)
     · adopt    → source=baseline, baseline_id=그 id, is_overridden=False
     · override → source=baseline, baseline_id=그 id, is_overridden=True
     · add      → source=tenant,   baseline_id=None,  is_overridden=False
   어서션은 코드 배열이라 항목 단위 편집 대상이 아님 → envelope 미적용.
4. cascade — 상위 exclude 시 하위 자동 제외(instance 행 안 만듦). process→sub→risk→control.
   단, control 의 risk_id 가 NULL 이면 제외하지 않는다(이관 전 risk 없는 통제 존재 가능);
   risk_id 가 있는데 그 risk 가 죽었을 때만 제외.
5. 어서션 병합: 통제별 = baseline_control_assertions − remove + add (정체성 id 매칭).
6. 관계 필드: resolved risk/sub_process/process 를 정체성 id lookup 체인으로 채움
   (조인 아닌 메모리 lookup) — api/rcm.py 의 selectinload 조인과 동일 결과.
"""
from sqlalchemy.orm import Session

from app.models.rcm_baseline import (
    BaselineProcess, ProcessInstance,
    BaselineSubProcess, SubProcessInstance,
    BaselineRisk, RiskInstance,
    BaselineControl, ControlInstance,
    BaselineRiskCategory,
    BaselineControlAssertion, ControlAssertionInstance,
)

# Control 응답과 동일한 형태를 만들기 위한 응답 키 (기존 ControlBase 와 1:1).
CONTROL_FIELDS = [
    "code", "name", "description", "risk_id",
    "objective", "owner_name",
    "is_key_control", "preventive_detective", "auto_manual",
    "activity_approval", "activity_verification", "activity_physical",
    "activity_master_data", "activity_reconciliation", "activity_supervision",
    "related_accounts", "frequency", "ipe_relevant", "related_systems", "euc_description",
]

# 계층별 미러링(병합) 필드 — override 시 non-NULL 이면 baseline 을 덮는다.
_PROCESS_FIELDS = ["code", "name", "description"]
_SUB_PROCESS_FIELDS = ["code", "name"]
_RISK_FIELDS = ["code", "description", "assessment_level"]
# risk_id 는 instance 에 없고 이중 FK(risk_baseline_id/risk_instance_id)로 표현되므로
# 미러링 대상에서 빼고 상위 참조 규칙(_parent_id)으로 별도 resolve.
_CONTROL_MERGE_FIELDS = [f for f in CONTROL_FIELDS if f != "risk_id"]


def _resolve_layer(db, baseline_model, instance_model, fields, baseline_fk_attr):
    """한 계층의 baseline − exclude + override(non-NULL 병합) + add 를 계산하는 공통 함수.

    반환: [(row, base, inst), ...]
    - row: fields 병합 결과 + source envelope(id/source/baseline_id/is_overridden)
    - base: baseline 객체(add 행이면 None) — 호출측이 상위 참조 resolve 에 사용
    - inst: instance 객체(순수 baseline 이면 None)
    상위 참조·관계 필드는 계층별 공개 함수가 base/inst 로 보강한다.
    """
    baselines = (
        db.query(baseline_model)
        .filter(baseline_model.is_deleted == False)  # noqa: E712
        .all()
    )
    instances = (
        db.query(instance_model)
        .filter(instance_model.is_deleted == False)  # noqa: E712
        .all()
    )  # 활성 tenant 자동 필터 (tenant_context)

    by_baseline_id = {
        getattr(inst, baseline_fk_attr): inst
        for inst in instances
        if getattr(inst, baseline_fk_attr) is not None
    }

    triples = []
    for base in baselines:
        inst = by_baseline_id.get(base.id)
        if inst is not None and inst.action == "exclude":
            continue
        overridden = inst is not None and inst.action == "override"
        row = {f: getattr(base, f) for f in fields}
        if overridden:
            for f in fields:
                value = getattr(inst, f)
                if value is not None:  # NULL=baseline 따름 (False 는 유효한 override)
                    row[f] = value
        row["id"] = base.id
        row["source"] = "baseline"
        row["baseline_id"] = base.id
        row["is_overridden"] = overridden
        triples.append((row, base, inst))

    for inst in instances:
        if getattr(inst, baseline_fk_attr) is None and inst.action == "add":
            row = {f: getattr(inst, f) for f in fields}
            row["id"] = inst.id
            row["source"] = "tenant"
            row["baseline_id"] = None
            row["is_overridden"] = False
            triples.append((row, None, inst))

    return triples


def _parent_id(base, inst, base_parent_attr, inst_baseline_attr, inst_instance_attr):
    """상위 참조의 정체성 id 를 결정한다 (1절 규칙).

    - instance 가 add 한 상위 밑(<상위>_instance_id) → 그 instance id
    - baseline 상위 밑(<상위>_baseline_id, override 상위 포함) → 그 baseline id
    - 둘 다 NULL(baseline 상위 그대로 따름) → baseline 항목의 원래 상위 FK
    - add 행(base=None)이면 baseline FK 가 없으므로 instance 참조만 사용
    """
    if inst is not None:
        if getattr(inst, inst_instance_attr) is not None:
            return getattr(inst, inst_instance_attr)
        if getattr(inst, inst_baseline_attr) is not None:
            return getattr(inst, inst_baseline_attr)
    if base is not None:
        return getattr(base, base_parent_attr)
    return None


def resolve_processes(db: Session) -> list[dict]:
    """활성 tenant 의 최종 프로세스 목록 (최상위 계층 — 상위 참조 없음)."""
    return [row for row, _base, _inst in _resolve_layer(
        db, BaselineProcess, ProcessInstance, _PROCESS_FIELDS, "baseline_process_id"
    )]


def resolve_sub_processes(db: Session) -> list[dict]:
    """활성 tenant 의 최종 하위프로세스 목록. process_id = 상위 정체성 id."""
    result = []
    for row, base, inst in _resolve_layer(
        db, BaselineSubProcess, SubProcessInstance, _SUB_PROCESS_FIELDS, "baseline_sub_process_id"
    ):
        row["process_id"] = _parent_id(
            base, inst, "process_id", "process_baseline_id", "process_instance_id"
        )
        result.append(row)
    return result


def resolve_risks(db: Session) -> list[dict]:
    """활성 tenant 의 최종 위험 목록. sub_process_id = 상위 정체성 id."""
    result = []
    for row, base, inst in _resolve_layer(
        db, BaselineRisk, RiskInstance, _RISK_FIELDS, "baseline_risk_id"
    ):
        row["sub_process_id"] = _parent_id(
            base, inst, "sub_process_id", "sub_process_baseline_id", "sub_process_instance_id"
        )
        result.append(row)
    return result


def _resolve_assertions(db: Session) -> dict:
    """통제 정체성 id → 어서션 코드 배열. baseline 연결 − remove + add.

    - baseline_control_assertions: 전역 표준 연결 (통제 = baseline id)
    - control_assertion_instances: 회사 결정(add/remove). control_instance_id 있으면 그 정체성,
      없으면 control_baseline_id. (활성 tenant 자동 필터)
    """
    baseline_links = (
        db.query(BaselineControlAssertion)
        .filter(BaselineControlAssertion.is_deleted == False)  # noqa: E712
        .all()
    )
    instances = (
        db.query(ControlAssertionInstance)
        .filter(ControlAssertionInstance.is_deleted == False)  # noqa: E712
        .all()
    )

    cat_ids = (
        {l.baseline_risk_category_id for l in baseline_links}
        | {i.baseline_risk_category_id for i in instances}
    )
    code_by_cat = {}
    if cat_ids:
        for cat in db.query(BaselineRiskCategory).filter(
            BaselineRiskCategory.id.in_(cat_ids)
        ).all():
            code_by_cat[cat.id] = cat.code

    by_control: dict = {}
    for link in baseline_links:
        by_control.setdefault(link.baseline_control_id, set()).add(link.baseline_risk_category_id)
    for inst in instances:
        control_id = inst.control_instance_id if inst.control_instance_id is not None else inst.control_baseline_id
        cats = by_control.setdefault(control_id, set())
        if inst.action == "add":
            cats.add(inst.baseline_risk_category_id)
        elif inst.action == "remove":
            cats.discard(inst.baseline_risk_category_id)

    return {
        control_id: sorted(code_by_cat[c] for c in cats if c in code_by_cat)
        for control_id, cats in by_control.items()
    }


def resolve_controls(db: Session) -> list[dict]:
    """활성 tenant 의 최종 통제 목록 = baseline − exclude + override병합 + add.

    cascade(상위 계층) + 관계 필드(process_code/sub_process_code/risk_level/assertions)까지
    채운 완성 형태. 반환 dict 는 기존 Control 응답(ControlSearchOut) 키 구성 + source envelope:
    CONTROL_FIELDS + id/created_at/updated_at + source/baseline_id/is_overridden
    + risk_level/sub_process_code/process_code/assertions.

    - baseline 유래 행(adopt/override)의 id 는 baseline id — 통제의 정체성은 표준 쪽.
    - add 행의 id 는 instance id.
    """
    processes = resolve_processes(db)
    sub_processes = resolve_sub_processes(db)
    risks = resolve_risks(db)

    proc_by_id = {p["id"]: p for p in processes}
    sub_by_id = {s["id"]: s for s in sub_processes}
    risk_by_id = {r["id"]: r for r in risks}

    # cascade — 상위가 살아있는(=exclude/전파 제외되지 않은) 것만 alive.
    alive_processes = set(proc_by_id)
    alive_sub = {s["id"] for s in sub_processes if s["process_id"] in alive_processes}
    alive_risks = {r["id"] for r in risks if r["sub_process_id"] in alive_sub}

    assertions_by_control = _resolve_assertions(db)

    result: list[dict] = []
    for row, base, inst in _resolve_layer(
        db, BaselineControl, ControlInstance, _CONTROL_MERGE_FIELDS, "baseline_control_id"
    ):
        # 2-B-2 부채 정리 — 상위(risk) 정체성 id 규칙으로 resolve
        risk_id = _parent_id(base, inst, "risk_id", "risk_baseline_id", "risk_instance_id")
        row["risk_id"] = risk_id

        # cascade: risk 가 있는데 죽었으면 제외. risk_id NULL 은 유지(이관 전 통제).
        if risk_id is not None and risk_id not in alive_risks:
            continue

        src = base if base is not None else inst
        row["created_at"] = src.created_at
        row["updated_at"] = src.updated_at

        # 관계 필드 — 정체성 id lookup 체인 (상위 없거나 못 찾으면 None)
        risk = risk_by_id.get(risk_id)
        row["risk_level"] = risk["assessment_level"] if risk else None
        sub = sub_by_id.get(risk["sub_process_id"]) if risk else None
        row["sub_process_code"] = sub["code"] if sub else None
        proc = proc_by_id.get(sub["process_id"]) if sub else None
        row["process_code"] = proc["code"] if proc else None
        row["assertions"] = assertions_by_control.get(row["id"], [])

        result.append(row)

    result.sort(key=lambda r: r["code"] or "")
    return result
