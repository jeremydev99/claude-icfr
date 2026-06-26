from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class UserBrief(BaseModel):
    """이력·감사 응답용 사용자 간략 정보 (id + display_name=실명).

    test_module·remediation 양쪽 history 응답에서 공통 사용 (작업: 감사 일관화).
    단순 데이터 스키마이므로 공통화는 ADR-0020 추상화 위반 아님.
    """
    id: UUID
    display_name: str

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    role: str = "user"


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordResetRequest(BaseModel):
    """관리자 비밀번호 리셋 — old 검증 없이 재설정 (관리자 전용)."""
    new_password: str = Field(min_length=8)
