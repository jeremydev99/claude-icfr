"""매뉴얼 패널 키 규칙 (7-A, ADR-0035).

**키는 불투명한 식별자다.** 이 파일은 형식(문자셋)만 검증한다 — 점(`.`)으로 나눠 route
이름이나 섹션 이름을 뽑아내는 함수를 여기에 두지 않는다. 조회(`api/help.py`)도 접두사
**문자열 일치**만 쓴다. 키 구조를 해석하는 코드가 생기면 화면 이름이 바뀔 때마다
저장소·조회 코드까지 함께 고쳐야 한다 — 그 결합을 만들지 않는 것이 이 규칙의 목적이다.

권장 접두사(강제하지 않는다 — 시드 데이터 작성 규약일 뿐이다):
    menu.<route>              메뉴
    screen.<route>.<섹션>      화면 안의 섹션
    field.<모듈>.<API 필드명>   항목 (필드명은 스키마의 snake_case 그대로)
    action.<모듈>.<동작>        버튼·동작
    term.<용어>                용어
"""
import re

from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

# 소문자·숫자·`_`·`-`만 세그먼트에 허용, 세그먼트는 `.`로 구분, 빈 세그먼트 금지
_SEGMENT = r"[a-z0-9_-]+"
KEY_PATTERN = re.compile(rf"^{_SEGMENT}(\.{_SEGMENT})*$")


def validate_key(key: str) -> None:
    """형식 위반 시 ValueError. 소문자·숫자·`_`·`-`·`.`만 허용, 빈 세그먼트 금지."""
    if not isinstance(key, str) or not KEY_PATTERN.match(key):
        raise ValueError(f"help key 형식이 올바르지 않습니다: {key!r}")


def prefix_filter(key_column, prefix: str) -> ColumnElement:
    """접두사 일치 — `prefix` 자기 자신이거나 `prefix.`로 시작하는 키.

    `_`는 이 키 규칙에서 유효한 문자이자 SQL LIKE 의 와일드카드(임의의 한 글자)이므로,
    LIKE 패턴에 넣기 전에 반드시 이스케이프한다. 이스케이프하지 않으면
    `field.rcm.control_type` 조회가 `field.rcm.controlXtype` 같은 엉뚱한 키까지 잡는다.
    """
    validate_key(prefix)
    escaped = prefix.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return or_(key_column == prefix, key_column.like(f"{escaped}.%", escape="\\"))
