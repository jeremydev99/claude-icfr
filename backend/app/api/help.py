"""매뉴얼 패널 문구 조회 API (7-A, ADR-0035).

조회 전용이다 — 문구 수정은 시드 재적재로 한다(`seeds/seed_help_texts.py`). 쓰기 API 는
7-C 에서 검토한다. 전 역할이 읽을 수 있다(외부감사인 포함) — 도움말은 통제 데이터가 아니라
제품이 제공하는 문구다.

**접두사 조회는 문자열 일치만 쓴다** — 키를 점으로 쪼개 해석하지 않는다(`core/help_keys.py`).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.help_keys import prefix_filter, validate_key
from app.models.help_text import HelpText
from app.schemas.help_text import HelpTextOut

router = APIRouter(prefix="/api/help", tags=["help"])


@router.get("", response_model=list[HelpTextOut])
def list_help_texts(
    prefix: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
    locale: str = "ko",
) -> list[HelpText]:
    """`prefix` 자기 자신이거나 `prefix.`로 시작하는 키를 전부 반환. 화면 하나가 한 번에 부른다."""
    try:
        clause = prefix_filter(HelpText.key, prefix)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return (
        db.query(HelpText)
        .filter(HelpText.is_deleted == False, HelpText.locale == locale)  # noqa: E712
        .filter(clause)
        .order_by(HelpText.sort_order, HelpText.key)
        .all()
    )


@router.get("/{key}", response_model=HelpTextOut)
def get_help_text(
    key: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
    locale: str = "ko",
) -> HelpText:
    try:
        validate_key(key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    row = (
        db.query(HelpText)
        .filter(HelpText.key == key, HelpText.locale == locale, HelpText.is_deleted == False)  # noqa: E712
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"help key 없음: {key}")
    return row
