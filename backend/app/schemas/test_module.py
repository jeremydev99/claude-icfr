from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.user import UserBrief  # 공통 사용자 간략 스키마 (id+display_name)


# ── ControlRiskAssessment (RAWC) ──────────────────────────

class ControlRiskAssessmentBase(BaseModel):
    control_id: UUID
    fiscal_year: int
    frequency_score: int = Field(default=2, ge=1, le=3)
    nature_score: int = Field(default=2, ge=1, le=3)
    precision_score: int = Field(default=2, ge=1, le=3)
    dependency_score: int = Field(default=2, ge=1, le=3)
    automation_score: int = Field(default=2, ge=1, le=3)
    authority_score: int = Field(default=2, ge=1, le=3)
    review_score: int = Field(default=2, ge=1, le=3)
    prior_year_effectiveness: str = Field(default="N/A", pattern="^(Effective|Not_Effective|N/A)$")
    overall_assessment: str = Field(default="Not_Higher", pattern="^(Not_Higher|Higher)$")
    assessor_id: UUID | None = None
    assessment_date: date | None = None
    notes: str | None = None

class ControlRiskAssessmentCreate(ControlRiskAssessmentBase):
    pass

class ControlRiskAssessmentUpdate(BaseModel):
    frequency_score: int | None = Field(None, ge=1, le=3)
    nature_score: int | None = Field(None, ge=1, le=3)
    precision_score: int | None = Field(None, ge=1, le=3)
    dependency_score: int | None = Field(None, ge=1, le=3)
    automation_score: int | None = Field(None, ge=1, le=3)
    authority_score: int | None = Field(None, ge=1, le=3)
    review_score: int | None = Field(None, ge=1, le=3)
    prior_year_effectiveness: str | None = Field(None, pattern="^(Effective|Not_Effective|N/A)$")
    overall_assessment: str | None = Field(None, pattern="^(Not_Higher|Higher)$")
    assessor_id: UUID | None = None
    assessment_date: date | None = None
    notes: str | None = None

class ControlRiskAssessmentRead(ControlRiskAssessmentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── TestRun ───────────────────────────────────────────────

class TestRunBase(BaseModel):
    control_id: UUID
    fiscal_year: int
    tester_id: UUID | None = None
    test_date: date | None = None
    result: str | None = Field(default=None, pattern="^(pass|fail|n/a)$")
    notes: str | None = None
    # 그룹 7
    wtt_summary: str | None = None
    existing_process_notes: str | None = None
    method_inquiry: bool = False
    method_observation: bool = False
    method_inspection: bool = False
    method_reperformance: bool = False
    population: str | None = None
    test_frequency: str | None = Field(default=None, pattern="^(O|D|W|M|Q|A)$")
    sample_size: int | None = None
    procedure: str | None = None

class TestRunCreate(TestRunBase):
    pass

class TestRunUpdate(BaseModel):
    tester_id: UUID | None = None
    test_date: date | None = None
    result: str | None = Field(None, pattern="^(pass|fail|n/a)$")
    notes: str | None = None
    wtt_summary: str | None = None
    existing_process_notes: str | None = None
    method_inquiry: bool | None = None
    method_observation: bool | None = None
    method_inspection: bool | None = None
    method_reperformance: bool | None = None
    population: str | None = None
    test_frequency: str | None = Field(None, pattern="^(O|D|W|M|Q|A)$")
    sample_size: int | None = None
    procedure: str | None = None

class TestRunRead(TestRunBase):
    id: UUID
    status: str
    approved_by_id: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── TestStep ──────────────────────────────────────────────

class TestStepBase(BaseModel):
    step_order: int
    description: str
    result: str = Field(pattern="^(pass|fail)$")

class TestStepCreate(TestStepBase):
    test_run_id: UUID

class TestStepUpdate(BaseModel):
    description: str | None = None
    result: str | None = Field(None, pattern="^(pass|fail)$")

class TestStepRead(TestStepBase):
    id: UUID
    test_run_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── TestStatusHistory ─────────────────────────────────────
# UserBrief 는 app.schemas.user 로 공통화 (감사 일관화). 위에서 import.


class TestStatusHistoryRead(BaseModel):
    id: UUID
    test_run_id: UUID
    from_status: str | None
    to_status: str
    changed_by: UserBrief          # id + display_name (명세서 5.3절)
    changed_by_id: UUID            # FK 원본 (하위 호환)
    changed_at: datetime
    reason: str | None
    model_config = ConfigDict(from_attributes=True)


# ── 워크플로 전이 요청 ─────────────────────────────────────

class TransitionRequest(BaseModel):
    to_status: str = Field(pattern="^(in_progress|completed|approved)$")
    reason: str | None = None
