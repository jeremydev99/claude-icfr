from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class TestStepBase(BaseModel):
    step_order: int
    description: str
    result: str = Field(pattern="^(pass|fail)$")

class TestStepCreate(TestStepBase):
    test_run_id: UUID

class TestStepUpdate(BaseModel):
    description: str | None = None
    result: str | None = Field(None, pattern="^(pass|fail)$")

class TestStepRead(TestStepBase):
    id: UUID
    test_run_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TestRunBase(BaseModel):
    control_id: UUID
    tester_id: UUID
    test_date: date
    result: str = Field(pattern="^(pass|fail|n/a)$")
    notes: str | None = None

class TestRunCreate(TestRunBase):
    pass

class TestRunUpdate(BaseModel):
    result: str | None = Field(None, pattern="^(pass|fail|n/a)$")
    notes: str | None = None

class TestRunRead(TestRunBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
