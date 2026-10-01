"""매뉴얼 패널 문구 저장 — help_texts (7-A, ADR-0035).

**tenant 비종속** — 도움말은 제품이 제공하는 문구이고 회사 데이터가 아니다.
`scoping_templates` 와 같은 자리다(`IdentityBase`).

**키는 불투명한 식별자로 다룬다.** `menu.<route>`·`screen.<route>.<섹션>`·
`field.<모듈>.<필드명>`·`action.<모듈>.<동작>`·`term.<용어>` 형태로 짓지만, 코드는 점(`.`)
으로 쪼개 route·섹션을 해석하지 않는다. 조회는 접두사 **문자열 일치**만 쓴다
(`core/help_keys.py`). 키 구조를 해석하는 코드가 생기면 화면 이름이 바뀔 때마다 키 규칙과
조회 로직을 함께 고쳐야 한다 — 저장소와 소비자가 키 구조에 대해 합의할 필요가 없게
하는 것이 이 규칙의 목적이다.

locale 은 지금 'ko' 하나뿐이지만 지금 넣어 둔다 — 나중에 붙이면 unique 제약(`key`, `locale`)
을 바꿔야 하기 때문이다.

**회사별 문구 수정(overlay)은 이 단계에 없다.** 키가 전역 고유하므로, 필요해지면
`help_text_overlays`(tenant_id + help_text_id FK) 를 추가하기만 하면 된다 — 이 테이블은
바꾸지 않는다.

문구 원본은 `backend/seeds/data/help_texts_ko.json` 이고, `seeds/seed_help_texts.py` 가
이 테이블에 멱등 upsert 한다. **쓰기 API 는 없다**(7-C 로 미룸) — 문구 수정은 시드 재적재로 한다.
"""
from datetime import date

from sqlalchemy import Date, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentityBase


class HelpText(IdentityBase):
    """매뉴얼 패널 문구 한 건. body 가 없으면(NULL) '문구 미작성' 상태를 뜻한다."""

    __tablename__ = "help_texts"
    __table_args__ = (
        Index(
            "uq_help_texts_key_locale", "key", "locale",
            unique=True,
            sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("NOT is_deleted"),
        ),
    )

    key: Mapped[str] = mapped_column(String(150), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="ko")
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 규정 인용 시 출처·기준일(13.9-8) — 제도는 개정되므로 기준일 없는 규정 설명은 낡은
    # 판단을 유도한다. source 가 있으면 as_of 도 있어야 한다 — DB 제약이 아니라
    # 시드 로더가 검증한다(seeds/seed_help_texts.py load_entries).
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    # baseline 콘텐츠 개정 회차 — rcm_baseline.baseline_version 과 같은 개념(행 단위)
    baseline_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
