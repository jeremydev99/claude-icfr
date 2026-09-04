"""평가 회차·활동·승인 스키마 — 3-2.

계약은 기존 규약을 따른다(`docs/api/org-contract.md`·`rcm-hierarchy-contract.md`).
목록 봉투 `{"items", "total", "skip", "limit"}`, PATCH 는 `exclude_unset` 판별.
"""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_KIND = "^(design|operation)$"
_FREQ = "^(weekly|monthly|quarterly|semiannual|annual)$"
_ACTIVITY = "^(design|design_change|design_assessment|test|operation_assessment)$"
_STAGE = "^(dept|assessor)$"


# ── 회차 ──────────────────────────────────────────────────

class CycleCreate(BaseModel):
    kind: str = Field(pattern=_KIND)
    frequency: str = Field(pattern=_FREQ)
    name: str = Field(min_length=1, max_length=200)
    # 미전송 시 회계연도 시작월 + 주기로 **제안값**을 계산한다(ADR-0032 §2.2).
    # 강제하지 않는다 — 담당자가 조정할 수 있어야 하므로 보내면 그 값을 쓴다.
    period_start: date | None = None
    period_end: date | None = None
    # 기간과 다른 개념 — "언제까지 작업하는가"
    due_date: date | None = None
    # 기간 제안에 쓰는 기준. 미전송 시 오늘 날짜 기준으로 회차를 잡는다
    period_index: int | None = Field(None, ge=1, le=53)
    fiscal_year: int | None = Field(None, ge=2000, le=2100)


class CycleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    period_start: date | None = None
    period_end: date | None = None
    due_date: date | None = None


class CycleRead(BaseModel):
    id: UUID
    kind: str
    frequency: str
    name: str
    period_start: date
    period_end: date
    due_date: date | None = None
    status: str
    closed_at: datetime | None = None
    closed_by_id: UUID | None = None
    incomplete_reason: str | None = None
    approved_at: datetime | None = None
    approved_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # 표시용 파생값
    closed_by_name: str | None = None
    approved_by_name: str | None = None
    target_count: int | None = None
    model_config = ConfigDict(from_attributes=True)


class CycleTargetRead(BaseModel):
    """회차 대상 통제 **스냅샷** 1건. 생성 시점 사실이며 이후 주기가 바뀌어도 불변."""
    control_id: UUID
    control_code: str | None = None
    model_config = ConfigDict(from_attributes=True)


class PeriodSuggestion(BaseModel):
    """기간 제안값. 회차 생성 화면이 미리 받아 채워 넣을 수 있게 별도로 낸다."""
    period_start: date
    period_end: date
    fiscal_year: int
    period_index: int
    fiscal_year_start_month: int


# ── 활동 ──────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    control_id: UUID
    activity_kind: str = Field(pattern=_ACTIVITY)
    result: str | None = Field(None, max_length=20)
    note: str | None = None


class ActivityRead(BaseModel):
    id: UUID
    cycle_id: UUID
    control_id: UUID
    activity_kind: str
    result: str | None = None
    note: str | None = None
    performed_by_id: UUID
    performed_at: datetime
    created_at: datetime
    performed_by_name: str | None = None
    # 이 활동에 붙은 승인 단계들
    approvals: list["ApprovalRead"] = []
    model_config = ConfigDict(from_attributes=True)


# ── 승인 ──────────────────────────────────────────────────

class ApprovalCreate(BaseModel):
    stage: str = Field(pattern=_STAGE)
    note: str | None = None


class ApprovalRead(BaseModel):
    id: UUID
    activity_id: UUID
    stage: str
    approved_by_id: UUID
    approved_at: datetime
    note: str | None = None
    approved_by_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ── 마감·최종승인 ─────────────────────────────────────────

class CycleCloseRequest(BaseModel):
    """미완 통제가 있으면 사유가 필수다(ADR-0032 §2.5).

    막으면 회차가 영원히 안 닫히고, 조용히 허용하면 무엇이 빠졌는지 남지 않는다.
    """
    incomplete_reason: str | None = None


class IncompleteControl(BaseModel):
    """마감 시 제시하는 미완 통제 1건. 무엇이 없어서 미완인지 함께 낸다."""
    control_id: UUID
    control_code: str | None = None
    missing: list[str]      # 없는 활동 종류


class CycleCloseResult(BaseModel):
    cycle: CycleRead
    incomplete: list[IncompleteControl] = []


ActivityRead.model_rebuild()
