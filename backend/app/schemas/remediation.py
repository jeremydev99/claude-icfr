from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class DeficiencyBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    test_run_id: UUID | None = None
    severity: str = Field(pattern="^(low|medium|high)$")
    description: str
    status: str = Field(default="open", pattern="^(open|in_progress|closed)$")

class DeficiencyCreate(DeficiencyBase):
    pass

class DeficiencyUpdate(BaseModel):
    severity: str | None = Field(None, pattern="^(low|medium|high)$")
    description: str | None = None
    status: str | None = Field(None, pattern="^(open|in_progress|closed)$")

class DeficiencyRead(DeficiencyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RemediationPlanBase(BaseModel):
    deficiency_id: UUID
    owner_id: UUID
    target_date: date
    action_plan: str

class RemediationPlanCreate(RemediationPlanBase):
    pass

class RemediationPlanUpdate(BaseModel):
    target_date: date | None = None
    action_plan: str | None = None

class RemediationPlanRead(RemediationPlanBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
