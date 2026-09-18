import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.rcm_baseline import (
    ASSESSMENT_FREQUENCIES,
    AUTO_MANUAL_VALUES,
    FREQUENCY_VALUES,
    IPE_RELEVANT_VALUES,
    PREVENTIVE_DETECTIVE_VALUES,
    RISK_LEVEL_VALUES,
)


def _one_of(values: tuple[str, ...]) -> str:
    """허용 값 목록 → 정규식. **목록을 두 번 적지 않기 위해서다** — 정규식에 직접 쓰면
    상수와 어긋나도 알 방법이 없다. `N/A` 처럼 메타문자가 섞인 값이 있어 escape 한다."""
    return "^(" + "|".join(re.escape(v) for v in values) + ")$"

# ── Process ──────────────────────────────────────────────

class ProcessBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None

class ProcessCreate(ProcessBase):
    pass

class ProcessUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None

class ProcessRead(ProcessBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    # source envelope (ADR-0027 / ADR-0029, 2-A-4-3) — resolver 유래 항목의 정체성 메타.
    # 통제(ControlRead)와 **동일한 flat 계약**(중첩 wrapper 금지) — FE 가 계층별로 분기하지 않도록.
    source: str | None = None            # "baseline"(adopt/override) | "tenant"(add)
    baseline_id: UUID | None = None      # baseline 유래면 그 id, add면 None
    is_overridden: bool = False          # override instance 적용 시 True
    model_config = ConfigDict(from_attributes=True)


# ── SubProcess ────────────────────────────────────────────

class SubProcessBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    process_id: UUID

class SubProcessCreate(SubProcessBase):
    pass

class SubProcessUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)

class SubProcessRead(SubProcessBase):
    # resolver 는 상위 미지정 add 행을 낼 수 있어 읽기에서는 nullable (Create 는 Base 상속으로 required 유지). ADR-0029.
    process_id: UUID | None = None
    id: UUID
    created_at: datetime
    updated_at: datetime
    # source envelope (ADR-0027 / ADR-0029, 2-A-4-3) — resolver 유래 항목의 정체성 메타.
    # 통제(ControlRead)와 **동일한 flat 계약**(중첩 wrapper 금지) — FE 가 계층별로 분기하지 않도록.
    source: str | None = None            # "baseline"(adopt/override) | "tenant"(add)
    baseline_id: UUID | None = None      # baseline 유래면 그 id, add면 None
    is_overridden: bool = False          # override instance 적용 시 True
    model_config = ConfigDict(from_attributes=True)


# ── Risk ──────────────────────────────────────────────────

class RiskBase(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    description: str
    assessment_level: str = Field(default="LR", pattern=_one_of(RISK_LEVEL_VALUES))
    sub_process_id: UUID

class RiskCreate(RiskBase):
    pass

class RiskUpdate(BaseModel):
    description: str | None = None
    assessment_level: str | None = Field(None, pattern=_one_of(RISK_LEVEL_VALUES))

class RiskRead(RiskBase):
    # resolver 는 상위 미지정 add 행을 낼 수 있어 읽기에서는 nullable (Create 는 Base 상속으로 required 유지). ADR-0029.
    sub_process_id: UUID | None = None
    id: UUID
    created_at: datetime
    updated_at: datetime
    # source envelope (ADR-0027 / ADR-0029, 2-A-4-3) — resolver 유래 항목의 정체성 메타.
    # 통제(ControlRead)와 **동일한 flat 계약**(중첩 wrapper 금지) — FE 가 계층별로 분기하지 않도록.
    source: str | None = None            # "baseline"(adopt/override) | "tenant"(add)
    baseline_id: UUID | None = None      # baseline 유래면 그 id, add면 None
    is_overridden: bool = False          # override instance 적용 시 True
    model_config = ConfigDict(from_attributes=True)


# ── RiskCategory (Assertion) ──────────────────────────────

class RiskCategoryBase(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None

class RiskCategoryCreate(RiskCategoryBase):
    pass

class RiskCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = None

class RiskCategoryRead(RiskCategoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Control ───────────────────────────────────────────────

class ControlBase(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    risk_id: UUID

    # 그룹 2
    objective: str | None = None
    owner_name: str | None = None

    # 그룹 3
    is_key_control: bool = True
    preventive_detective: str = Field(default="P", pattern=_one_of(PREVENTIVE_DETECTIVE_VALUES))
    auto_manual: str = Field(default="M", pattern=_one_of(AUTO_MANUAL_VALUES))
    activity_approval: bool = False
    activity_verification: bool = False
    activity_physical: bool = False
    activity_master_data: bool = False
    activity_reconciliation: bool = False
    activity_supervision: bool = False

    # 그룹 5
    related_accounts: str | None = None
    frequency: str = Field(default="A", pattern=_one_of(FREQUENCY_VALUES))
    # 평가주기 — frequency(통제 수행 주기)와 다른 개념. 일 단위 미지원(ADR-0032 §2.1)
    assessment_frequency: str = Field(default="annual", pattern=_one_of(ASSESSMENT_FREQUENCIES))
    ipe_relevant: str = Field(default="N/A", pattern=_one_of(IPE_RELEVANT_VALUES))
    related_systems: str | None = None
    euc_description: str | None = None

class ControlCreate(ControlBase):
    pass

class ControlUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    objective: str | None = None
    owner_name: str | None = None
    is_key_control: bool | None = None
    preventive_detective: str | None = Field(None, pattern=_one_of(PREVENTIVE_DETECTIVE_VALUES))
    auto_manual: str | None = Field(None, pattern=_one_of(AUTO_MANUAL_VALUES))
    activity_approval: bool | None = None
    activity_verification: bool | None = None
    activity_physical: bool | None = None
    activity_master_data: bool | None = None
    activity_reconciliation: bool | None = None
    activity_supervision: bool | None = None
    related_accounts: str | None = None
    frequency: str | None = Field(None, pattern=_one_of(FREQUENCY_VALUES))
    assessment_frequency: str | None = Field(None, pattern=_one_of(ASSESSMENT_FREQUENCIES))
    ipe_relevant: str | None = Field(None, pattern=_one_of(IPE_RELEVANT_VALUES))
    related_systems: str | None = None
    euc_description: str | None = None

class ControlRead(ControlBase):
    id: UUID
    # resolve_controls 는 risk 없는 통제(risk_id NULL — 이관 전/미매핑)를 낼 수 있으므로
    # 읽기에서는 nullable (ControlCreate 는 ControlBase 상속으로 required 유지). ADR-0027 2-A-4-1.
    risk_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # source envelope (ADR-0027, 2-A-3) — resolve_controls 유래 항목의 정체성 메타.
    # flat 유지(중첩 wrapper 금지) — Regina FE 가 flat 계약(sourceEnvelope.ts)으로 준비 완료.
    # 기본값 보유 — 통제 조회 경로(search/상세/목록)는 2-A-4-2 로 전부 resolver 경유라
    # 실제로는 항상 채워진다. 기본값은 resolver 외 경로(직접 model_validate)의 호환용.
    source: str | None = None            # "baseline"(adopt/override) | "tenant"(add)
    baseline_id: UUID | None = None      # baseline 유래면 그 id, add면 None
    is_overridden: bool = False          # override instance 적용 시 True
    model_config = ConfigDict(from_attributes=True)


# ── ControlAssertion ──────────────────────────────────────

class ControlAssertionBase(BaseModel):
    control_id: UUID
    risk_category_id: UUID

class ControlAssertionCreate(ControlAssertionBase):
    pass

class ControlAssertionRead(ControlAssertionBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Bulk 작업 스키마 ──────────────────────────────────────

class BulkDeleteRequest(BaseModel):
    control_ids: list[UUID]

class BulkUpdateRequest(BaseModel):
    control_ids: list[UUID]
    # 단건 PATCH 와 동일 스키마 — 라우터가 exclude_unset 으로 미전송을 판별한다(2-A-4-2).
    updates: ControlUpdate


# ── Search 전용 응답 스키마 ──────────────────────────────────

class ControlSearchOut(ControlRead):
    """Search 엔드포인트 전용. ControlRead + 관계 데이터 4개 필드.

    FE 목록 화면이 별도 API 호출 없이 모든 정보를 받도록.
    """
    process_code: str | None = None
    sub_process_code: str | None = None
    risk_level: str | None = None  # risk.assessment_level (LR/MR/HR/SR)
    assertions: list[str] = []    # ["E", "C", "V"] 형태


class ControlSearchResponse(BaseModel):
    items: list[ControlSearchOut]
    total: int
    skip: int
    limit: int
    sort: str


# ── Dashboard summary (4-1) ─────────────────────────────────

class SummaryBucket(BaseModel):
    """집계 한 칸. `value` 는 **RCM 검색에 그대로 넘기는 필터 값**이다.

    화면이 라벨을 다시 만들지 않도록 `label` 을 함께 낸다 — 프로세스명처럼
    백엔드에만 있는 값이 섞여 있어 매핑을 FE 에 두면 반쪽이 된다.
    """
    value: str
    label: str
    count: int


class SummaryGroup(BaseModel):
    """집계 한 묶음. `filter_param` 이 None 이면 드릴스루할 수 없는 묶음이다."""
    key: str
    label: str
    filter_param: str | None = None
    buckets: list[SummaryBucket] = []


class OrgSummary(BaseModel):
    """통제 조직별 — `control_owner` 배정 → 그 사람의 주 소속 부서(ADR-0031 §2.2).

    **새 분류 체계가 아니다.** 배정이 0건이면 `unassigned` 가 전체 건수가 된다.
    """
    unassigned: int
    buckets: list[SummaryBucket] = []


class ProgressSummary(BaseModel):
    """진행 현황 — 평가 회차(ADR-0032)가 생기면 자동으로 채워진다.

    `targets` 는 시점별 진행 의무(회차 × 대상 통제), `completed` 는 활동이 한 건이라도
    기록된 대상 수, `incomplete` 는 나머지다. 회차 0건이면 전부 0 이며 **0 을 가리지 않는다.**
    """
    cycles: int
    targets: int
    activities: int
    completed: int
    incomplete: int


class RcmSummaryResponse(BaseModel):
    control_total: int
    process_total: int
    groups: list[SummaryGroup] = []
    org: OrgSummary
    progress: ProgressSummary
