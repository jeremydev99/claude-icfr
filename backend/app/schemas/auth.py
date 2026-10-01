from pydantic import BaseModel, EmailStr, field_validator

from app.core.password_policy import validate_password


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """본인 비밀번호 변경 — old 검증 후 변경."""
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return validate_password(v)


class ChangePasswordResponse(BaseModel):
    """변경 후 새 토큰 — 기존 토큰은 무효가 되므로(다른 기기 세션 종료) 이 기기는 새 토큰으로 이어간다."""
    detail: str
    access_token: str
    refresh_token: str
