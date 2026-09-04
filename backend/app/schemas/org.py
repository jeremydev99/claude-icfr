"""부서·역할 배정 스키마 — 3-1.

계약은 기존 RCM API 규약을 따른다(`docs/api/rcm-hierarchy-contract.md`).
목록 봉투는 `{"items": [...], "total": int, "skip": int, "limit": int}`,
PATCH 는 전 필드 optional + `exclude_unset` 판별.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Department ────────────────────────────────────────────

class DepartmentBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    manager_id: UUID | None = None
    # 계층은 개념만 보존 — 초기 전부 NULL (ADR-0031 §2.8)
    parent_id: UUID | None = None
    # 인사시스템 연동 키. 현재 미사용
    external_code: str | None = Field(None, max_length=50)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    manager_id: UUID | None = None
    parent_id: UUID | None = None
    external_code: str | None = Field(None, max_length=50)


class DepartmentRead(DepartmentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    # 표시용 파생값 — 화면이 id 로 다시 조회하지 않도록
    manager_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ── UserDepartment (소속) ─────────────────────────────────

class UserDepartmentCreate(BaseModel):
    user_id: UUID
    department_id: UUID
    is_primary: bool = False


class UserDepartmentUpdate(BaseModel):
    is_primary: bool | None = None


class UserDepartmentRead(BaseModel):
    id: UUID
    user_id: UUID
    department_id: UUID
    is_primary: bool
    created_at: datetime
    updated_at: datetime
    user_name: str | None = None
    department_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ── 역할 배정 ─────────────────────────────────────────────

class RoleAssignmentCreate(BaseModel):
    scope: str = Field(pattern="^(process|control)$")
    target_id: UUID
    role_name: str = Field(pattern="^(control_owner|dept_approver|assessor)$")
    user_id: UUID
    # 이해상충 조합이면 사유가 필수다. 없으면 409 (ADR-0031 §2.5)
    conflict_reason: str | None = None


class RoleAssignmentRead(BaseModel):
    id: UUID | None = None            # 유도값(dept_approver)은 레코드가 없어 None
    scope: str
    target_id: UUID
    role_name: str
    user_id: UUID
    user_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ResolvedRole(BaseModel):
    """통제 하나에 대해 해석된 역할 1건.

    `source` 가 계약의 핵심이다 — 이 값이 어디서 왔는지 FE 가 구분할 수 있어야
    "이 통제만 예외 지정된 상태"를 표시할 수 있다(RCM 의 source envelope 과 같은 개념).
    """
    role_name: str
    user_id: UUID | None = None
    user_name: str | None = None
    # "control"(통제별 지정) | "process"(프로세스 기본값) | "derived"(부서 책임자 유도) | "none"
    source: str
    # 기본값 유래면 그 프로세스 id, 유도면 부서 id
    source_id: UUID | None = None


class ControlRolesRead(BaseModel):
    """통제 1건의 역할 해석 결과 + 배정 참고 정보."""
    control_id: UUID
    control_code: str | None = None
    process_id: UUID | None = None
    # ADR-0031 §2.4 — 이관하지 않고 참고 정보로 함께 싣는다.
    # "문서상 수행자"와 실제 배정이 어긋나면 그 자체가 검토 대상이 된다.
    owner_name: str | None = None
    roles: list[ResolvedRole]
    conflicts: list[str] = []
    # 부서승인 단계가 성립하지 않는가 — 통제책임자가 곧 부서 책임자인 경우.
    # **이해상충이 아니다**(2026-09-04 정정, ADR-0031 §2.4). 승인 단계가 없는 것이지
    # 겸직이 아니므로 `conflicts` 에 넣지 않고 별도로 표시한다.
    #
    # `source` 에 "skipped" 를 넣지 않은 이유 — `source` 는 "값이 어디서 왔는가"라는
    # 단일 의미이고 스킵은 상태다. 섞으면 RCM source envelope 과도 개념이 어긋나고,
    # 스킵일 때 유도된 부서 책임자가 누구인지 표현할 자리가 없어진다.
    # 스킵이어도 `roles[]` 의 dept_approver 는 그대로 남으며 user_id 는 control_owner
    # 와 같다 — 별도 승인자가 아니라는 뜻이다.
    dept_approval_skipped: bool = False


# ── 정책 ──────────────────────────────────────────────────

class TenantPolicyUpsert(BaseModel):
    policy_key: str = Field(min_length=1, max_length=60)
    policy_value: str = Field(min_length=1, max_length=200)


class TenantPolicyRead(BaseModel):
    id: UUID
    policy_key: str
    policy_value: str
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
