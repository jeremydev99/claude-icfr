"""RCM baseline/instance 모델 (ADR-0027, 2-A-1 + 2-B-1).

- BaselineControl: 전역 표준 통제(basic-perfect의 그릇). tenant 비종속 → IdentityBase.
- ControlInstance: 회사별 결정(adopt/exclude/override/add). AuditedBase → tenant_id 자동.
  override 필드는 baseline 전 필드의 nullable 미러링 — NULL=baseline 따름, 값=override.
  (ADR-0027 필드 diff 방식 — JSON 아님. 정렬·검색·타입안전 유지)
- 2-B-1 상위 계층: BaselineProcess/BaselineSubProcess/BaselineRisk/BaselineRiskCategory —
  전부 전역(IdentityBase)이라 baseline_controls→baseline_risks→baseline_sub_processes→
  baseline_processes FK 체인이 tenant 필터에 걸리지 않는다.

기존 processes/sub_processes/risks/risk_categories/controls 테이블은 미변경(병행 구축).
이관은 2-A-2, 조회 전환은 2-A-3.

risk_id 결정:
- baseline.risk_id 는 FK→baseline_risks.id nullable — 2-A-1의 "2-B에서 FK 전환" 위임 이행.
  nullable 은 이관(2-A-2) 전까지 유지, 이관 후 NOT NULL 검토.
- instance 의 상위 참조는 이중 nullable FK (2-B-2) — <상위>_baseline_id(baseline 상위 밑)
  / <상위>_instance_id(회사가 add 한 상위 밑). 둘 다 NULL=baseline 상위 따름,
  둘 다 non-NULL 은 CheckConstraint 로 차단. override 된 상위의 정체성은 여전히 baseline
  이므로 baseline_id 쪽을 쓴다. ControlInstance.risk_id(FK→risks)도 같은 방식으로 전환됨.

RiskCategory(어서션)는 baseline만 두고 instance 미도입 — 제도 고정 개념(회계감사기준),
회사별 목록 변형 case 희박. 필요 시 후속에서 instance 테이블만 추가하면 됨.
"""
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Boolean, ForeignKey, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import IdentityBase, AuditedBase


class BaselineProcess(IdentityBase):
    """표준 프로세스 (전역). Process 미러링."""
    __tablename__ = "baseline_processes"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    sub_processes: Mapped[list["BaselineSubProcess"]] = relationship(
        "BaselineSubProcess", back_populates="process"
    )


class BaselineSubProcess(IdentityBase):
    """표준 하위프로세스 (전역). SubProcess 미러링."""
    __tablename__ = "baseline_sub_processes"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    process_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_processes.id"), nullable=False, index=True
    )

    process: Mapped["BaselineProcess"] = relationship(
        "BaselineProcess", back_populates="sub_processes"
    )
    risks: Mapped[list["BaselineRisk"]] = relationship(
        "BaselineRisk", back_populates="sub_process"
    )


class BaselineRisk(IdentityBase):
    """표준 위험 (전역). Risk 미러링."""
    __tablename__ = "baseline_risks"

    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_level: Mapped[str] = mapped_column(String(5), nullable=False, default="LR")
    # "LR" (Low), "MR" (Medium), "HR" (High), "SR" (Significant)
    sub_process_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_sub_processes.id"), nullable=False, index=True
    )

    sub_process: Mapped["BaselineSubProcess"] = relationship(
        "BaselineSubProcess", back_populates="risks"
    )
    controls: Mapped[list["BaselineControl"]] = relationship(
        "BaselineControl", back_populates="risk"
    )


class BaselineRiskCategory(IdentityBase):
    """표준 경영자 주장 분류 (전역, Assertion). RiskCategory 미러링. baseline-only — 상단 docstring 참조."""
    __tablename__ = "baseline_risk_categories"

    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class BaselineControl(IdentityBase):
    """표준 통제 (전역 — 모든 tenant 공통). code 전역 unique."""
    __tablename__ = "baseline_controls"

    # 기본 식별자 — Control 미러링
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_risks.id"), nullable=True, index=True
    )

    # 그룹 2: 담당자·목적
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 그룹 3: 통제 성격
    is_key_control: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preventive_detective: Mapped[str] = mapped_column(String(2), nullable=False, default="P")
    auto_manual: Mapped[str] = mapped_column(String(2), nullable=False, default="M")

    # 그룹 3: 통제 활동 유형 6종
    activity_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_verification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_physical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_master_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_reconciliation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_supervision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 그룹 5: 통제 환경·시스템
    related_accounts: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency: Mapped[str] = mapped_column(String(2), nullable=False, default="A")
    ipe_relevant: Mapped[str] = mapped_column(String(5), nullable=False, default="N/A")
    related_systems: Mapped[str | None] = mapped_column(Text, nullable=True)
    euc_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    risk: Mapped["BaselineRisk | None"] = relationship(
        "BaselineRisk", back_populates="controls"
    )
    instances: Mapped[list["ControlInstance"]] = relationship(
        "ControlInstance", back_populates="baseline_control"
    )


class ProcessInstance(AuditedBase):
    """회사별 프로세스 결정 (최상위 계층 — 상위 참조 없음). action 별 데이터 규칙:

    - adopt:    baseline_process_id 채움, 미러링 필드 전부 NULL
    - exclude:  baseline_process_id 채움, 나머지 NULL (제외 표시)
    - override: baseline_process_id 채움, 변경 필드만 값 채움
    - add:      baseline_process_id NULL, 자체 필드 채움
    """
    __tablename__ = "process_instances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_process_instances_tenant_code"),
        UniqueConstraint("tenant_id", "baseline_process_id", name="uq_process_instances_tenant_baseline"),
        Index("ix_process_instances_code", "code"),
    )

    baseline_process_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_processes.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    # "adopt" | "exclude" | "override" | "add"

    # ── baseline_processes 필드의 nullable 미러링 (NULL=baseline 따름) ──
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    baseline_process: Mapped["BaselineProcess | None"] = relationship("BaselineProcess")


class SubProcessInstance(AuditedBase):
    """회사별 하위프로세스 결정. action 별 데이터 규칙:

    - adopt:    baseline_sub_process_id 채움, 미러링 필드 전부 NULL, 상위 참조 NULL
    - exclude:  baseline_sub_process_id 채움, 나머지 NULL (제외 표시)
    - override: baseline_sub_process_id 채움, 변경 필드만 값. 상위를 바꿨으면 상위 참조 하나 채움
    - add:      baseline_sub_process_id NULL, 자체 필드 채움, 상위 참조 하나 필수(앱 레벨 검증)

    상위 참조(이중 nullable FK) 정합 규칙:
    - override 된 상위의 정체성은 여전히 baseline → process_baseline_id 사용.
      process_instance_id 는 회사가 add 한 상위 밑에서만 사용.
    - 둘 다 NULL = baseline 의 상위를 그대로 따름.
    - 둘 다 non-NULL 금지 — CheckConstraint 로 차단.
    """
    __tablename__ = "sub_process_instances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sub_process_instances_tenant_code"),
        UniqueConstraint("tenant_id", "baseline_sub_process_id", name="uq_sub_process_instances_tenant_baseline"),
        Index("ix_sub_process_instances_code", "code"),
        CheckConstraint(
            "NOT (process_baseline_id IS NOT NULL AND process_instance_id IS NOT NULL)",
            name="ck_sub_process_instances_single_parent",
        ),
    )

    baseline_sub_process_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_sub_processes.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)

    # ── baseline_sub_processes 필드의 nullable 미러링 ──
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── 상위 참조 (이중 nullable FK — 상단 docstring 정합 규칙 참조) ──
    process_baseline_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_processes.id"), nullable=True, index=True
    )
    process_instance_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("process_instances.id"), nullable=True, index=True
    )

    baseline_sub_process: Mapped["BaselineSubProcess | None"] = relationship("BaselineSubProcess")


class RiskInstance(AuditedBase):
    """회사별 위험 결정. action 별 데이터 규칙·상위 참조 정합 규칙은 SubProcessInstance 와 동일
    (상위 = sub_process)."""
    __tablename__ = "risk_instances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_risk_instances_tenant_code"),
        UniqueConstraint("tenant_id", "baseline_risk_id", name="uq_risk_instances_tenant_baseline"),
        Index("ix_risk_instances_code", "code"),
        CheckConstraint(
            "NOT (sub_process_baseline_id IS NOT NULL AND sub_process_instance_id IS NOT NULL)",
            name="ck_risk_instances_single_parent",
        ),
    )

    baseline_risk_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_risks.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)

    # ── baseline_risks 필드의 nullable 미러링 ──
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_level: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # ── 상위 참조 (이중 nullable FK) ──
    sub_process_baseline_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_sub_processes.id"), nullable=True, index=True
    )
    sub_process_instance_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("sub_process_instances.id"), nullable=True, index=True
    )

    baseline_risk: Mapped["BaselineRisk | None"] = relationship("BaselineRisk")


class ControlInstance(AuditedBase):
    """회사별 통제 결정. action 별 데이터 규칙:

    - adopt:    baseline_control_id 채움, override 필드 전부 NULL
    - exclude:  baseline_control_id 채움, override 필드 전부 NULL (제외 표시)
    - override: baseline_control_id 채움, 변경 필드만 값 채움. 상위(risk)를 바꿨으면 상위 참조 하나 채움
    - add:      baseline_control_id NULL, 자체 필드 전부 채움, 상위 참조 하나 필수(앱 레벨 검증)

    상위 참조(risk_baseline_id/risk_instance_id) 정합 규칙은 SubProcessInstance 와 동일.
    (2-B-2 에서 risk_id(FK→risks) 를 이중 FK 로 전환 — 계층 참조 방식 통일)
    """
    __tablename__ = "control_instances"
    __table_args__ = (
        # instance 자체 code (add·override 시). NULL 다수 허용(adopt/exclude).
        UniqueConstraint("tenant_id", "code", name="uq_control_instances_tenant_code"),
        # 한 tenant 가 같은 baseline 에 두 개의 결정을 갖는 모순 차단 (NULL=add 는 다수 허용).
        UniqueConstraint("tenant_id", "baseline_control_id", name="uq_control_instances_tenant_baseline"),
        Index("ix_control_instances_code", "code"),
        CheckConstraint(
            "NOT (risk_baseline_id IS NOT NULL AND risk_instance_id IS NOT NULL)",
            name="ck_control_instances_single_parent",
        ),
    )

    baseline_control_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_controls.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    # "adopt" | "exclude" | "override" | "add"

    # ── 이하 baseline_controls 전 필드의 nullable 미러링 (NULL=baseline 따름) ──
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 상위 참조 (이중 nullable FK — 2-B-2 에서 risk_id(FK→risks) 대체) ──
    risk_baseline_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("baseline_risks.id"), nullable=True, index=True
    )
    risk_instance_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("risk_instances.id"), nullable=True, index=True
    )

    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    is_key_control: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    preventive_detective: Mapped[str | None] = mapped_column(String(2), nullable=True)
    auto_manual: Mapped[str | None] = mapped_column(String(2), nullable=True)

    activity_approval: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    activity_verification: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    activity_physical: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    activity_master_data: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    activity_reconciliation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    activity_supervision: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    related_accounts: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ipe_relevant: Mapped[str | None] = mapped_column(String(5), nullable=True)
    related_systems: Mapped[str | None] = mapped_column(Text, nullable=True)
    euc_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    baseline_control: Mapped["BaselineControl | None"] = relationship(
        "BaselineControl", back_populates="instances"
    )
