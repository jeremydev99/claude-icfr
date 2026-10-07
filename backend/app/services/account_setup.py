"""직원 계정 설정 링크 발급·사용 (ADR-0041). 관리자는 링크만 전달하고 비밀번호는 직원이 정한다."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.account_setup import PURPOSE_INVITE, PURPOSE_RESET, AccountSetupToken
from app.models.user import User

TOKEN_HOURS = 72


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def unusable_password() -> str:
    """초대 대기 계정의 비밀번호 자리 — 아무도 모르는 임의 값의 해시(로그인 불가)."""
    return hash_password(secrets.token_urlsafe(48))


def issue(db: Session, user: User, issuer_id, purpose: str | None = None) -> tuple[str, AccountSetupToken]:
    """새 링크 발급 — 그 사용자의 쓰지 않은 이전 링크는 취소한다. 원문은 이 응답에서만 돌려준다."""
    now = datetime.now(UTC)
    purpose = purpose or (PURPOSE_INVITE if user.invite_pending else PURPOSE_RESET)
    for t in db.query(AccountSetupToken).filter(AccountSetupToken.user_id == user.id,
                                                AccountSetupToken.used_at.is_(None),
                                                AccountSetupToken.revoked_at.is_(None)).all():
        t.revoked_at = now
    raw = secrets.token_urlsafe(32)
    row = AccountSetupToken(user_id=user.id, purpose=purpose, token_hash=_h(raw),
                            expires_at=now + timedelta(hours=TOKEN_HOURS), issued_by_id=issuer_id)
    db.add(row)
    db.flush()
    return raw, row


def by_token(db: Session, token: str) -> tuple[AccountSetupToken, User]:
    t = db.query(AccountSetupToken).filter(AccountSetupToken.token_hash == _h(token)).first()
    if t is None or t.used_at is not None or t.revoked_at is not None:
        raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다 — 이미 사용했거나 새 링크가 발급됐습니다")
    if _utc(t.expires_at) < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="링크가 만료됐습니다 — 관리자에게 새 링크를 요청하세요")
    u = db.get(User, t.user_id)
    if u is None or u.is_deleted or not u.is_active:
        raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다")
    return t, u


def complete(db: Session, token: str, password: str) -> User:
    """직원이 비밀번호를 정한다 — 링크는 한 번만. 다른 기기의 이전 세션은 끊긴다(password_changed_at)."""
    t, u = by_token(db, token)
    now = datetime.now(UTC)
    u.hashed_password = hash_password(password)
    u.password_changed_at = now
    u.failed_login_count, u.locked_until = 0, None
    u.invite_pending, u.must_change_password = False, False
    t.used_at = now
    return u


def setup_url(origin: str, token: str) -> str:
    return f"{origin.rstrip('/')}/setup/{token}"


__all__ = ["PURPOSE_INVITE", "PURPOSE_RESET", "TOKEN_HOURS", "by_token", "complete", "issue", "setup_url",
           "unusable_password"]
