"""조직(부서) 모델 — ADR-0031 §2.8, 3-1.

**회사 조직도의 스냅샷이지 원본이 아니다.** 원본은 인사시스템이고, 여기서는
내부회계전담부서 담당자가 현황을 옮겨 담는다. 발령·겸직·개편 같은 인사 로직은
구현하지 않는다.

계층은 `parent_id` 컬럼으로 **개념만 보존**하고 평면으로 운영한다(초기 전부 NULL).
조회·배정 로직은 평면 목록을 전제로 쓴다. 본부·팀 계층이 필요해지면 값만 채우면 된다.
근거: 나중에 컬럼을 추가하려면 마이그레이션이 또 필요하고, **스키마 변경은 횟수 자체가
위험**이다(ADR-0030 경험).

테넌트 격리는 `AuditedBase`(TenantMixin) 자동 격리 + 복합 FK 로 DB 가 보장한다
(ADR-0025 / ADR-0030 §2.3). **수동 tenant 필터를 걸지 않는다.**
"""
from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditedBase


class Department(AuditedBase):
    """부서 — 팀장급이 책임지는 회사의 기능 조직 단위.

    예: 자금팀, 회계팀, 영업1팀, 개발1팀, 내부회계전담팀, 개발본부 직속부서.

    **`manager_id` 는 중복을 허용한다** — 본부장이 팀장 퇴사 시 팀장을 겸임하는 경우가
    실재한다. 한 사람이 여러 부서의 책임자가 될 수 있다.
    """
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_departments_tenant_name"),
        # 복합 FK 참조 대상 (ADR-0030 §2.3) — 하위 테이블이 (id, tenant_id) 로 가리킨다
        UniqueConstraint("id", "tenant_id", name="uq_departments_id_tenant"),
        # 자기참조도 테넌트를 넘지 못한다 — 계층을 쓰게 되는 시점에 이미 막혀 있어야 한다
        ForeignKeyConstraint(
            ["parent_id", "tenant_id"], ["departments.id", "departments.tenant_id"],
            name="fk_departments_parent_tenant",
        ),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    manager_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    # 계층은 개념만 보존 — 초기 전부 NULL, 조회는 평면 전제 (§2.8)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True  # FK 는 위 복합 FK
    )
    # 인사시스템 연동 키 — 현재 미사용. 연동 시점에 매핑 키가 된다 (§2.8)
    external_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    manager: Mapped["User | None"] = relationship("User", foreign_keys=[manager_id])  # noqa: F821


class UserDepartment(AuditedBase):
    """사용자 ↔ 부서 소속. **한 사람이 여러 부서에 소속될 수 있다.**

    근거: 회계팀 직원이 내부회계전담팀을 겸하는 등 중소기업에서 실재한다.

    **주 소속(`is_primary`)은 사용자당 정확히 하나다.** `dept_approver` 유도의
    기준이 되므로(§2.3) 둘이면 어느 부서 책임자를 쓸지 정할 수 없다.
    DB 부분 인덱스로 강제한다 — 애플리케이션 검증만 두면 한 곳만 빠뜨려도 뚫린다.
    """
    __tablename__ = "user_departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "department_id", name="uq_user_departments_pair"),
        # 주 소속은 사용자당 1건 — 부분 유니크 인덱스로 DB 가 강제한다.
        # 앱 검증만 두면 한 경로만 빠뜨려도 뚫린다(회귀 방지 원칙: 판별은 구조로).
        Index(
            "uq_user_departments_one_primary", "tenant_id", "user_id",
            unique=True, sqlite_where=text("is_primary = 1"),
            postgresql_where=text("is_primary"),
        ),
        ForeignKeyConstraint(
            ["department_id", "tenant_id"], ["departments.id", "departments.tenant_id"],
            name="fk_user_departments_department_tenant",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    department_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True  # FK 는 위 복합 FK
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # noqa: F821
    department: Mapped["Department"] = relationship("Department", foreign_keys=[department_id])
