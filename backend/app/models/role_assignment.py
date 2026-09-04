"""역할 배정·정책 모델 — ADR-0031 §2.2~2.6, 3-1.

**역할은 사람이 아니라 통제에 붙는다**(§2.2). 같은 사람이 통제 A에서는 통제책임자,
통제 B에서는 평가자가 될 수 있어야 한다 — 관리부서가 4명인 회사에서 상호 배정은
불가피하고 국내 실무에서 허용된다. 역할을 사람 속성으로 두면 이 구조를 표현할 수 없다.

**배정은 프로세스 기본값 + 통제별 예외다**(§2.3). 통제 93건 × 역할 3종을 개별 배정하면
279회 조작이 된다. baseline/overlay 와 같은 원칙 — **저장은 차이만, 조회는 해석**
(ADR-0029 §2.1·§2.2).

**이해상충은 막지 않고 경고 + 사유를 기록한다**(§2.5). 막으면 중소기업이 시스템을
쓸 수 없고, 조용히 허용하면 감사에서 지적된다. 사유 기록이 보완통제 증적이 된다.

테넌트 단위 역할 5종(`icfr_manager`/`ceo`/`auditor`/`external_auditor`/`sys_admin`)은
**여기가 아니라 기존 `user_roles` 에 담는다**(ADR-0031 §3.1). 이 모듈은 통제 단위
역할만 다룬다.
"""
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditedBase

# ── 통제 단위 역할 (ADR-0031 §2.3) ────────────────────────────────
# dept_approver 는 통제책임자의 주 소속 부서 책임자에서 **유도**되며, 배정 레코드가
# 없어도 값이 나온다. 통제별 개별 지정이 있으면 그것이 유도값을 이긴다.
ROLE_CONTROL_OWNER = "control_owner"
ROLE_DEPT_APPROVER = "dept_approver"
ROLE_ASSESSOR = "assessor"
CONTROL_ROLES = (ROLE_CONTROL_OWNER, ROLE_DEPT_APPROVER, ROLE_ASSESSOR)

# ── 배정 범위 ────────────────────────────────────────────────────
# 같은 테이블에 프로세스 기본값과 통제별 예외를 함께 담고 scope 로 구분한다.
# 테이블을 둘로 나누면 해석 로직이 두 벌이 된다.
SCOPE_PROCESS = "process"
SCOPE_CONTROL = "control"
ASSIGNMENT_SCOPES = (SCOPE_PROCESS, SCOPE_CONTROL)


class RoleAssignment(AuditedBase):
    """통제 단위 역할 배정. `scope` 로 프로세스 기본값과 통제별 예외를 구분한다.

    - `scope='process'` → `target_id` 는 프로세스 정체성 id. 그 프로세스 하위 통제의 기본값
    - `scope='control'` → `target_id` 는 통제 정체성 id. 해당 통제에만 적용, 기본값을 이긴다

    **`target_id` 에 FK 를 걸지 않는다.** 대상이 baseline 유래면 `baseline_processes.id`,
    회사 add 면 `process_instances.id` 라 참조 테이블이 하나로 정해지지 않는다
    (resolver 의 "정체성 id" 규칙 — ADR-0027). 존재 검증은 핸들러가 resolver 결과와
    대조해서 한다. 이 사정을 모르고 FK 를 추가하면 add 항목 배정이 막힌다.
    """
    __tablename__ = "role_assignments"
    __table_args__ = (
        # 한 대상·한 역할당 1건. 같은 통제에 통제책임자가 둘일 수 없다.
        UniqueConstraint(
            "tenant_id", "scope", "target_id", "role_name",
            name="uq_role_assignments_target_role",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_role_assignments_id_tenant"),
    )

    scope: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # ASSIGNMENT_SCOPES 참조 (process | control)
    target_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    role_name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # CONTROL_ROLES 참조
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # noqa: F821


class ConflictAcknowledgement(AuditedBase):
    """이해상충 승인 사유 (§2.5). **이력으로 보존한다 — 보완통제 증적이다.**

    판정은 통제 단위다. "이 통제에서 이 조합인가"만 본다 — 사람 단위로 보면
    상호 배정이 불가피한 중소기업에서 전부 걸린다.

    배정이 바뀌어도 과거 사유를 지우지 않는다. 감사에서 "그때 왜 겸직을 허용했는가"를
    물으면 이 기록이 답이 된다.
    """
    __tablename__ = "conflict_acknowledgements"

    scope: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    target_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    # 충돌 조합 — "control_owner=assessor" 형태
    conflict_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # noqa: F821


class TenantPolicy(AuditedBase):
    """테넌트 정책 설정 (§2.6). `icfr_manager` 만 변경할 수 있다.

    **key-value 로 둔다.** 3-2·3-3 에서 항목이 추가되므로(증빙 편집 토글, 보존기간)
    컬럼을 늘려가면 그때마다 마이그레이션이 필요하다 — 스키마 변경은 횟수 자체가
    위험이다(ADR-0030 경험). 지금 필요 없는 컬럼을 미리 만들지도 않는다.

    값 해석은 소비하는 쪽이 한다. 미설정 키는 기본값을 쓴다(핸들러가 정의).
    """
    __tablename__ = "tenant_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_key", name="uq_tenant_policies_key"),
    )

    policy_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    policy_value: Mapped[str] = mapped_column(String(200), nullable=False)


# ── 이해상충 조합 (§2.5) ──────────────────────────────────────────
# (역할A, 역할B) — 같은 사람이 한 통제에서 두 역할을 겸하면 경고.
CONFLICT_PAIRS = (
    (ROLE_CONTROL_OWNER, ROLE_ASSESSOR),
    (ROLE_CONTROL_OWNER, ROLE_DEPT_APPROVER),
)

# 계층을 넘는 조합 — 통제 단위 assessor 와 **테넌트 단위** icfr_manager 다.
# icfr_manager 는 role_assignments 가 아니라 user_roles 에 있으므로(ADR-0031 §3.1)
# 판정 시 그쪽을 함께 읽어야 한다. 위 두 조합과 검사 방식이 다르니 분리해 둔다.
ROLE_ICFR_MANAGER = "icfr_manager"
ROLE_EXTERNAL_AUDITOR = "external_auditor"
CROSS_LAYER_CONFLICT_PAIRS = (
    (ROLE_ASSESSOR, ROLE_ICFR_MANAGER),
)

# 정책 키 — 금지로 켜면 저장 자체를 거부한다(409). 기본은 허용(경고+사유).
POLICY_DEPT_APPROVAL_ENABLED = "dept_approval_enabled"


def conflict_key(role_a: str, role_b: str) -> str:
    """충돌 조합 키. 순서를 고정해 같은 조합이 두 문자열로 갈리지 않게 한다."""
    a, b = sorted((role_a, role_b))
    return f"{a}={b}"


def conflict_policy_key(role_a: str, role_b: str) -> str:
    """조합별 금지 토글의 정책 키."""
    return f"conflict_{conflict_key(role_a, role_b).replace('=', '_')}_blocked"
