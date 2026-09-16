from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditedBase


class UserRole(AuditedBase):
    """테넌트 단위 제도 운영 역할 (ADR-0031 §2.1·§3.1).

    **`users.role`(시스템 관리)과 다른 것이며 서로 참조하지 않는다**(§3.2).
    """

    __tablename__ = "user_roles"
    __table_args__ = (
        # 같은 사람에게 같은 역할이 2행 저장되면 1행을 지워도 역할이 남는다 —
        # 해제한 줄 알았는데 권한이 유지되는 상태가 되므로 DB 가 막는다(13.9-35 ④).
        #
        # **소프트 삭제라 부분 유니크여야 한다.** 평범한 유니크면 역할 해제 후
        # 재배정이 IntegrityError 로 터진다(해제 행이 남아 있어서). 재배정은 정상
        # 업무다. 선례: `models/org.py` `uq_user_departments_one_primary`.
        Index(
            "uq_user_roles_active_pair", "tenant_id", "user_id", "role_name",
            unique=True, sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("NOT is_deleted"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(100), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
