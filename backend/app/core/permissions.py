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
from app.models.role_assignment import ROLE_EXTERNAL_AUDITOR, ROLE_ICFR_MANAGER
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


def require_write(user: CurrentUser, db: Session = Depends(get_db)) -> User:
    """생성·수정 API 공통 가드. **`external_auditor` 는 조회 전용이다**(ADR-0031 §2.1).

    외부감사인이 평가 데이터를 만들거나 고칠 수 있으면 그 자체가 독립성 훼손이다.
    막는 지점을 엔드포인트마다 두면 한 곳만 빠뜨려도 뚫리므로 의존성 하나로 모은다.
    """
    if ROLE_EXTERNAL_AUDITOR in tenant_roles(db, user.id):
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
