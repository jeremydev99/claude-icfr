from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit_context import system_actor
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import can_write, tenant_roles
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    issued_before_password_change,
    verify_password,
)
from app.core.tenant_context import get_active_tenant
from app.models.login_event import LoginEvent
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
)
from app.schemas.user import TenantAccessRead, UserRead

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _client_ip(request: Request) -> str | None:
    """호스트 nginx 가 넣는 X-Real-IP(실제 접속 IP)를 우선한다 — 컨테이너에서 보면 client 는 프록시다."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else None)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # sqlite 는 tz 를 버린다


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """로그인 — 계정 잠금·시도 기록 포함 (보안 1단계, 2026-10-01).

    - 연속 실패 `login_lock_threshold` 회면 `login_lock_minutes` 분 잠금(423). 잠긴 동안은 비밀번호를
      **확인하지 않는다** — 맞는 비밀번호인지 알려주면 잠금이 대입 공격을 막지 못한다.
    - 성공하면 실패 횟수·잠금을 지운다. 모든 시도를 `login_events` 에 남긴다(없는 이메일 포함).
    - 없는 이메일과 틀린 비밀번호는 같은 401 문구다(계정 존재 여부를 드러내지 않는다).
    """
    settings = get_settings()
    email = form_data.username.strip().lower()
    now = datetime.now(UTC)
    # 이메일은 대소문자·앞뒤 공백과 무관하게 찾는다 — 휴대폰 키보드가 첫 글자를 대문자로 바꾸거나
    # 자동 완성이 공백을 붙이면 로그인이 막혔다(2026-09-30 모바일 로그인 실패 보고)
    user = db.query(User).filter(
        func.lower(User.email) == email,
        User.is_deleted == False,  # noqa: E712
    ).first()

    def record(success: bool, reason: str) -> None:
        db.add(LoginEvent(
            user_id=user.id if user else None, email=email[:255], success=success, reason=reason,
            ip=_client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        ))

    with system_actor("system:auth-login"):
        if user and user.locked_until and _as_utc(user.locked_until) > now:
            record(False, "locked")
            db.commit()
            left = int((_as_utc(user.locked_until) - now).total_seconds() // 60) + 1
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"로그인 실패가 반복되어 계정이 잠겼습니다 — {left}분 후 다시 시도하거나 관리자에게 해제를 요청하세요",
            )
        if not user or not verify_password(form_data.password, user.hashed_password):
            if user:
                user.failed_login_count = (user.failed_login_count or 0) + 1
                if user.failed_login_count >= settings.login_lock_threshold:
                    user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
            record(False, "bad_password" if user else "unknown_email")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다",
            )
        if not user.is_active:
            record(False, "inactive")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="비활성화된 계정입니다",
            )
        user.failed_login_count = 0
        user.locked_until = None
        record(True, "ok")
        db.commit()
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
    if issued_before_password_change(payload, user.password_changed_at):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="비밀번호가 변경되어 다시 로그인해야 합니다")
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
    # 활성 테넌트는 get_current_user 가 정한 값이다(X-Tenant-Id 헤더 또는 단일 수렴).
    # **이전에는 tenants[0] 을 썼다** — 테넌트가 1개뿐이라 드러나지 않았을 뿐,
    # 여러 테넌트 + 헤더 지정 시 실제 활성 테넌트와 다른 값을 보고했다.
    # 아래 tenant_roles·can_write 가 활성 테넌트 기준이므로 그 기준을 맞춘다.
    active = get_active_tenant()
    result.active_tenant_id = active or (result.tenants[0].id if result.tenants else None)

    # 제도 운영 역할 — user_roles(AuditedBase) 라 활성 테넌트로 자동 필터된다(ADR-0025).
    # 판정은 core/permissions 하나뿐이며 여기서 다시 계산하지 않는다.
    roles = tenant_roles(db, current_user.id)
    result.tenant_roles = sorted(roles)
    result.can_write = can_write(roles)
    return result


@router.post("/change-password", status_code=status.HTTP_200_OK, response_model=ChangePasswordResponse)
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChangePasswordResponse:
    """본인 비밀번호 변경 — old_password 검증 후 변경.

    변경 시각보다 먼저 발급된 토큰은 무효가 된다(다른 기기 세션 종료). 이 기기는 응답의 새 토큰으로 이어간다.
    """
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다",
        )
    current_user.hashed_password = hash_password(body.new_password)
    current_user.password_changed_at = datetime.now(UTC)
    db.commit()
    return ChangePasswordResponse(
        detail="비밀번호가 변경되었습니다",
        access_token=create_access_token(str(current_user.id)),
        refresh_token=create_refresh_token(str(current_user.id)),
    )
