"""RCM baseline/instance 병합 (ADR-0027, 2-A-1).

resolve_controls 가 "모든 회사의 통제 = 표준(baseline) ± 회사결정(instance)" 을 계산하는
단일 지점. 후속 단계(2-A-3)에서 모든 RCM 조회 API 가 이 함수를 거친다.

tenant 는 인자로 받지 않는다 — ADR-0025 자동 격리(활성 tenant ContextVar)가
ControlInstance 조회를 이미 필터하며, 수동 tenant 필터는 금지(한 곳만 빠뜨려도 누출).
"""
from sqlalchemy.orm import Session

from app.models.rcm_baseline import BaselineControl, ControlInstance

# Control 응답과 동일한 형태를 만들기 위한 병합 대상 필드 (기존 ControlBase 와 1:1).
CONTROL_FIELDS = [
    "code", "name", "description", "risk_id",
    "objective", "owner_name",
    "is_key_control", "preventive_detective", "auto_manual",
    "activity_approval", "activity_verification", "activity_physical",
    "activity_master_data", "activity_reconciliation", "activity_supervision",
    "related_accounts", "frequency", "ipe_relevant", "related_systems", "euc_description",
]


def resolve_controls(db: Session) -> list[dict]:
    """활성 tenant 의 최종 통제 목록 = baseline − exclude + override병합 + add.

    반환 dict 는 기존 Control 응답(ControlRead)과 동일한 키 구성:
    CONTROL_FIELDS + id/created_at/updated_at.
    - baseline 유래 행(adopt/override)의 id 는 baseline id — 통제의 정체성은 표준 쪽.
      (override 편집 진입점을 instance id 로 바꿀지는 2-A-4 CRUD 전환에서 결정)
    - add 행의 id 는 instance id.
    """
    baselines = (
        db.query(BaselineControl)
        .filter(BaselineControl.is_deleted == False)  # noqa: E712
        .all()
    )
    instances = (
        db.query(ControlInstance)
        .filter(ControlInstance.is_deleted == False)  # noqa: E712
        .all()
    )  # 활성 tenant 자동 필터 (tenant_context)

    by_baseline_id = {
        inst.baseline_control_id: inst
        for inst in instances
        if inst.baseline_control_id is not None
    }

    result: list[dict] = []
    for base in baselines:
        inst = by_baseline_id.get(base.id)
        if inst is not None and inst.action == "exclude":
            continue
        row = {f: getattr(base, f) for f in CONTROL_FIELDS}
        row["id"] = base.id
        row["created_at"] = base.created_at
        row["updated_at"] = base.updated_at
        if inst is not None and inst.action == "override":
            for f in CONTROL_FIELDS:
                value = getattr(inst, f)
                if value is not None:  # NULL=baseline 따름 (False 는 유효한 override)
                    row[f] = value
        result.append(row)

    for inst in instances:
        if inst.baseline_control_id is None and inst.action == "add":
            row = {f: getattr(inst, f) for f in CONTROL_FIELDS}
            row["id"] = inst.id
            row["created_at"] = inst.created_at
            row["updated_at"] = inst.updated_at
            result.append(row)

    result.sort(key=lambda r: r["code"] or "")
    return result
