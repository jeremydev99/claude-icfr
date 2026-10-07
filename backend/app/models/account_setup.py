"""직원 계정 설정 링크 (2026-10-07, ADR-0041 — 관리자가 비밀번호를 모르게).

관리자가 계정을 만들거나 재설정 링크를 발급하면 한 번 쓰는 링크가 생긴다. 직원이 링크에서 직접 비밀번호를 정한다.
링크 원문은 저장하지 않고 SHA-256 해시만 둔다. 72시간 유효, 한 번 쓰면 끝, 새로 발급하면 이전 것은 취소.
사용자 계정과 같이 전역(테넌트 비종속)이다.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentityBase

PURPOSE_INVITE = "invite"   # 새 직원 — 처음 비밀번호
PURPOSE_RESET = "reset"     # 기존 직원 — 비밀번호 재설정(사용 전까지 기존 비밀번호 유지)


class AccountSetupToken(IdentityBase):
    __tablename__ = "account_setup_tokens"
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(10), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
