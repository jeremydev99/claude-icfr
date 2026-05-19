"""
EUC 모듈 모델.

Phase 1에서 다음 엔티티 추가 예정 (ClaudeICFR.md 섹션 4.4 참조):
- EUCFile, EUCHashHistory

모든 PK: Surrogate UUID (ADR-0015).
감사 컬럼: AuditedBase 상속 (created_at, updated_at, is_deleted 등).
"""
# from sqlalchemy.orm import Mapped, mapped_column
# from app.models.base import AuditedBase

# Phase 1에서 활성화