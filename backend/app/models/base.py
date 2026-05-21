from datetime import datetime
from uuid import UUID
from uuid_utils import uuid7 as _uuid7_native
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String, Boolean, Integer, func
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


class AuditedBase(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    """공통 감사 컬럼이 모두 포함된 베이스 — 모든 비즈니스 테이블이 이걸 상속."""
    __abstract__ = True
