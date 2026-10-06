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
    create_mfa_token,
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
    LoginResponse,
    MfaEnableRequest,
    MfaEnableResponse,
    MfaSetupRequest,
    MfaSetupResponse,
    MfaVerifyRequest,
    RefreshRequest,
    RefreshResponse,
)
from app.schemas.user import TenantAccessRead, UserRead

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _client_ip(request: Request) -> str | None:
    """호스트 nginx 가 넣는 X-Real-IP(실제 접속 IP)를 우선한다 — 컨테이너에서 보면 client 는 프록시다."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else None)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # sqlite 는 tz 를 버린다


def _is_external(db: Session, user: User) -> bool:
    """어느 테넌트에서든 활성 외부 사용자인가 — 로그인 시점엔 활성 테넌트가 없어 자동 필터가 걸리지 않는다."""
    from app.models.external import EXT_ACTIVE, ExternalProfile
    return db.query(ExternalProfile).filter(ExternalProfile.user_id == user.id, ExternalProfile.status == EXT_ACTIVE,
                                            ExternalProfile.is_deleted == False).first() is not None  # noqa: E712


def _mfa_required(db: Session, user: User) -> bool:
    """MFA 의무 — 외부 사용자는 처음부터, 내부 마스터·책임관리자는 유예일부터 (ADR-0039 §2.4)."""
    from datetime import date

    from app.models.role_assignment import ROLE_ICFR_LEAD, ROLE_ICFR_MANAGER
    from app.models.user_mgmt import UserRole
    if _is_external(db, user):
        return True
    if date.today() < date.fromisoformat(get_settings().mfa_internal_required_from):
        return False
    return db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.is_deleted == False,  # noqa: E712
                                     UserRole.role_name.in_([ROLE_ICFR_MANAGER, ROLE_ICFR_LEAD])).first() is not None


def _issue(db: Session, user: User) -> tuple[str, str]:
    hours = get_settings().external_refresh_hours if _is_external(db, user) else None
    return create_access_token(str(user.id)), create_refresh_token(str(user.id), hours=hours)


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> LoginResponse:
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
    if user is not None:
        request.state.audit_user_id = user.id   # 감사 로그 — 토큰이 아직 없으므로 계정을 직접 알린다(실패 시도도)

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
        # MFA — 비밀번호가 맞아도 여기서 끝나지 않는다(ADR-0039). 성공 기록은 2단계 통과 때
        if user.mfa_enabled_at is not None:
            record(True, "mfa_challenge")
            db.commit()
            return LoginResponse(mfa_required=True, mfa_token=create_mfa_token(str(user.id), "verify"))
        if _mfa_required(db, user):
            record(True, "mfa_setup")
            db.commit()
            return LoginResponse(mfa_setup_required=True, mfa_token=create_mfa_token(str(user.id), "setup"))
        record(True, "ok")
        db.commit()
    access, refresh_tok = _issue(db, user)
    return LoginResponse(access_token=access, refresh_token=refresh_tok)


def _user_from_mfa_token(db: Session, token: str | None, purpose: str) -> User:
    payload = decode_token(token or "")
    if payload is None or payload.get("type") != "mfa" or payload.get("purpose") != purpose:
        raise HTTPException(status_code=401, detail="인증 단계가 만료됐습니다 — 다시 로그인하세요")
    from uuid import UUID
    u = db.query(User).filter(User.id == UUID(payload["sub"]), User.is_deleted == False,  # noqa: E712
                              User.is_active == True).first()  # noqa: E712
    if u is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")
    return u


@router.post("/mfa/verify", response_model=LoginResponse)
def mfa_verify(body: MfaVerifyRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    """로그인 2단계 — OTP 6자리 또는 복구 코드(1회용). 틀리면 로그인 실패로 센다(잠금 규칙 동일)."""
    from app.core import mfa
    user = _user_from_mfa_token(db, body.mfa_token, "verify")
    request.state.audit_user_id = user.id
    settings = get_settings()
    now = datetime.now(UTC)
    secret = mfa.decrypt(user.mfa_secret_enc or "")
    ok = bool(secret) and mfa.verify(secret, body.code)
    used_recovery = False
    if not ok:
        rest = mfa.use_recovery_code(user.mfa_recovery, body.code)
        if rest is not None:
            ok, used_recovery = True, True
            user.mfa_recovery = rest
    with system_actor("system:auth-login"):
        db.add(LoginEvent(user_id=user.id, email=user.email, success=ok,
                          reason=("ok_recovery" if used_recovery else "ok") if ok else "mfa_bad_code",
                          ip=_client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300] or None))
        if not ok:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= settings.login_lock_threshold:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        else:
            user.failed_login_count, user.locked_until = 0, None
        db.commit()
    if not ok:
        raise HTTPException(status_code=401, detail="인증 코드가 올바르지 않습니다")
    access, refresh_tok = _issue(db, user)
    return LoginResponse(access_token=access, refresh_token=refresh_tok)


def _mfa_subject(db: Session, request: Request, mfa_token: str | None) -> tuple[User, bool]:
    """등록 주체 — 로그인 중(mfa_token, purpose=setup)이거나 로그인한 사용자(Authorization). (사용자, 로그인 중 여부)."""
    if mfa_token:
        return _user_from_mfa_token(db, mfa_token, "setup"), True
    auth = request.headers.get("authorization") or ""
    payload = decode_token(auth.removeprefix("Bearer ").strip()) if auth.startswith("Bearer ") else None
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    from uuid import UUID
    u = db.query(User).filter(User.id == UUID(payload["sub"]), User.is_deleted == False).first()  # noqa: E712
    if u is None or issued_before_password_change(payload, u.password_changed_at):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return u, False


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(body: MfaSetupRequest, request: Request, db: Session = Depends(get_db)) -> MfaSetupResponse:
    """등록 시작 — 새 비밀값(아직 미적용)과 QR. 첫 코드를 확인해야 적용된다."""
    from app.core import mfa
    user, _ = _mfa_subject(db, request, body.mfa_token)
    secret = mfa.new_secret()
    with system_actor("system:auth-mfa"):
        user.mfa_pending_enc = mfa.encrypt(secret)
        db.commit()
    uri = mfa.provisioning_uri(secret, user.email)
    return MfaSetupResponse(secret=secret, otpauth_uri=uri, qr_svg=mfa.qr_svg_data_uri(uri))


@router.post("/mfa/enable", response_model=MfaEnableResponse)
def mfa_enable(body: MfaEnableRequest, request: Request, db: Session = Depends(get_db)) -> MfaEnableResponse:
    """등록 확정 — 앱에 뜬 코드가 맞으면 적용하고 복구 코드 10개를 **한 번만** 보여 준다."""
    from app.core import mfa
    user, in_login = _mfa_subject(db, request, body.mfa_token)
    request.state.audit_user_id = user.id
    pending = mfa.decrypt(user.mfa_pending_enc or "")
    if not pending or not mfa.verify(pending, body.code):
        raise HTTPException(status_code=422, detail="인증 코드가 맞지 않습니다 — 앱에 표시된 6자리를 다시 입력하세요")
    codes, hashes = mfa.new_recovery_codes()
    with system_actor("system:auth-mfa"):
        user.mfa_secret_enc, user.mfa_pending_enc = user.mfa_pending_enc, None
        user.mfa_enabled_at, user.mfa_recovery = datetime.now(UTC), hashes
        db.add(LoginEvent(user_id=user.id, email=user.email, success=True, reason="mfa_enrolled",
                          ip=_client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300] or None))
        db.commit()
    out = MfaEnableResponse(recovery_codes=codes)
    if in_login:
        out.access_token, out.refresh_token = _issue(db, user)
    return out


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
    result.mfa_enabled = current_user.mfa_enabled_at is not None
    result.mfa_required = _mfa_required(db, current_user)
    from app.models.external import TYPE_LABELS, ExternalProfile
    p = db.query(ExternalProfile).filter(ExternalProfile.user_id == current_user.id,
                                         ExternalProfile.is_deleted == False).first()  # noqa: E712
    if p is not None:
        result.external = {"user_type": p.user_type, "type_label": TYPE_LABELS.get(p.user_type, p.user_type),
                           "organization": p.organization, "modules": p.modules or [],
                           "valid_from": str(p.valid_from), "valid_until": str(p.valid_until)}
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
