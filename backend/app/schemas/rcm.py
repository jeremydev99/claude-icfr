from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    assessment_level: str = Field(default="LR", pattern="^(LR|MR|HR|SR)$")
    sub_process_id: UUID

class RiskCreate(RiskBase):
    pass

class RiskUpdate(BaseModel):
    description: str | None = None
    assessment_level: str | None = Field(None, pattern="^(LR|MR|HR|SR)$")

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
    preventive_detective: str = Field(default="P", pattern="^(P|D)$")
    auto_manual: str = Field(default="M", pattern="^(A|M|IT)$")
    activity_approval: bool = False
    activity_verification: bool = False
    activity_physical: bool = False
    activity_master_data: bool = False
    activity_reconciliation: bool = False
    activity_supervision: bool = False

    # 그룹 5
    related_accounts: str | None = None
    frequency: str = Field(default="A", pattern="^(O|D|W|M|Q|A)$")
    ipe_relevant: str = Field(default="N/A", pattern="^(Y|N|N/A)$")
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
    preventive_detective: str | None = Field(None, pattern="^(P|D)$")
    auto_manual: str | None = Field(None, pattern="^(A|M|IT)$")
    activity_approval: bool | None = None
    activity_verification: bool | None = None
    activity_physical: bool | None = None
    activity_master_data: bool | None = None
    activity_reconciliation: bool | None = None
    activity_supervision: bool | None = None
    related_accounts: str | None = None
    frequency: str | None = Field(None, pattern="^(O|D|W|M|Q|A)$")
    ipe_relevant: str | None = Field(None, pattern="^(Y|N|N/A)$")
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
