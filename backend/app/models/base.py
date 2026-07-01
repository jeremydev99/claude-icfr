from datetime import datetime
from uuid import UUID
from uuid_utils import uuid7 as _uuid7_native
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String, Boolean, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


def uuid7() -> UUID:
    """기본 PK 생성 — UUIDv7 (시간 기반 정렬, 인덱스 효율 ↑). ADR-0020."""
    return UUID(str(_uuid7_native()))


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class VersionMixin:
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class UUIDPrimaryKeyMixin:
    """Surrogate UUID PK — UUIDv7 기본 (ADR-0015, ADR-0020)."""
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7, nullable=False
    )


class TenantMixin:
    """멀티테넌시 — 회사(tenant) 격리 키 (ADR-0025).

    이 믹스인을 상속한 모든 모델은 자동 격리 대상이 된다:
    - 쓰기: before_flush 이벤트가 활성 tenant_id를 자동 stamp
    - 읽기: do_orm_execute + with_loader_criteria(TenantMixin, ...) 가 자동 필터
    (app/core/tenant_context.py)
    """
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )


class IdentityBase(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    """tenant 비종속 전역 테이블용 베이스 — User / Tenant / UserTenantAccess 전용.

    tenant_id 를 포함하지 않는다 (전역 계정·회사 정의·접근 매핑은 tenant에 귀속될 수 없음)."""
    __abstract__ = True


class AuditedBase(IdentityBase, TenantMixin):
    """공통 감사 컬럼 + tenant_id 가 모두 포함된 베이스 — 모든 비즈니스 테이블이 이걸 상속."""
    __abstract__ = True
