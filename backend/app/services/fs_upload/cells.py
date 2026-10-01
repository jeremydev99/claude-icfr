"""엑셀 셀 해석 — 금액·단위·계층 접두·라벨 정규화 (8-B, ADR-0037 §3).

순수 함수만 둔다. DB·openpyxl 워크시트를 모른다.

**금액 규칙** (마스터 확정 Q1 — 조용한 반올림 금지):
- 괄호·`△`·`▲` → 음수, `-`(대시) → 0, 빈칸 → None(0 이 아니다)
- bool(검산 열의 TRUE/FALSE) → None
- 부동소수 잡음(|x − round(x)| < 1e-6, 수식 결과에서 생긴다) → 정수 + `float_noise` 메모
- 그 밖의 소수 → `AmountError` (행 오류로 거부한다)
"""
import re
from decimal import Decimal, InvalidOperation

# 공백으로 취급할 문자 — 공시 양식은 NBSP 로 글자를 띄운다("자 산 총 계")
WS_CHARS = "  　\t"
_WS_RE = re.compile(r"[\s 　]+")

# 계층 접두 — 순위가 낮을수록 상위다. 로마숫자는 ASCII 와 전각(Ⅰ…) 둘 다 쓰인다
_ROMAN = r"(?:XI{0,3}|IX|IV|VI{0,3}|V|I{1,3}|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ])"
PREFIX_RULES: tuple[tuple[int, re.Pattern], ...] = (
    (1, re.compile(rf"^{_ROMAN}\s*\.\s*", re.I)),
    (2, re.compile(r"^\d{1,2}\s*\.\s*")),
    (3, re.compile(r"^\(\d{1,2}\)\s*")),
    (4, re.compile(r"^[가-하]\s*\.\s*")),
)

# 단위 — 표 머리의 "(단위 : 백만원)" 등. **못 찾으면 추정하지 않는다**(사용자 선택 필수)
UNIT_WORDS = {"원": 1, "천원": 1000, "백만원": 1000000}
_UNIT_RE = re.compile(r"단위[:：]?(백만원|십억원|천만원|억원|천원|만원|원)")

FLOAT_NOISE = 1e-6


class AmountError(ValueError):
    """금액으로 읽을 수 없는 셀 — 행 오류로 보고한다."""


def norm(text: str | None) -> str:
    """비교용 정규화 — 모든 공백(NBSP·전각 포함) 제거. 원문은 따로 보존한다."""
    return _WS_RE.sub("", text or "")


def leading_ws(text: str) -> int:
    n = 0
    for ch in text:
        if ch not in WS_CHARS:
            break
        n += 1
    return n


def split_prefix(label: str) -> tuple[int, str]:
    """(접두 순위, 접두를 뗀 라벨). 접두가 없으면 순위 0."""
    t = label.strip(WS_CHARS)
    for rank, rx in PREFIX_RULES:
        m = rx.match(t)
        if m:
            return rank, t[m.end():].strip(WS_CHARS)
    return 0, t


def display_label(label: str) -> str:
    """표시용 라벨 — 접두를 떼고 NBSP 띄어쓰기("자 산 총 계")를 붙인다.

    글자 사이마다 공백이 있는 표기(한 글자씩 띄움)만 붙인다. 일반 문장의 띄어쓰기는 둔다.
    """
    _, t = split_prefix(label)
    t = t.replace(" ", " ").replace("　", " ")
    parts = t.split()
    if len(parts) >= 3 and all(len(p) == 1 for p in parts):
        return "".join(parts)
    return " ".join(parts)


def detect_unit(text: str) -> tuple[str, int | None] | None:
    """셀 문자열에서 단위 표기를 찾는다. (표기, 배수|None=미지원 단위) 또는 None."""
    m = _UNIT_RE.search(norm(text))
    if not m:
        return None
    word = m.group(1)
    return word, UNIT_WORDS.get(word)


def parse_amount(value) -> tuple[Decimal | None, str | None]:
    """셀 값 → (금액, 메모). 메모: `float_noise`·`dash`·`text` 또는 None."""
    if value is None or isinstance(value, bool):
        return None, None
    if isinstance(value, int):
        return Decimal(value), None
    if isinstance(value, float):
        r = round(value)
        if abs(value - r) < FLOAT_NOISE:
            return Decimal(r), ("float_noise" if value != r else None)
        raise AmountError(f"소수 금액은 저장하지 않습니다: {value}")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise AmountError(f"소수 금액은 저장하지 않습니다: {value}")
        return value, None
    if not isinstance(value, str):
        raise AmountError(f"금액이 아닙니다: {value!r}")
    s = value.strip(WS_CHARS)
    if s == "":
        return None, None
    if s in {"-", "—", "–"}:
        return Decimal(0), "dash"
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1].strip(WS_CHARS)
    if s[:1] in {"△", "▲"}:
        neg, s = True, s[1:].strip(WS_CHARS)
    s = s.replace(",", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        raise AmountError(f"금액이 아닙니다: {value!r}")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise AmountError(f"금액이 아닙니다: {value!r}") from None
    if d != d.to_integral_value():
        raise AmountError(f"소수 금액은 저장하지 않습니다: {value!r}")
    return (-d if neg else d), "text"


def raw_text(value) -> str | None:
    """원본 셀 값의 문자열 보존(`fs_amounts.raw_value`, 100자)."""
    if value is None:
        return None
    return str(value)[:100]
