from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean
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
