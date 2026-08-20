from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, RefreshRequest, RefreshResponse, TokenResponse
from app.schemas.user import TenantAccessRead, UserRead

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.query(User).filter(
        User.email == form_data.username,
        User.is_deleted == False,  # noqa: E712
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비활성화된 계정입니다",
        )
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> RefreshResponse:
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 리프레시 토큰입니다",
        )
    from uuid import UUID
    user_id_str = payload.get("sub")
    user = db.query(User).filter(
        User.id == UUID(user_id_str),
        User.is_deleted == False,  # noqa: E712
        User.is_active == True,  # noqa: E712
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다")
    return RefreshResponse(access_token=create_access_token(str(user.id)))


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user)) -> dict:
    # Phase 1.5+에서 블랙리스트 구현 예정
    return {"detail": "로그아웃 완료"}


@router.get("/me", response_model=UserRead)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    """내 정보 + 접근 가능한 tenant 목록. User는 전역 계정이므로 UserTenantAccess join으로 조회."""
    rows = (
        db.query(UserTenantAccess.role, Tenant)
        .join(Tenant, UserTenantAccess.tenant_id == Tenant.id)
        .filter(
            UserTenantAccess.user_id == current_user.id,
            UserTenantAccess.is_deleted == False,  # noqa: E712
            Tenant.is_deleted == False,  # noqa: E712
            Tenant.is_active == True,  # noqa: E712
        )
        .order_by(UserTenantAccess.created_at)
        .all()
    )
    result = UserRead.model_validate(current_user)
    result.tenants = [
        TenantAccessRead(id=tenant.id, name=tenant.name, code=tenant.code, role=role)
        for role, tenant in rows
    ]
    result.active_tenant_id = result.tenants[0].id if result.tenants else None
    return result


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """본인 비밀번호 변경 — old_password 검증 후 변경."""
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다",
        )
    current_user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"detail": "비밀번호가 변경되었습니다"}
