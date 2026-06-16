from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import AuditedBase


class EvidenceFile(AuditedBase):
    __tablename__ = "evidence_files"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    minio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    links: Mapped[list["EvidenceLink"]] = relationship(
        "EvidenceLink", back_populates="file", cascade="all, delete-orphan"
    )


class EvidenceLink(AuditedBase):
    __tablename__ = "evidence_links"

    file_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("evidence_files.id"), nullable=False, index=True
    )
    linked_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    linked_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    file: Mapped["EvidenceFile"] = relationship("EvidenceFile", back_populates="links")
