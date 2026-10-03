from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expires_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "iat": datetime.now(UTC), "type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, hours: int | None = None) -> str:
    """갱신 토큰 — 기본 `jwt_refresh_token_expires_days` 일. 외부 사용자는 `hours`(ADR-0039: 8시간)."""
    settings = get_settings()
    expire = datetime.now(UTC) + (timedelta(hours=hours) if hours else
                                  timedelta(days=settings.jwt_refresh_token_expires_days))
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "iat": datetime.now(UTC), "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def issued_before_password_change(payload: dict, password_changed_at: datetime | None) -> bool:
    """토큰이 마지막 비밀번호 변경보다 먼저 발급됐는가 — 그렇다면 무효로 본다(보안 1단계).

    `iat` 는 초 단위로 잘려 들어가므로 변경 시각도 초로 내려 비교한다(같은 초에 새로 받은 토큰을 살린다).
    `iat` 가 없는 옛 토큰은 변경 이력이 있으면 무효다. sqlite 는 tz 를 버리므로 naive 는 UTC 로 본다.
    """
    if password_changed_at is None:
        return False
    changed = password_changed_at if password_changed_at.tzinfo else password_changed_at.replace(tzinfo=UTC)
    iat = payload.get("iat")
    if iat is None:
        return True
    return int(iat) < int(changed.timestamp())


def create_mfa_token(subject: str, purpose: str) -> str:
    """MFA 2단계용 5분 토큰 — `purpose` = verify(코드 입력) | setup(등록). 이 토큰으로는 API 를 못 쓴다."""
    settings = get_settings()
    payload: dict[str, Any] = {"sub": subject, "exp": datetime.now(UTC) + timedelta(minutes=5),
                               "iat": datetime.now(UTC), "type": "mfa", "purpose": purpose}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
