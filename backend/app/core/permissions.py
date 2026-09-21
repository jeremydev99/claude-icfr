"""제도 운영 권한 검사 — ADR-0031 §3.2, 3-1.

**`users.role` 과 `user_roles` 는 다른 것이며 서로 참조하지 않는다**(ADR-0031 §3.2).

| | `users.role` | `user_roles` |
|---|---|---|
| 의미 | 시스템 관리 권한 | 제도 운영 권한 |
| 판정 | `deps.require_admin` **전용** | 이 모듈 |

`users.role == "admin"` 인 계정이 자동으로 `icfr_manager` 가 되지 않으며 그 반대도 아니다.
한쪽을 보고 다른 쪽을 추론하지 않는다 — §2.1.1 이 말하는 "시스템 관리 권한과 제도 운영
권한을 겸하면 그 자체가 감사 지적 대상"이라는 분리를 저장소·판정 양쪽에서 지킨다.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.role_assignment import (
    ROLE_EXTERNAL_AUDITOR,
    ROLE_ICFR_MANAGER,
    ROLE_SYS_ADMIN,
)
from app.models.user import User
from app.models.user_mgmt import UserRole


def tenant_roles(db: Session, user_id) -> set[str]:
    """활성 tenant 에서 이 사용자가 가진 제도 운영 역할 집합.

    `user_roles` 는 `AuditedBase` 라 tenant 필터가 자동으로 걸린다(ADR-0025).
    **여기서 수동 필터를 추가하지 않는다.**
    """
    return {
        r.role_name
        for r in db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.is_deleted == False,  # noqa: E712
        ).all()
    }


def can_write(roles: set[str]) -> bool:
    """제도 운영 데이터를 쓸 수 있는가. **`require_write` 와 같은 판정이다.**

    `/me` 응답의 `can_write` 와 `require_write` 가 각자 계산하면 규칙이 두 곳에
    존재하게 되고, 어긋날 때 어느 쪽이 맞는지 알 수 없다. 판정은 여기 하나뿐이고
    양쪽이 이 함수를 호출한다.

    지금은 단일 조건이나 권한 판정이 계속 늘고 있다(회차 상태별·통제 단위·정책 토글·
    증빙 편집). 조건이 늘 때도 이 함수만 고치면 되도록 둔다.
    """
    return ROLE_EXTERNAL_AUDITOR not in roles


def require_write(user: CurrentUser, db: Session = Depends(get_db)) -> User:
    """생성·수정 API 공통 가드. **`external_auditor` 는 조회 전용이다**(ADR-0031 §2.1).

    외부감사인이 평가 데이터를 만들거나 고칠 수 있으면 그 자체가 독립성 훼손이다.
    막는 지점을 엔드포인트마다 두면 한 곳만 빠뜨려도 뚫리므로 의존성 하나로 모은다.
    """
    if not can_write(tenant_roles(db, user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="외부감사인은 조회만 가능합니다",
        )
    return user


def require_icfr_manager(user: CurrentUser, db: Session = Depends(get_db)) -> User:
    """정책 변경 가드 — `icfr_manager` 만 테넌트 정책을 바꾼다(ADR-0031 §2.6)."""
    if ROLE_ICFR_MANAGER not in tenant_roles(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="내부회계관리자 권한이 필요합니다",
        )
    return user


def has_icfr_manager(db: Session) -> bool:
    """활성 tenant 에 `icfr_manager` 보유자가 1명이라도 있는가.

    `user_roles` 는 `AuditedBase` 라 tenant 필터가 자동이다(ADR-0025) —
    `tenant_roles` 와 같은 이유로 수동 필터를 붙이지 않는다.
    """
    return db.query(UserRole).filter(
        UserRole.role_name == ROLE_ICFR_MANAGER,
        UserRole.is_deleted == False,  # noqa: E712
    ).first() is not None


def require_role_assigner(user: CurrentUser, db: Session = Depends(get_db)) -> User:
    """테넌트 역할 배정·수정·삭제 가드 (ADR-0031 §3.3, 13.9-35).

    **배정만 막으면 안 된다** — `external_auditor` 가 자기 역할 행을 지우면
    조회 전용을 스스로 벗어난다. 생성·수정·삭제 세 경로가 같은 가드를 쓴다.

    **`require_admin`(`users.role`)으로 막지 않는다**(§3.2). 시스템 계정 관리
    권한과 제도 운영 권한은 서로를 추론하지 않으며, `sys_admin` 은 제도 활동에
    참여하지 않는다(§2.1.1).

    **부트스트랩 예외** — 테넌트에 `icfr_manager` 가 0명일 때만 `user_roles` 의
    `sys_admin` 이 배정할 수 있다. 첫 배정을 할 사람이 없는 상태를 풀기 위한
    것이며, 1명이라도 생기면 이 경로는 닫힌다. `sys_admin` 이 제도 운영에
    참여하는 것이 아니라 **초기 셋업만** 하는 것이고, 그 사실이 조건으로
    코드에 남는다. 이 조건이 없으면 "sys_admin 도 제도 역할을 배정한다"로
    잘못 읽힌다.

    **여기서도 `users.role` 은 보지 않는다** — 그래서 `user_roles` 가 완전히 빈
    테넌트는 첫 행을 API 로 만들 수 없다. 그건 실데이터 시딩이며 마스터가
    직접 실행한다(13.9-35).
    """
    roles = tenant_roles(db, user.id)
    if ROLE_ICFR_MANAGER in roles:
        return user
    if ROLE_SYS_ADMIN in roles and not has_icfr_manager(db):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=("역할 배정은 내부회계관리자만 가능합니다"
                " (내부회계관리자가 없는 테넌트에 한해 시스템관리자가 첫 배정을 합니다)"),
    )
