from pydantic import BaseModel, EmailStr, field_validator

from app.core.password_policy import validate_password


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """로그인 결과 — MFA 대상이면 토큰 대신 `mfa_token`(5분)과 다음 단계를 준다 (ADR-0039)."""
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False          # 등록돼 있음 → 코드 입력
    mfa_setup_required: bool = False    # 의무인데 미등록 → 등록 화면
    mfa_token: str | None = None


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str          # 6자리 OTP 또는 복구 코드(XXXX-XXXX)


class MfaSetupRequest(BaseModel):
    mfa_token: str | None = None   # 로그인 중 등록이면 필요, 로그인한 상태면 생략(Authorization 헤더)


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class MfaEnableRequest(BaseModel):
    mfa_token: str | None = None
    code: str


class MfaEnableResponse(BaseModel):
    recovery_codes: list[str]
    access_token: str | None = None     # 로그인 중 등록이면 여기서 로그인이 끝난다
    refresh_token: str | None = None


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
