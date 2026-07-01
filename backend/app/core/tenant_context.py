"""멀티테넌시 자동 격리 엔진 (ADR-0025).

ADR-0020(제로 추상화)의 **명시적 예외** — 데이터 누출 방지가 추상화 최소화보다 우선한다.
각 쿼리에 `.filter(tenant_id == ...)` 를 수동으로 거는 방식은 금지(한 곳만 빠뜨려도 누출).
대신 SQLAlchemy 이벤트로 tenant_id 를 자동 주입/필터한다:

- 쓰기: before_flush → 신규 객체(TenantMixin)에 활성 tenant_id 자동 stamp
- 읽기: do_orm_execute + with_loader_criteria(TenantMixin) → 전 SELECT 자동 필터
  (관계 로딩에도 자동 전파됨)

활성 tenant 는 요청 단위 ContextVar 로 관리한다(get_current_user 가 검증 후 설정).
ContextVar 미설정(=시스템/부트스트랩/마이그레이션 맥락)이면 필터를 적용하지 않는다.
"""
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.models.base import TenantMixin

# 기본 tenant — 단일 회사(온프레/현 단계) 및 기존 데이터 귀속 대상. 고정 UUID.
# 주의: hex 가 전부 숫자인 UUID(예: ...0001)는 SQLite 의 "UUID"(NUMERIC affinity) 컬럼에서
# 정수로 강제 변환되어 테스트가 깨진다. 영문자가 포함된 고정값을 쓴다(Postgres는 무관).
DEFAULT_TENANT_ID = UUID("d0000000-0000-0000-0000-000000000001")
DEFAULT_TENANT_CODE = "DEFAULT"
DEFAULT_TENANT_NAME = "사이냅소프트"

# 요청 단위 활성 tenant. 미설정 시 None → 자동 필터/주입 비활성(시스템 맥락).
_active_tenant_id: ContextVar[UUID | None] = ContextVar("active_tenant_id", default=None)


def set_active_tenant(tenant_id: UUID | None):
    """활성 tenant 설정. 반환된 토큰으로 reset 가능."""
    return _active_tenant_id.set(tenant_id)


def get_active_tenant() -> UUID | None:
    return _active_tenant_id.get()


def reset_active_tenant(token) -> None:
    _active_tenant_id.reset(token)


@event.listens_for(Session, "before_flush")
def _stamp_tenant_on_insert(session: Session, flush_context, instances) -> None:
    """신규 비즈니스 객체에 활성 tenant_id 자동 주입 (수동 설정 시 보존)."""
    tid = get_active_tenant()
    if tid is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantMixin) and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tid


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(execute_state) -> None:
    """모든 ORM SELECT 에 활성 tenant 필터 자동 적용 (관계 로딩 포함, 자동 전파)."""
    if (
        not execute_state.is_select
        or execute_state.is_column_load
        or execute_state.is_relationship_load
    ):
        return
    tid = get_active_tenant()
    if tid is None:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.tenant_id == tid,
            include_aliases=True,
        )
    )
