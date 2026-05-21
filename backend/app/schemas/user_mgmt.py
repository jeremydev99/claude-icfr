from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserRoleBase(BaseModel):
    user_id: UUID
    role_name: str = Field(min_length=1, max_length=50)
    scope: str | None = None

class UserRoleCreate(UserRoleBase):
    pass

class UserRoleUpdate(BaseModel):
    role_name: str | None = Field(None, min_length=1, max_length=50)
    scope: str | None = None

class UserRoleRead(UserRoleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
