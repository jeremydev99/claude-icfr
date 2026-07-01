from dataclasses import dataclass
from typing import Annotated
from uuid import UUID
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.core.tenant_context import set_active_tenant, get_active_tenant
from app.models.user import User
from app.models.tenant import UserTenantAccess

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _resolve_active_tenant(db: Session, user: User, x_tenant_id: str | None) -> UUID:
    """user 의 tenant 접근 권한을 검증해 활성 tenant_id 를 결정.

    - X-Tenant-Id 헤더 있음 → 그 tenant 에 접근 권한 필수(없으면 403)
    - 헤더 없음 + 접근 1개 → 자동 수렴(온프레/단일 회사)
    - 헤더 없음 + 접근 0개 → 403
    - 헤더 없음 + 접근 다수 → 400 (헤더 필요)
    """
    access_ids = {
        a.tenant_id
        for a in db.query(UserTenantAccess)
        .filter(
            UserTenantAccess.user_id == user.id,
            UserTenantAccess.is_deleted == False,  # noqa: E712
        )
        .all()
    }
    if x_tenant_id:
        try:
            requested = UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 X-Tenant-Id 형식입니다",
            )
        if requested not in access_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 회사(tenant)에 접근 권한이 없습니다",
            )
        return requested
    if len(access_ids) == 1:
        return next(iter(access_ids))
    if not access_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="소속된 회사(tenant)가 없습니다",
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="여러 회사에 접근 권한이 있습니다. X-Tenant-Id 헤더가 필요합니다",
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> User:
    """인증된 사용자 + 활성 tenant 확정.

    async 인 이유: 활성 tenant ContextVar 를 **이벤트 루프 컨텍스트**에 설정해야
    동기 엔드포인트(threadpool)로 자동 전파된다. 동기 의존성에서 설정하면 복사본에
    갇혀 전파되지 않는다 (ADR-0025 자동 격리 전제).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="자격 증명을 검증할 수 없습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    user = db.query(User).filter(
        User.id == UUID(user_id_str),
        User.is_deleted == False,  # noqa: E712
    ).first()
    if not user or not user.is_active:
        raise credentials_exception

    # 활성 tenant 검증·설정 (전 비즈니스 쿼리의 자동 격리 기준)
    tenant_id = _resolve_active_tenant(db, user, x_tenant_id)
    set_active_tenant(tenant_id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class CurrentContext:
    """인증된 사용자 + 검증된 활성 tenant_id. 명시적으로 tenant_id 가 필요한 엔드포인트용."""
    user: User
    tenant_id: UUID


def get_current_context(current_user: CurrentUser) -> CurrentContext:
    """get_current_user 가 설정한 활성 tenant 를 묶어 반환.

    동기 엔드포인트에서 get_active_tenant() 는 이벤트 루프에서 복사된 컨텍스트를
    읽으므로 get_current_user 가 설정한 값을 그대로 본다."""
    tenant_id = get_active_tenant()
    if tenant_id is None:  # 방어적 — get_current_user 통과 시 항상 설정됨
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="활성 회사(tenant)가 설정되지 않았습니다",
        )
    return CurrentContext(user=current_user, tenant_id=tenant_id)


CurrentCtx = Annotated[CurrentContext, Depends(get_current_context)]


def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다",
        )
    return current_user
