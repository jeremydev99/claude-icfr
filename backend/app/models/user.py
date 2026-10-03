from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentityBase


class User(IdentityBase):
    """전역 사용자 계정 — tenant 비종속 (ADR-0025).

    한 계정이 여러 회사(tenant)에 접근 가능. tenant 접근 권한은 UserTenantAccess가
    유일한 진실 원천. User 자체에는 tenant_id 를 두지 않는다."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 보안 1단계(2026-10-01): 연속 실패 횟수·잠금 해제 시각·비밀번호 변경 시각.
    # password_changed_at 보다 먼저 발급된 토큰은 무효다 — 비밀번호를 바꾸면 다른 기기의 세션이 끊긴다.
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # MFA(TOTP, ADR-0039) — 비밀값은 암호문만. pending 은 등록 중(첫 코드 확인 전), recovery 는 복구 코드 해시 목록
    mfa_secret_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mfa_pending_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_recovery: Mapped[list | None] = mapped_column(JSON, nullable=True)
