from datetime import date
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import AuditedBase


class Deficiency(AuditedBase):
    __tablename__ = "deficiencies"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    test_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_runs.id"), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    remediation_plan: Mapped["RemediationPlan | None"] = relationship(
        "RemediationPlan", back_populates="deficiency", uselist=False
    )


class RemediationPlan(AuditedBase):
    __tablename__ = "remediation_plans"

    deficiency_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("deficiencies.id"), nullable=False, unique=True, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    action_plan: Mapped[str] = mapped_column(Text, nullable=False)

    deficiency: Mapped["Deficiency"] = relationship("Deficiency", back_populates="remediation_plan")
