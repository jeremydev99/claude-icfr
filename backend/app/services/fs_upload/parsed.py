"""파서 출력 자료구조 (8-B). 판독기(disclosure·horizontal)가 채우고 구조 추론(structure)이 보탠다."""
from dataclasses import dataclass, field
from decimal import Decimal

KIND_DISCLOSURE = "disclosure_form"    # FS_SOURCE_KIND 값과 같다
KIND_HORIZONTAL = "horizontal_years"

# 행 종류 (structure 가 정한다)
ROW_SECTION_HEADER = "section_header"  # BS 의 "자산"/"부채"/"자본" — 계정으로 만들지 않는다
ROW_TITLE = "title"                    # 금액 없는 제목 — 금액 행 없는 계정
ROW_HEADER = "header"                  # 아래 행들을 묶는 소계(머리가 위)
ROW_FOOTER = "footer"                  # 앞 행들을 합한 합계(합계가 아래) — PL 사다리·총계
ROW_LEAF = "leaf"

# 추론 플래그 — preview 에 그대로 나간다
FLAG_SIGN_AMBIGUOUS = "sign_ambiguous"        # 부호 해가 여럿 — 음수 최소 해를 골랐다
FLAG_SIGN_UNRESOLVED = "sign_unresolved"      # 하위 합과 맞는 부호가 없다(원본 소계 불일치 가능)
FLAG_FOOTER_MISMATCH = "footer_mismatch"      # 굵은 합계 행인데 합이 안 맞아 구간 전체를 묶었다
FLAG_EXCLUDED_PER_SHARE = "excluded_per_share"  # 주당이익 — 원/주 단위라 금액 트리에서 뺀다


@dataclass(eq=False)
class ParsedRow:
    row_no: int
    raw_label: str
    label: str                                  # 표시용(접두 제거·글자 띄움 제거)
    rank: int                                   # 접두 순위 0=없음
    indent: int                                 # 셀 들여쓰기×2 + 앞 공백 수
    bold: bool
    amounts: dict[int, Decimal | None]          # 회계연도 → 금액(공시 표시 그대로)
    raw_values: dict[int, str | None] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)    # 주석번호·열 위치·조정 열·매핑 열
    errors: list[str] = field(default_factory=list)
    # ── 구조 추론 결과 ──
    kind: str = ""
    parent: "ParsedRow | None" = None
    children: list["ParsedRow"] = field(default_factory=list)
    sign: int = 1                               # 부모에 더할 때 곱하는 부호(rollup_sign)
    section: str = ""
    flags: list[str] = field(default_factory=list)
    level: int | None = None
    excluded: bool = False

    def has_amount(self) -> bool:
        return any(v is not None for v in self.amounts.values())

    @property
    def is_subtotal(self) -> bool:
        return self.kind in (ROW_HEADER, ROW_FOOTER) and bool(self.children) and self.has_amount()

    @property
    def is_account(self) -> bool:
        return self.kind != ROW_SECTION_HEADER and not self.excluded


@dataclass
class ParsedSheet:
    kind: str
    sheet_name: str
    statement_type: str | None                  # 감지값. 못 찾으면 None
    periods: list[int]                          # 회계연도 — 최신이 먼저
    rows: list[ParsedRow]
    unit_word: str | None = None                # 표 머리 표기("원"·"백만원")
    unit: int | None = None                     # 감지 배수. 표기가 있어도 미지원이면 None
    consolidated_hint: bool = False             # 제목에 "연결"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)   # 업로드를 막는 오류
    roots: list[ParsedRow] = field(default_factory=list)

    def account_rows(self) -> list[ParsedRow]:
        return [r for r in self.rows if r.is_account]
