"""감사 로그 (2026-10-06, 마스터 지시 "관리자 페이지에 감사로그 — 사용자 활동 전체").

API 요청 중 **상태를 바꾸는 요청 전부**(등록·수정·삭제·승인·확정·로그인/로그아웃 등)와 **다운로드·내보내기 조회**를
한 줄씩 남긴다(`core/middleware.AuditLogMiddleware`). 화면 조회(GET)는 양이 많고 의미가 적어 남기지 않는다.
행은 **추가만** 한다 — 수정·삭제 API 가 없다(감사 증적). 누가·언제·어디서(IP)·무엇을(모듈·동작·대상)·결과(상태 코드)를 담는다.

AuditedBase 가 아니다: 요청 처리 밖(미들웨어)에서 쓰므로 활성 테넌트 자동 필터·행위자 스탬프를 타지 않고,
`tenant_id` 는 요청 헤더나 사용자의 접근 테넌트로 직접 채운다. 조회 API 가 활성 테넌트로 거른다.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                                                  index=True)
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    route: Mapped[str] = mapped_column(String(300), nullable=False)      # 경로 틀(/api/scoping/{scoping_id})
    path: Mapped[str] = mapped_column(String(500), nullable=False)       # 실제 경로
    module: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_label: Mapped[str | None] = mapped_column(String(300), nullable=True)   # 기록 시점 대상 이름(코드·명칭)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
