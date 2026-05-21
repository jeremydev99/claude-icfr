from datetime import date
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import AuditedBase


class TestRun(AuditedBase):
    __tablename__ = "test_runs"

    control_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False, index=True
    )
    tester_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["TestStep"]] = relationship(
        "TestStep", back_populates="test_run", cascade="all, delete-orphan"
    )


class TestStep(AuditedBase):
    __tablename__ = "test_steps"

    test_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_runs.id"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)

    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="steps")
