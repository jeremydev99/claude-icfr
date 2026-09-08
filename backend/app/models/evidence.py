"""증빙 파일 모델 — ADR-0032 §2.7.

**증빙은 감사 증거물이다.** 지워지면 안 된다.

`AuditedBase` 의 `deleted_at`/`deleted_by` 는 문자열 컬럼이라 "누가"를 계정으로
되짚을 수 없다. 증빙은 **"누가 언제 올렸다가 지웠는지"가 감사에서 실제로 묻는
질문**이므로 계정 FK 로 따로 남긴다.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    # ── 부착 대상 (ADR-0032 §2.7) ──
    # **증빙은 통제 × 회차에 붙는다.** 같은 통제라도 회차가 다르면 다른 증빙이다.
    #
    # 활동(assessment_activities)이 아니라 통제×회차에 직접 붙인 이유:
    # ① 활동은 같은 통제·회차에 여러 번 남을 수 있어(재수행·보완) 활동에 붙이면
    #    "어느 수행분의 증빙인가"가 갈린다
    # ② 마감 미완 판정이 통제×회차 단위라 증빙도 같은 축이어야 짝이 맞는다
    # ③ §2.2 경로가 cycles/{cycle_id}/controls/{control_id} 구조다
    #
    # **nullable 인 것은 기존 4건(시드·테스트 잔재) 때문이다.** 신규 업로드에서는
    # 핸들러가 필수로 막는다 — DB 제약으로 막으면 그 4건을 지우거나 값을 지어내야 한다
    # (13.9-29 — 실데이터 조작을 하지 않기로 확정).
    cycle_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    # control_id 에 FK 를 걸지 않는다 — baseline 유래면 baseline_controls.id, add 면
    # control_instances.id 라 참조 테이블이 하나로 정해지지 않는다(정체성 id 규칙,
    # ADR-0027). role_assignments.target_id·cycle_targets.control_id 와 같은 사정이다.
    control_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)

    # ── 삭제 이력 (ADR-0032 §2.4) ──
    # **파일도 레코드도 지우지 않는다.** 삭제 표시만 하고 조회에서 제외한다.
    # 레코드만 남기고 파일을 지우면 "그때 지운 게 뭐였나"에 답할 수 없다 —
    # 보존기간이 5년 이상이므로 파일도 그 기간을 따른다(§2.9).
    deleted_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    deleted_at_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

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
