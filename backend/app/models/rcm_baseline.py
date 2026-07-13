"""RCM baseline/instance 모델 (ADR-0027, 2-A-1).

- BaselineControl: 전역 표준 통제(basic-perfect의 그릇). tenant 비종속 → IdentityBase.
- ControlInstance: 회사별 결정(adopt/exclude/override/add). AuditedBase → tenant_id 자동.
  override 필드는 baseline 전 필드의 nullable 미러링 — NULL=baseline 따름, 값=override.
  (ADR-0027 필드 diff 방식 — JSON 아님. 정렬·검색·타입안전 유지)

기존 controls 테이블은 미변경. 이관은 2-A-2, 조회 전환은 2-A-3.

risk_id 결정(명세 §1 위임사항):
- baseline.risk_id 는 FK 없는 nullable UUID — 전역 테이블이 tenant 종속 risks 를
  FK 참조하면 격리 위반(다른 tenant 맥락에서 자동필터에 걸려 참조가 깨짐). 2-B에서
  baseline_risks 신설 시 FK 전환.
- instance.risk_id 는 FK→risks.id nullable — instance 는 tenant 종속이라 자기 tenant 의
  risk 참조가 정합.
"""
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import IdentityBase, AuditedBase


class BaselineControl(IdentityBase):
    """표준 통제 (전역 — 모든 tenant 공통). code 전역 unique."""
    __tablename__ = "baseline_controls"

    # 기본 식별자 — Control 미러링
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    # FK 없음 — 상단 docstring 의 risk_id 결정 참조 (2-B baseline_risks 에서 FK 전환)

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

    instances: Mapped[list["ControlInstance"]] = relationship(
        "ControlInstance", back_populates="baseline_control"
    )


class ControlInstance(AuditedBase):
    """회사별 통제 결정. action 별 데이터 규칙:

    - adopt:    baseline_control_id 채움, override 필드 전부 NULL
    - exclude:  baseline_control_id 채움, override 필드 전부 NULL (제외 표시)
    - override: baseline_control_id 채움, 변경 필드만 값 채움
    - add:      baseline_control_id NULL, 자체 필드 전부 채움
    """
    __tablename__ = "control_instances"
    __table_args__ = (
        # instance 자체 code (add·override 시). NULL 다수 허용(adopt/exclude).
        UniqueConstraint("tenant_id", "code", name="uq_control_instances_tenant_code"),
        # 한 tenant 가 같은 baseline 에 두 개의 결정을 갖는 모순 차단 (NULL=add 는 다수 허용).
        UniqueConstraint("tenant_id", "baseline_control_id", name="uq_control_instances_tenant_baseline"),
        Index("ix_control_instances_code", "code"),
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
    risk_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("risks.id"), nullable=True, index=True
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
