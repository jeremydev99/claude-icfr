from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scoping import GovernanceInfo
from app.schemas.user import UserBrief  # 공통 사용자 간략 스키마 (test_module과 일관화)

# ── Deficiency ─────────────────────────────────────────────

class DeficiencyBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    test_run_id: UUID | None = None
    severity: str = Field(pattern="^(low|medium|high)$")
    description: str
    status: str = Field(default="open", pattern="^(open|in_progress|closed)$")
    fiscal_year: int = Field(default=2025)
    control_id: UUID | None = None

class DeficiencyCreate(DeficiencyBase):
    final_conclusion: str | None = None   # 작성 중 결론 — 확정은 결재 승인으로만(ADR-0038 2-3)

class DeficiencyUpdate(BaseModel):
    severity: str | None = Field(None, pattern="^(low|medium|high)$")
    description: str | None = None
    status: str | None = Field(None, pattern="^(open|in_progress|closed)$")
    fiscal_year: int | None = None
    control_id: UUID | None = None
    final_conclusion: str | None = None
    # confirmed_at·confirmed_by_id 는 받지 않는다 — 확정은 결재 승인으로만 서버가 적는다(ADR-0038 2-3)

class DeficiencyRead(DeficiencyBase):
    id: UUID
    final_conclusion: str | None = None
    confirmed_at: datetime | None = None
    confirmed_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # 결재 상태(ADR-0038 2-3) — draft | review | confirmed
    approval_status: str = "draft"
    model_config = ConfigDict(from_attributes=True)


class DeficiencyBulkTransition(BaseModel):
    """미비점 일괄 결재(ADR-0038 2-4) — 각 건을 단건 규칙 그대로 판정한다."""
    ids: list[UUID] = Field(min_length=1, max_length=200)
    to_status: str = Field(pattern="^(draft|review|confirmed)$")
    reason: str | None = None


class DeficiencyBulkResultItem(BaseModel):
    id: UUID
    code: str | None
    ok: bool
    approval_status: str | None
    detail: str | None = None


class DeficiencyBulkResult(BaseModel):
    succeeded: int
    failed: int
    items: list[DeficiencyBulkResultItem]


class DeficiencyApproval(BaseModel):
    """미비점 평가 결재 정보 — 화면의 결재 패널이 그대로 쓴다."""
    deficiency: DeficiencyRead
    legacy_confirmed: bool          # 확정인데 결재 기록 없음 = 이전 방식 확정
    governance: GovernanceInfo


# ── RemediationStatusHistory ────────────────────────────────

class RemediationStatusHistoryRead(BaseModel):
    id: UUID
    remediation_plan_id: UUID
    from_status: str | None = None
    to_status: str
    changed_by: UserBrief          # id + display_name(실명) — test_module과 동일 구조
    changed_by_id: UUID            # FK 원본 (하위 호환)
    changed_at: datetime
    reason: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ── RemediationPlan ─────────────────────────────────────────

class RemediationPlanBase(BaseModel):
    deficiency_id: UUID
    owner_id: UUID
    target_date: date
    action_plan: str
    improvement_description: str | None = None
    priority: str = Field(default="Medium", pattern="^(High|Medium|Low)$")
    owner_opinion: str | None = None
    reviewer_opinion: str | None = None

class RemediationPlanCreate(RemediationPlanBase):
    pass

class RemediationPlanUpdate(BaseModel):
    target_date: date | None = None
    action_plan: str | None = None
    improvement_description: str | None = None
    priority: str | None = Field(None, pattern="^(High|Medium|Low)$")
    owner_opinion: str | None = None
    reviewer_opinion: str | None = None

class RemediationPlanRead(RemediationPlanBase):
    id: UUID
    status: str
    approved_by_id: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RemediationTransitionRequest(BaseModel):
    to_status: str = Field(pattern="^(in_progress|completed|approved)$")
    reason: str | None = None


# ── DesignAssessment ────────────────────────────────────────

class DesignAssessmentBase(BaseModel):
    control_id: UUID
    fiscal_year: int
    design_score_1: int = Field(default=2, ge=1, le=3)
    design_score_2: int = Field(default=2, ge=1, le=3)
    design_score_3: int = Field(default=2, ge=1, le=3)
    design_score_4: int = Field(default=2, ge=1, le=3)
    design_score_5: int = Field(default=2, ge=1, le=3)
    design_score_6: int = Field(default=2, ge=1, le=3)
    design_score_7: int = Field(default=2, ge=1, le=3)
    design_score_8: int = Field(default=2, ge=1, le=3)
    overall_design: str = Field(default="Effective", pattern="^(Effective|Not_Effective)$")
    design_notes: str | None = None
    assessment_method: str = Field(default="Walkthrough", pattern="^(Walkthrough|Test_of_Operation|Hybrid)$")
    performer_name: str | None = None
    performance_frequency: str | None = Field(None, pattern="^(O|D|W|M|Q|A)$")
    procedure: str | None = None
    evidence_notes: str | None = None
    assessor_id: UUID | None = None
    assessment_date: date | None = None

class DesignAssessmentCreate(DesignAssessmentBase):
    pass

class DesignAssessmentUpdate(BaseModel):
    design_score_1: int | None = Field(None, ge=1, le=3)
    design_score_2: int | None = Field(None, ge=1, le=3)
    design_score_3: int | None = Field(None, ge=1, le=3)
    design_score_4: int | None = Field(None, ge=1, le=3)
    design_score_5: int | None = Field(None, ge=1, le=3)
    design_score_6: int | None = Field(None, ge=1, le=3)
    design_score_7: int | None = Field(None, ge=1, le=3)
    design_score_8: int | None = Field(None, ge=1, le=3)
    overall_design: str | None = Field(None, pattern="^(Effective|Not_Effective)$")
    design_notes: str | None = None
    assessment_method: str | None = Field(None, pattern="^(Walkthrough|Test_of_Operation|Hybrid)$")
    performer_name: str | None = None
    performance_frequency: str | None = Field(None, pattern="^(O|D|W|M|Q|A)$")
    procedure: str | None = None
    evidence_notes: str | None = None
    assessor_id: UUID | None = None
    assessment_date: date | None = None

class DesignAssessmentRead(DesignAssessmentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
