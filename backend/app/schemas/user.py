from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBrief(BaseModel):
    """이력·감사 응답용 사용자 간략 정보 (id + display_name=실명).

    test_module·remediation 양쪽 history 응답에서 공통 사용 (작업: 감사 일관화).
    단순 데이터 스키마이므로 공통화는 ADR-0020 추상화 위반 아님.
    """
    id: UUID
    display_name: str

    model_config = {"from_attributes": True}


class TenantAccessRead(BaseModel):
    """/me 응답용 — 접근 가능한 tenant + 해당 tenant에서의 역할 (UserTenantAccess.role)."""
    id: UUID
    name: str
    code: str
    role: str

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    """`/me` 응답.

    **`role` 이라는 이름이 세 곳에서 다른 의미로 쓰인다**(13.9-23·24). 구분:

    | 필드 | 출처 | 의미 |
    |---|---|---|
    | `role` | `users.role` | **시스템 관리 권한**. `require_admin` 전용(사용자 CRUD 4곳) |
    | `tenants[].role` | `user_tenant_access.role` | 테넌트 **접근** 권한. 판정에 쓰는 코드 0건(13.9-23) |
    | `tenant_roles` | `user_roles` | **제도 운영 역할**(ADR-0031 §2.1). 권한 판정의 근거 |

    `tenant_roles`·`can_write` 는 **활성 테넌트 기준**이며 `active_tenant_id` 와 같은
    맥락이라 함께 top-level 에 둔다. `tenants[]` 안에 넣으려면 테넌트마다 활성
    컨텍스트를 바꿔가며 `user_roles` 를 읽어야 하는데, 그 방식은 ADR-0025 자동 격리가
    막으려던 수동 교차 조회다.
    """
    id: UUID
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    tenants: list[TenantAccessRead] = []
    active_tenant_id: UUID | None = None
    # 활성 테넌트에서 이 사용자가 가진 제도 운영 역할 (user_roles).
    # FE 는 "왜 못 쓰는지"를 안내할 때 이 값을 본다.
    tenant_roles: list[str] = []
    # 제도 운영 데이터를 쓸 수 있는가. **판정은 core/permissions.can_write 하나뿐**이며
    # require_write 와 같은 함수를 쓴다 — FE 가 규칙을 다시 구현하면 어긋난다.
    # 버튼 숨김은 이 값, 안내 문구는 tenant_roles 로 판단한다.
    can_write: bool = True

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    role: str = "user"


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordResetRequest(BaseModel):
    """관리자 비밀번호 리셋 — old 검증 없이 재설정 (관리자 전용)."""
    new_password: str = Field(min_length=8)
