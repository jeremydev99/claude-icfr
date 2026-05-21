from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import AuditedBase


class Process(AuditedBase):
    __tablename__ = "processes"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    controls: Mapped[list["Control"]] = relationship("Control", back_populates="process")


class RiskCategory(AuditedBase):
    __tablename__ = "risk_categories"

    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Control(AuditedBase):
    __tablename__ = "controls"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("processes.id"), nullable=False, index=True
    )
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)

    process: Mapped["Process"] = relationship("Process", back_populates="controls")
    assertions: Mapped[list["ControlAssertion"]] = relationship(
        "ControlAssertion", back_populates="control", cascade="all, delete-orphan"
    )


class ControlAssertion(AuditedBase):
    __tablename__ = "control_assertions"

    control_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False, index=True
    )
    risk_category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("risk_categories.id"), nullable=False, index=True
    )

    control: Mapped["Control"] = relationship("Control", back_populates="assertions")
    risk_category: Mapped["RiskCategory"] = relationship("RiskCategory")
