"""외부 사용자 — 초대·접근 범위·정기 재확인 (ADR-0039).

- `Invitation`: 요청 → 마스터 승인 → 1회용 링크(토큰은 **해시만** 저장, 72시간) → 수락.
- `ExternalProfile`: 테넌트별 외부 사용자의 유형·소속 법인·모듈·유효기간·상태. 인증 의존성이 요청마다 확인한다.
- `AccessReview`: 분기별 외부 사용자 접근 재확인 기록(누가·언제·그때 목록) — ITGC 증적.
"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

# 유형 → 테넌트 역할 (ADR-0039 §2.1)
TYPE_ADVISOR = "advisor"          # PA회계법인
TYPE_AUDITOR = "auditor"          # 외부감사인
TYPE_COMMITTEE = "committee"      # 감사위원회·사외이사
TYPE_SPECIALIST = "specialist"    # 세무·기장대리인
TYPE_LABELS = {TYPE_ADVISOR: "PA회계법인(ICFR 자문)", TYPE_AUDITOR: "외부감사인",
               TYPE_COMMITTEE: "감사위원회·사외이사", TYPE_SPECIALIST: "세무·기장대리인"}
TYPE_ROLE = {TYPE_ADVISOR: "external_advisor", TYPE_AUDITOR: "external_auditor",
             TYPE_COMMITTEE: "auditor", TYPE_SPECIALIST: "external_specialist"}
# 쓰기 모듈 기본값 — 세무·기장대리인은 재무제표만(마스터 확정). 다른 유형은 역할이 범위를 정한다
DEFAULT_MODULES = {TYPE_SPECIALIST: ["financial_statements"]}
MODULE_LABELS = {"financial_statements": "재무제표"}

INV_PENDING = "pending_approval"
INV_APPROVED = "approved"         # 링크 발급됨, 수락 대기
INV_ACCEPTED = "accepted"
INV_REVOKED = "revoked"
INV_EXPIRED = "expired"
INV_LABELS = {INV_PENDING: "승인 대기", INV_APPROVED: "수락 대기", INV_ACCEPTED: "수락 완료",
              INV_REVOKED: "취소", INV_EXPIRED: "만료"}

EXT_ACTIVE = "active"
EXT_REVOKED = "revoked"


class Invitation(AuditedBase):
    __tablename__ = "invitations"
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_type: Mapped[str] = mapped_column(String(20), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    modules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=INV_PENDING)
    requested_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    approved_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidentiality_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalProfile(AuditedBase):
    __tablename__ = "external_profiles"
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    user_type: Mapped[str] = mapped_column(String(20), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    modules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=EXT_ACTIVE)
    invitation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    approved_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccessReview(AuditedBase):
    """외부 사용자 접근 재확인 1회 — 그때의 목록을 스냅샷으로 남긴다."""
    __tablename__ = "access_reviews"
    reviewed_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
