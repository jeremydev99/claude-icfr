from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.role_assignment import LEGACY_TENANT_ROLES, TENANT_ROLES


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


def _validate_tenant_role(value: str | None) -> str | None:
    """신규 배정은 ADR-0031 §2.1 테넌트 역할 5종만 허용한다 (13.9-35 ③).

    **목록은 `models/role_assignment.TENANT_ROLES` 하나뿐이다** — 겸직 판정과
    배정 검증이 다른 목록을 보면 한쪽만 고쳐졌을 때 알 수 없다.

    스키마에서 막으므로 거부는 FastAPI 규약대로 **422** 이고, 엔드포인트 3곳에
    검증이 흩어지지 않는다. 오타(`icfr_mananger`)가 201 로 저장된 뒤 어떤 판정에도
    걸리지 않아 조용히 무효가 되던 상태를 막는 것이 목적이다.

    구 3역할은 **읽기만 허용**한다 — `UserRoleRead` 는 이 검증을 쓰지 않으므로
    기존 행 조회는 그대로 동작하고, 신규 배정 경로만 막힌다(13.9-24).
    """
    if value is None or value in TENANT_ROLES:
        return value
    allowed = ", ".join(TENANT_ROLES)
    if value in LEGACY_TENANT_ROLES:
        raise ValueError(
            f"구 역할명 '{value}' 은 신규 배정할 수 없습니다. 허용: {allowed}"
        )
    raise ValueError(f"허용되지 않는 역할명 '{value}'. 허용: {allowed}")


class UserRoleBase(BaseModel):
    user_id: UUID
    role_name: str = Field(min_length=1, max_length=50)
    scope: str | None = None

class UserRoleCreate(UserRoleBase):
    check_role_name = field_validator("role_name")(_validate_tenant_role)

class UserRoleUpdate(BaseModel):
    role_name: str | None = Field(None, min_length=1, max_length=50)
    scope: str | None = None

    check_role_name = field_validator("role_name")(_validate_tenant_role)

class UserRoleRead(UserRoleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
