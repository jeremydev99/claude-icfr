"""매뉴얼 패널 문구 조회 스키마 (7-A, ADR-0035). 조회 전용 — 쓰기 스키마는 없다."""
from datetime import date

from pydantic import BaseModel, ConfigDict


class HelpTextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    locale: str
    title: str | None
    body: str | None
    source: str | None
    as_of: date | None
    sort_order: int
