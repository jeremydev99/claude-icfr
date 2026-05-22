from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


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
    id: UUID
    created_at: datetime
    updated_at: datetime
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
    id: UUID
    created_at: datetime
    updated_at: datetime
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
    created_at: datetime
    updated_at: datetime
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
    updates: ControlUpdate

class ClearAllRequest(BaseModel):
    confirm: str  # 반드시 "DELETE_ALL_RCM_DATA"
