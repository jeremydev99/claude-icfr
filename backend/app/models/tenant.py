"""멀티테넌시 모델 (ADR-0025).

- Tenant: 회사. 모든 비즈니스 데이터의 격리 단위.
- UserTenantAccess: user ↔ tenant 다대다 + 해당 tenant에서의 역할.
  한 계정이 여러 회사에 접근 = 매핑 다수. 온프레는 모든 user가 단일 tenant에 매핑.

Tenant / UserTenantAccess 는 tenant 비종속 전역 테이블이므로 IdentityBase 를 상속한다
(자기 자신에 tenant_id 금지 — 순환 방지).
"""
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import IdentityBase


class Tenant(IdentityBase):
    """회사(tenant). SaaS = 공유 DB 다중 tenant, 온프레 = tenant 1개짜리 인스턴스."""
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserTenantAccess(IdentityBase):
    """user ↔ tenant 접근 매핑 + 해당 tenant에서의 역할.

    tenant 접근 권한의 유일한 진실 원천. (user, tenant) 조합은 유일."""
    __tablename__ = "user_tenant_access"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # noqa: F821
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])

    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant_access"),
    )
