"""감사 컬럼 행위자 컨텍스트 (ADR-0036, 13.9-51).

`created_by`·`updated_by`·`deleted_by` 에 들어갈 "누가"를 요청·작업 단위로 들고 다닌다.
tenant_id 자동 격리(ADR-0025, `core/tenant_context.py`)와 같은 구조다 —
**핸들러가 감사 컬럼을 직접 대입하지 않는다**(한 곳만 빠뜨려도 흔적이 비기 때문).

행위자 값은 두 종류뿐이다.
- 사용자: `str(user.id)` — `get_current_user` 가 요청마다 설정한다. 이메일·이름은 쓰지 않는다.
- 시스템: `system:<출처>` — 사용자 없는 쓰기(bootstrap·시드·이관)가 **명시해야만** 기록된다.
  `unknown` 같은 기본값은 두지 않는다. 지정이 없으면 기록 단계에서 실패시킨다(fail-closed).

`session.info["system_actor"]` 는 **테스트 전용 경로**다 — 직접 삽입용 테스트 세션에만 붙인다.
ContextVar 는 테스트 스레드에서 TestClient 요청 안으로 전파되므로, 테스트 행위자를
ContextVar 로 걸면 API 경로의 행위자 누락이 테스트에서 가려진다. 운영 `SessionLocal` 에는
붙이지 않으며 테스트로 고정한다(`tests/test_audit_columns.py`).
"""
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy.orm import Session

SYSTEM_ACTOR_PATTERN = re.compile(r"^system:[a-z][a-z0-9-]*$")
SESSION_INFO_ACTOR_KEY = "system_actor"

# 시스템 행위자 — 출처별로 나눈다(어느 경로가 쓴 행인지 컬럼만으로 알 수 있게).
SYSTEM_BOOTSTRAP = "system:bootstrap"
SYSTEM_SEED_USERS = "system:seed-users"
SYSTEM_SEED_BASELINE = "system:seed-baseline"
SYSTEM_SEED_EUC_IUC = "system:seed-euc-iuc"
SYSTEM_SEED_SCOPING_TEMPLATE = "system:seed-scoping-template"
SYSTEM_MIGRATION_RCM_BASELINE = "system:migration-rcm-baseline"
SYSTEM_TEST = "system:test"

# 요청·작업 단위 행위자. 미설정 시 None → 감사 대상 쓰기는 실패한다.
_current_actor: ContextVar[str | None] = ContextVar("current_actor", default=None)


def _validate_system_actor(actor: str) -> str:
    if not isinstance(actor, str) or not SYSTEM_ACTOR_PATTERN.match(actor):
        raise ValueError(f"시스템 행위자 형식은 system:<출처> 이어야 합니다: {actor!r}")
    return actor


def set_user_actor(user_id: UUID):
    """요청 사용자를 행위자로 설정. 반환된 토큰으로 reset 가능."""
    return _current_actor.set(str(user_id))


def get_current_actor() -> str | None:
    return _current_actor.get()


def reset_current_actor(token) -> None:
    _current_actor.reset(token)


@contextmanager
def system_actor(actor: str) -> Iterator[None]:
    """사용자 없는 쓰기 블록에 시스템 행위자를 명시한다. 블록을 벗어나면 원래 값으로 돌아간다."""
    token = _current_actor.set(_validate_system_actor(actor))
    try:
        yield
    finally:
        _current_actor.reset(token)


def resolve_actor(session: Session) -> str | None:
    """flush 시점의 행위자. ContextVar(사용자·system_actor 블록) → 테스트 세션 info 순."""
    actor = get_current_actor()
    if actor:
        return actor
    info_actor = session.info.get(SESSION_INFO_ACTOR_KEY)
    if info_actor is not None:
        return _validate_system_actor(info_actor)
    return None
