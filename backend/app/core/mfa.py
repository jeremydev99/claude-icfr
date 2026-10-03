"""MFA(TOTP, RFC 6238) — 비밀값 암호화·코드 확인·QR·복구 코드 (ADR-0039 §2.4).

- 비밀값은 Fernet 으로 암호화해 `users.mfa_secret_enc` 에 둔다. 키 = 서버 env `MFA_ENC_KEY`(Fernet 키),
  없으면 JWT 비밀값의 SHA-256 에서 파생한다(JWT 비밀값을 바꾸면 MFA 를 다시 등록해야 한다 — 운영은 `MFA_ENC_KEY` 권장).
- 코드 확인은 ±30초(앞뒤 1구간)를 허용한다 — 휴대폰 시계 차이.
- 복구 코드는 10개, SHA-256 해시만 저장, 쓰면 지운다.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import secrets
from datetime import UTC, datetime

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

ISSUER = "ICFR"


def _fernet() -> Fernet:
    key = os.environ.get("MFA_ENC_KEY")
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(("mfa:" + get_settings().jwt_secret_key).encode()).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def new_secret() -> str:
    return pyotp.random_base32()


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def verify(secret: str, code: str) -> bool:
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    return len(code) == 6 and pyotp.TOTP(secret).verify(code, valid_window=1)


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_svg_data_uri(text: str) -> str:
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()


def _hash(code: str) -> str:
    return hashlib.sha256(code.replace("-", "").strip().upper().encode()).hexdigest()


def new_recovery_codes(n: int = 10) -> tuple[list[str], list[str]]:
    """(보여 줄 코드, 저장할 해시)."""
    codes = [f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}" for _ in range(n)]
    return codes, [_hash(c) for c in codes]


def use_recovery_code(hashes: list[str] | None, code: str) -> list[str] | None:
    """맞으면 그 코드를 뺀 새 목록, 틀리면 None."""
    h = _hash(code or "")
    if not hashes or h not in hashes:
        return None
    return [x for x in hashes if x != h]


def now() -> datetime:
    return datetime.now(UTC)
