"""평가 회차·활동·승인 모델 — ADR-0032 §2.3~2.7, 3-2.

**회차는 전담부서(`assessor`)가 만든다**(§2.1). 통제책임자는 만들 수 없다.

**설계평가 회차와 운영평가 회차는 독립이다**(§2.2). 서로 참조하지 않으며 동시에 열린다.

**대상 통제는 회차 생성 시점에 스냅샷으로 고정한다**(`cycle_targets`).
ADR-0029 §2.1·§2.2 는 "저장하지 않고 조회 시점 계산"을 원칙으로 하지만 **성격이 다르다** —
그쪽은 *현재 상태*를 계산하는 것이고, 회차는 *과거 시점의 사실*을 기록하는 것이다.

셋 다 스냅샷을 요구한다.
1. 감사가 "1분기 운영평가 대상이 무엇이었는가"를 묻는다. 주기를 나중에 바꿔 과거 회차
   대상이 달라지면 증적 훼손이다.
2. 활동 기록은 통제별로 붙는데 대상이 계산이면, 주기 변경 후 "기록은 있는데 대상
   목록에 없는 통제"가 생긴다 — 모순 상태다.
3. ADR-0032 §5 가 본 단계 책임으로 못박은 "시점 조회 가능"과 직결된다.

**마감 단위는 회차다**(§2.4). 통제 단위 마감은 두지 않는다.
**미완이 있어도 마감할 수 있되 사유가 필수다**(§2.5) — 막으면 회차가 영원히 안 닫히고,
조용히 허용하면 무엇이 빠졌는지 남지 않는다.
"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditedBase

# ── 회차 종류 (ADR-0032 §2.2) ─────────────────────────────────────
CYCLE_DESIGN = "design"
CYCLE_OPERATION = "operation"
CYCLE_KINDS = (CYCLE_DESIGN, CYCLE_OPERATION)

# ── 회차 상태 (§2.4·§2.7) ────────────────────────────────────────
CYCLE_OPEN = "open"
CYCLE_CLOSED = "closed"
CYCLE_APPROVED = "approved"
CYCLE_STATUSES = (CYCLE_OPEN, CYCLE_CLOSED, CYCLE_APPROVED)

# ── 활동 종류 (§2.3) ─────────────────────────────────────────────
# 수행 주체가 다르다 — design/change/test 는 control_owner, *_assessment 는 assessor.
ACTIVITY_DESIGN = "design"                  # 설계
ACTIVITY_DESIGN_CHANGE = "design_change"    # 설계변경
ACTIVITY_DESIGN_ASSESSMENT = "design_assessment"      # 설계평가
ACTIVITY_TEST = "test"                      # 테스트(자체점검)
ACTIVITY_OPERATION_ASSESSMENT = "operation_assessment"  # 운영평가
ACTIVITY_KINDS = (
    ACTIVITY_DESIGN, ACTIVITY_DESIGN_CHANGE, ACTIVITY_DESIGN_ASSESSMENT,
    ACTIVITY_TEST, ACTIVITY_OPERATION_ASSESSMENT,
)

# 활동 → (수행 역할, 속한 회차 종류)
ACTIVITY_RULES = {
    ACTIVITY_DESIGN: ("control_owner", CYCLE_DESIGN),
    ACTIVITY_DESIGN_CHANGE: ("control_owner", CYCLE_DESIGN),
    ACTIVITY_DESIGN_ASSESSMENT: ("assessor", CYCLE_DESIGN),
    ACTIVITY_TEST: ("control_owner", CYCLE_OPERATION),
    ACTIVITY_OPERATION_ASSESSMENT: ("assessor", CYCLE_OPERATION),
}

# ── 승인 단계 (§2.5) ─────────────────────────────────────────────
APPROVAL_DEPT = "dept"            # 부서승인 — 정책 토글·스킵 대상
APPROVAL_ASSESSOR = "assessor"    # 평가자 승인
APPROVAL_STAGES = (APPROVAL_DEPT, APPROVAL_ASSESSOR)


class AssessmentCycle(AuditedBase):
    """평가 회차. `kind` 로 설계평가/운영평가를 가른다 — 두 종류는 독립이다."""
    __tablename__ = "assessment_cycles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "name", name="uq_assessment_cycles_kind_name"),
        # 복합 FK 참조 대상 (ADR-0030 §2.3)
        UniqueConstraint("id", "tenant_id", name="uq_assessment_cycles_id_tenant"),
    )

    kind: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    frequency: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    # ASSESSMENT_FREQUENCIES 참조 — 이 값과 일치하는 통제가 대상이 된다
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 평가 **대상 기간** — "언제를 평가하는가"
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    # 마감기한 — "언제까지 작업하는가". 대상 기간과 다른 개념이라 별도 필드다
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=CYCLE_OPEN, index=True)

    # ── 마감 (§2.5) ──
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # 미완 사유 — 미완 통제가 있는 채로 마감할 때 필수. 없으면 마감 자체가 거부된다
    incomplete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 최종승인 (§2.7) ──
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    closed_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[closed_by_id])
    approved_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[approved_by_id])


class CycleTarget(AuditedBase):
    """회차 대상 통제 **스냅샷**. 생성 시점의 대상을 고정한다(모듈 docstring 참조).

    `control_id` 에 FK 를 걸지 않는다 — baseline 유래면 `baseline_controls.id`,
    회사 add 면 `control_instances.id` 라 참조 테이블이 하나로 정해지지 않는다
    (정체성 id 규칙, ADR-0027). `role_assignments.target_id` 와 같은 사정이다.

    `control_code` 를 함께 저장한다. 스냅샷의 의미가 "그때 무엇이 대상이었는가" 이므로
    통제가 나중에 제외돼 resolver 결과에서 사라져도 목록이 읽혀야 한다.
    """
    __tablename__ = "cycle_targets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cycle_id", "control_id", name="uq_cycle_targets_pair"),
        ForeignKeyConstraint(
            ["cycle_id", "tenant_id"], ["assessment_cycles.id", "assessment_cycles.tenant_id"],
            name="fk_cycle_targets_cycle_tenant",
        ),
    )

    cycle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True  # FK 는 위 복합 FK
    )
    control_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    control_code: Mapped[str | None] = mapped_column(String(30), nullable=True)


class AssessmentActivity(AuditedBase):
    """활동 기록 — 설계·설계변경·설계평가·테스트·운영평가.

    **수행자와 수행 시각을 남긴다**(ADR-0032 §2.8). 역할 배정 이력은 관리하지 않는다 —
    감사가 묻는 것은 "1분기 평가를 누가 했는가"이고 그 답이 여기 있다.

    한 통제·한 회차에 같은 종류의 활동이 여러 번 기록될 수 있다(재수행·보완).
    유니크 제약을 두지 않는 이유다 — 마지막 것만 남기면 경위가 사라진다.
    """
    __tablename__ = "assessment_activities"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_assessment_activities_id_tenant"),
        ForeignKeyConstraint(
            ["cycle_id", "tenant_id"], ["assessment_cycles.id", "assessment_cycles.tenant_id"],
            name="fk_assessment_activities_cycle_tenant",
        ),
    )

    cycle_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    control_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    activity_kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    # ACTIVITY_KINDS 참조
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 수행자·수행시각 — 감사추적의 실체 (§2.8)
    performed_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    performed_by: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[performed_by_id])


class ActivityApproval(AuditedBase):
    """활동에 대한 승인 — 부서승인 / 평가자 승인.

    **최종승인은 여기 있지 않다.** 그것은 개별 통제가 아니라 **회차 전체**에 대한 것이라
    `AssessmentCycle.approved_at/by` 에 둔다(ADR-0032 §2.6).
    """
    __tablename__ = "activity_approvals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "activity_id", "stage", name="uq_activity_approvals_stage"),
        ForeignKeyConstraint(
            ["activity_id", "tenant_id"],
            ["assessment_activities.id", "assessment_activities.tenant_id"],
            name="fk_activity_approvals_activity_tenant",
        ),
    )

    activity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # APPROVAL_STAGES 참조
    approved_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    approved_by: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[approved_by_id])
