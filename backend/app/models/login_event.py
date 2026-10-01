from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentityBase


class LoginEvent(IdentityBase):
    """로그인 시도 기록 (보안 1단계, 2026-10-01) — 성공·실패·잠김을 IP·기기와 함께 남긴다.

    사용자 계정이 전역(ADR-0025)이라 이 기록도 테넌트에 속하지 않는다. 행위자는 `system:auth-login`.
    없는 이메일로 시도한 것도 남긴다(`user_id` NULL) — 대입 공격 흔적을 보려는 것이다.
    """
    __tablename__ = "login_events"

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # ok | bad_password | unknown_email | locked | inactive
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
