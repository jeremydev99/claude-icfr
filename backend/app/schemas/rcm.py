from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


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


class ControlBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    process_id: UUID
    frequency: str = Field(min_length=1, max_length=20)

class ControlCreate(ControlBase):
    pass

class ControlUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    frequency: str | None = Field(None, min_length=1, max_length=20)

class ControlRead(ControlBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ControlAssertionBase(BaseModel):
    control_id: UUID
    risk_category_id: UUID

class ControlAssertionCreate(ControlAssertionBase):
    pass

class ControlAssertionRead(ControlAssertionBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
