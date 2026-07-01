import logging
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.core.tenant_context import (
    DEFAULT_TENANT_ID, DEFAULT_TENANT_CODE, DEFAULT_TENANT_NAME,
)
from app.models.user import User
from app.models.tenant import Tenant, UserTenantAccess

logger = logging.getLogger(__name__)


def ensure_default_tenant(db: Session) -> Tenant:
    """기본 tenant(단일 회사/온프레) 보장. 마이그레이션이 이미 만들었으면 재사용."""
    tenant = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).first()
    if tenant is None:
        tenant = Tenant(
            id=DEFAULT_TENANT_ID,
            name=DEFAULT_TENANT_NAME,
            code=DEFAULT_TENANT_CODE,
            is_active=True,
        )
        db.add(tenant)
        db.commit()
        logger.info(f"Default tenant created: {DEFAULT_TENANT_CODE}")
    return tenant


def bootstrap_admin(db: Session) -> None:
    """Phase 0 임시 admin 계정 + 기본 tenant 접근 권한 자동 생성. 멱등."""
    settings = get_settings()
    ensure_default_tenant(db)

    admin = db.query(User).filter(User.role == "admin", User.is_deleted == False).first()  # noqa: E712
    if admin is None:
        admin = User(
            email=settings.admin_email,
            hashed_password=hash_password(settings.admin_password),
            display_name=settings.admin_display_name,
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.info(f"Bootstrap admin created: {settings.admin_email}")
    else:
        logger.info(f"Admin account already exists: {admin.email}")

    # admin 의 기본 tenant 접근 권한 보장 (없으면 로그인 후 모든 요청 403)
    access = db.query(UserTenantAccess).filter(
        UserTenantAccess.user_id == admin.id,
        UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
        UserTenantAccess.is_deleted == False,  # noqa: E712
    ).first()
    if access is None:
        db.add(UserTenantAccess(
            user_id=admin.id, tenant_id=DEFAULT_TENANT_ID, role="admin",
        ))
        db.commit()
        logger.info("Admin default-tenant access granted")
