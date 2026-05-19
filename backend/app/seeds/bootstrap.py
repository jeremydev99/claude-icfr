import logging
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.models.user import User

logger = logging.getLogger(__name__)


def bootstrap_admin(db: Session) -> None:
    """Phase 0 임시 admin 계정 자동 생성. Phase 1 정식 시드에서 대체됨."""
    settings = get_settings()
    existing = db.query(User).filter(User.role == "admin", User.is_deleted == False).first()  # noqa: E712
    if existing:
        logger.info(f"Admin account already exists: {existing.email}")
        return
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
