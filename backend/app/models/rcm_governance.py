"""회계연도 RCM 확정 (ADR-0038 2-5) — RCM 은 하나뿐인 라이브 문서라, 회계연도별 확정본을 따로 둔다.

- `RcmFiscalYear` — 회계연도 RCM 문서 1건(결재 대상). 결재 상태는 공통 `approval_states`(entity_type=rcm_fiscal_year).
- `RcmSnapshot` — 승인 시점의 RCM 전체(프로세스·하위·위험·통제·어서션 연결). 확정마다 1행, **지우지 않는다**.
  재오픈 후 다시 확정하면 다음 버전 행이 생기고 이전 버전은 그대로 남는다.
- 잠금: 가장 최근 회계연도 RCM 이 검토 중·확정이면 라이브 RCM 쓰기 전부 409(`services/rcm_approval.ensure_rcm_editable`).
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase


class RcmFiscalYear(AuditedBase):
    __tablename__ = "rcm_fiscal_years"
    __table_args__ = (
        Index("uq_rcm_fiscal_years_year", "tenant_id", "fiscal_year", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)


class RcmSnapshot(AuditedBase):
    __tablename__ = "rcm_snapshots"
    rcm_year_id: Mapped[UUID] = mapped_column(ForeignKey("rcm_fiscal_years.id"), nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    control_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
