"""보고서 문서 (2026-10-06, 마스터 지시 "보고서 양식 템플릿 — 사용자가 수정할 수 있게").

회계연도마다 이사회 보고 패키지의 문서들(운영실태보고서·감사위원회 평가보고서·이사회 보고 자료·의사록(안) 등)을 둔다.
**문서 본문(기본 문구)은 화면의 템플릿이 데이터로 만들고, 여기에는 사람이 고친 부분만 저장한다**(`content`:
섹션 키 → 고친 문단, 표 키 → 고친 행). 고치지 않은 섹션은 데이터가 바뀌면 같이 바뀐다 — 수치를 손으로 옮겨 적지 않는다.
`doc_key = meta` 는 패키지 기본 정보(회사명·대표이사·위원 명단·회의 일시 등)다.

확정(`final`)되면 수정할 수 없고, 마스터관리자가 재오픈한다. 이력은 `governance_events`(entity `report_document`).
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

ENTITY_REPORT_DOCUMENT = "report_document"
DOC_DRAFT = "draft"
DOC_FINAL = "final"

# 문서 키 — 화면 템플릿과 같은 목록. 모르는 키는 저장하지 않는다
DOC_KEYS = (
    "meta",            # 패키지 기본 정보
    "ops_report",      # 대표이사·내부회계관리자의 내부회계관리제도 운영실태보고서
    "ac_report",       # 감사위원회의 내부회계관리제도 평가보고서
    "board_ops",       # 이사회 보고 — 운영실태 결과 보고(요약)
    "ac_eval",         # 감사위원회 평가결과·세부 내역·활동 내역
    "ac_minutes",      # 감사위원회 의사록(안)
    "board_minutes",   # 이사회 의사록(안)
)


class ReportDocument(AuditedBase):
    __tablename__ = "report_documents"
    __table_args__ = (
        Index("uq_report_documents_year_key", "tenant_id", "fiscal_year", "doc_key", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    doc_key: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DOC_DRAFT)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
