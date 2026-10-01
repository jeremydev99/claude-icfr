"""재무제표 구조 추론 — 트리·소계·합산 부호·섹션 제안 (8-B, ADR-0037 §3).

엑셀은 트리를 직접 담지 않는다. 행 순서·접두·들여쓰기·굵게·**금액**으로 트리를 되살린다.
결과는 **제안**이다 — preview 로 사람이 보고 commit 한다. 확정 관문은 8-A `validate()` 그대로다.

## 알고리즘 (2025 감사 완료본 실측으로 검증 — BS·PL·CF 공시양식 2기간·PL정산표 3연도 소계 오류 0)
1. **수준 힌트** = 접두 순위(로마 1 < 아라비아 2 < 괄호 3 < 가나다 4) × 10 + 들여쓰기.
   접두 없이 들여쓴 행은 잎(100+). **접두·들여쓰기가 모두 없는 행(flat)은 금액으로 판정한다.**
2. **머리 소계(header)** — 다음 행이 더 깊으면 머리. 자식 부호는 풀이로 구한다.
3. **합계 행(footer)** — 앞 형제(또는 최상위 노드)의 **끝 구간**이 부호 조합으로 맞으면 그 구간을
   자식으로 묶는다(짧은 구간 우선). PL 사다리(영업이익 = 영업수익 − 영업비용)·총계·기말현금이 이것이다.
4. **부호 풀이는 모든 기간을 동시에 만족해야 채택한다.** 한 기간만 보면 `0 = 0 + 0` 같은 우연
   일치가 생긴다(실측 `상환할증금`). 0 이 아닌 값이 하나도 없으면 근거로 치지 않는다.
   음수 개수가 가장 적은 해를 고르고, 해가 여럿이면 `sign_ambiguous`.
5. **섹션 제안** — BS 는 금액 없는 `자산`/`부채`/`자본` 행, PL 은 부호(합계·혼합 소계=profit,
   누적 부호 + =revenue, − =expense), CF 는 최상위 머리의 `영업활동`/`투자활동`/`재무활동`.

**이름을 보는 곳은 제안값뿐이다**(BS 섹션 머리·CF 섹션·주당이익 제외·종류 감지). 8-A 검증은
여전히 이름을 보지 않는다(ADR-0037 §2.3).
"""
import itertools
from decimal import Decimal

from app.services.fs_upload.cells import norm
from app.services.fs_upload.parsed import (
    FLAG_EXCLUDED_PER_SHARE,
    FLAG_FOOTER_MISMATCH,
    FLAG_SIGN_AMBIGUOUS,
    FLAG_SIGN_UNRESOLVED,
    ROW_FOOTER,
    ROW_HEADER,
    ROW_LEAF,
    ROW_SECTION_HEADER,
    ROW_TITLE,
    ParsedRow,
    ParsedSheet,
)

ZERO = Decimal(0)
BS_SECTION_WORDS = {"자산": "asset", "부채": "liability", "자본": "equity"}
CF_SECTION_WORDS = (("영업활동", "operating"), ("투자활동", "investing"), ("재무활동", "financing"))
PER_SHARE_WORD = "주당"
MAX_FOOTER_SPAN = 8      # 합계 행이 묶을 수 있는 끝 구간 최대 길이
MAX_BRUTE_SIGNS = 12     # 자식이 이보다 많으면 1~2개 뒤집기까지만 탐색
LEVEL_FOOTER, LEVEL_BOLD_HEAD, LEVEL_LEAF = 0, 5, 100


# ── 부호 풀이 ───────────────────────────────────────────────────────

def solve_signs(targets: list[Decimal | None], vecs: list[list[Decimal]],
                tol: Decimal = ZERO) -> tuple[list[int], bool] | None:
    """모든 기간 j 에서 targets[j] = Σ s_i · vecs[i][j] 를 만족하는 부호 s ∈ {+1, −1}.

    음수 개수 최소 해와 "해가 여럿인가"를 돌려준다. 해가 없으면 None. targets[j] 가 None 인 기간은
    비교하지 않는다.
    """
    n = len(vecs)
    idx = [j for j, t in enumerate(targets) if t is not None]
    if n == 0 or not idx:
        return None

    def ok(signs: list[int]) -> bool:
        return all(abs(sum((s * v[j] for s, v in zip(signs, vecs)), ZERO) - targets[j]) <= tol for j in idx)

    if ok([1] * n):
        return [1] * n, False
    ks = range(1, n + 1) if n <= MAX_BRUTE_SIGNS else (1, 2)
    for k in ks:
        sols = []
        for neg in itertools.combinations(range(n), k):
            signs = [-1 if i in neg else 1 for i in range(n)]
            if ok(signs):
                sols.append(signs)
        if sols:
            return sols[0], len(sols) > 1
    return None


def has_evidence(targets: list[Decimal | None], vecs: list[list[Decimal]]) -> bool:
    """0 이 아닌 값이 하나라도 있어야 합계·부호 추론의 근거가 된다."""
    return any(t for t in targets if t is not None) or any(x for v in vecs for x in v)


def effective(row: ParsedRow, year: int) -> Decimal:
    """유효 금액 — 있으면 그 값, 없으면 하위 유효 금액 × 부호 합(8-A `validate` 와 같은 정의)."""
    v = row.amounts.get(year)
    if v is not None:
        return v
    return sum((effective(c, year) * c.sign for c in row.children if not c.excluded), ZERO)


def _hint(r: ParsedRow) -> int | None:
    if r.rank:
        return r.rank * 10 + r.indent
    return LEVEL_LEAF + r.indent if r.indent else None


# ── 추론 ────────────────────────────────────────────────────────────

def infer(sheet: ParsedSheet) -> None:
    """`sheet.rows` 에 kind·parent·children·sign·level·section·flags 를 채우고 `sheet.roots` 를 만든다."""
    rows, periods, stype = sheet.rows, sheet.periods, sheet.statement_type
    roots: list[ParsedRow] = []
    block_start = 0            # 마지막 섹션 머리 이후 roots 시작 위치
    stack: list[ParsedRow] = []
    section = ""

    for r in rows:
        r.level = _hint(r)

    def look(nx: ParsedRow | None) -> int | None:
        if nx is None:
            return None
        if nx.level is not None:
            return nx.level
        return LEVEL_BOLD_HEAD if (nx.bold or not nx.has_amount()) else LEVEL_LEAF

    def targets(r: ParsedRow) -> list[Decimal | None]:
        return [r.amounts.get(y) for y in periods]

    def try_footer(r: ParsedRow, cands: list[ParsedRow], min_len: int):
        tg = targets(r)
        if all(t is None for t in tg):
            return None
        for n in range(min_len, min(len(cands), MAX_FOOTER_SPAN) + 1):
            tail = cands[-n:]
            if n == 1 and not tail[0].children:
                # 하나만 묶는 합계는 완결된 블록(자식이 있는 머리)만 — "VII.법인세등 / 법인세등" 처럼
                # 머리 바로 아래 같은 금액의 잎을 합계로 뒤집지 않는다(실측 회귀)
                continue
            vecs = [[effective(c, y) for y in periods] for c in tail]
            if not has_evidence(tg, vecs):
                continue
            sol = solve_signs(tg, vecs)
            if sol:
                return tail, sol
        return None

    def make_footer(r: ParsedRow, tail: list[ParsedRow], signs: list[int], ambiguous: bool,
                    owner: list[ParsedRow]) -> None:
        for c, s in zip(tail, signs):
            owner.remove(c)
            c.parent, c.sign = r, s
        r.children = list(tail)
        r.kind = ROW_FOOTER
        if ambiguous:
            r.flags.append(FLAG_SIGN_AMBIGUOUS)

    for i, r in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if not r.has_amount() and stype == "BS" and norm(r.label) in BS_SECTION_WORDS:
            r.kind, section = ROW_SECTION_HEADER, BS_SECTION_WORDS[norm(r.label)]
            block_start, stack = len(roots), []
            continue
        r.section = section

        # 바로 앞 행이 "이 행이 더 깊다"는 이유로 머리가 됐고 그 머리가 **다른 노드 안에** 있으면,
        # 이 행은 그 머리의 자식이다 — 합계로 보지 않는다. 그렇지 않으면 원본 오류값이 우연히 같은
        # 금액일 때 잎이 바깥 블록의 합계로 뒤집힌다("지배주주지분 > Ⅰ.자본금 > 자본금").
        # 머리가 최상위면 합계 판정을 그대로 한다 — "IV. 이익잉여금" 다음 "자본총계"(실측 BS공시).
        expect_child = bool(stack) and i > 0 and stack[-1] is rows[i - 1] \
            and stack[-1].kind == ROW_HEADER and not stack[-1].children and stack[-1].parent is not None

        # 1) flat 행 — 합계인지 금액으로 판정
        if r.level is None and expect_child:
            r.level = look(r)
        if r.level is None:
            got = try_footer(r, roots, 2) if r.has_amount() else None
            if got is None and r.has_amount() and roots[block_start:]:
                # 섹션 안 구간은 하나만 묶어도 된다 — "부채총계 = 유동부채" 처럼 자식이 하나인 합계
                got = try_footer(r, roots[block_start:], 1)
                if got is None and r.bold:
                    block = roots[block_start:]
                    got = (block, ([1] * len(block), False))
                    r.flags.append(FLAG_FOOTER_MISMATCH)
            if got:
                tail, (signs, amb) = got
                make_footer(r, tail, signs, amb, roots)
                r.level = LEVEL_FOOTER
                r.parent = None
                roots.append(r)
                block_start = min(block_start, len(roots) - 1)
                stack = [r]
                continue
            if r.bold or not r.has_amount():
                r.kind = ROW_HEADER if r.has_amount() else ROW_TITLE
                r.level = LEVEL_BOLD_HEAD
                while stack and stack[-1].level >= LEVEL_BOLD_HEAD:
                    stack.pop()
                parent = stack[-1] if stack else None
                r.parent = parent
                (parent.children if parent else roots).append(r)
                stack.append(r)
                continue
            r.level = LEVEL_LEAF

        # 2) 접두·들여쓰기 행 — 다음 행이 더 깊으면 머리, 아니면 합계 또는 잎
        level = r.level
        nl = look(nxt)
        is_header = nl is not None and nl > level
        while stack and stack[-1].level >= level:
            stack.pop()
        parent = stack[-1] if stack else None
        owner = parent.children if parent else roots
        # 들여쓴 무접두 행(공시양식의 세부 계정)은 합계가 될 수 없다 — 우연 일치 방지
        if not is_header and r.has_amount() and (r.rank or not r.indent):
            sibs = list(parent.children if parent else roots[block_start:])
            got = try_footer(r, sibs, 2)
            if got:
                tail, (signs, amb) = got
                make_footer(r, tail, signs, amb, owner)
                r.parent = parent
                owner.append(r)
                stack.append(r)
                continue
        r.kind = ROW_HEADER if is_header else (ROW_LEAF if r.has_amount() else ROW_TITLE)
        r.parent = parent
        owner.append(r)
        stack.append(r)

    sheet.roots = roots
    _exclude_per_share(sheet)
    _solve_header_signs(sheet)
    _assign_sections(sheet)


def _exclude_per_share(sheet: ParsedSheet) -> None:
    """주당이익 행은 원/주 단위라 재무제표 단위 금액 트리에 넣지 않는다(마스터 확정 Q7)."""
    def drop(r: ParsedRow) -> None:
        r.excluded = True
        for c in r.children:
            drop(c)

    for r in sheet.rows:
        if r.kind != ROW_SECTION_HEADER and not r.excluded and PER_SHARE_WORD in norm(r.label):
            drop(r)
            r.flags.append(FLAG_EXCLUDED_PER_SHARE)
            owner = r.parent.children if r.parent else sheet.roots
            owner.remove(r)
            r.parent = None


def _solve_header_signs(sheet: ParsedSheet) -> None:
    """머리 소계의 자식 부호 — 깊은 행부터(역순) 풀어야 자식의 유효 금액이 먼저 정해진다."""
    periods = sheet.periods
    for r in reversed(sheet.rows):
        if r.kind != ROW_HEADER or r.excluded or not r.children or not r.has_amount():
            continue
        tg = [r.amounts.get(y) for y in periods]
        vecs = [[effective(c, y) for y in periods] for c in r.children]
        if not has_evidence(tg, vecs):
            continue
        sol = solve_signs(tg, vecs)
        if sol is None:
            r.flags.append(FLAG_SIGN_UNRESOLVED)
            continue
        for c, s in zip(r.children, sol[0]):
            c.sign = s
        if sol[1]:
            r.flags.append(FLAG_SIGN_AMBIGUOUS)


def _assign_sections(sheet: ParsedSheet) -> None:
    stype = sheet.statement_type

    def walk_pl(r: ParsedRow, eff: int) -> None:
        mixed = r.children and len({c.sign for c in r.children}) > 1
        r.section = "profit" if (r.kind == ROW_FOOTER or mixed) else ("revenue" if eff > 0 else "expense")
        for c in r.children:
            walk_pl(c, eff * c.sign)

    def walk_cf(r: ParsedRow, sec: str | None) -> None:
        if sec is None:
            sec = next((v for k, v in CF_SECTION_WORDS if k in norm(r.label)), None)
        r.section = sec or "cf_other"
        for c in r.children:
            walk_cf(c, sec)

    def walk_bs(r: ParsedRow) -> None:
        for c in r.children:
            walk_bs(c)
        if {c.section for c in r.children} >= {"liability", "equity"}:
            r.section = "liability_equity"

    for r in sheet.roots:
        if stype == "PL":
            walk_pl(r, 1)
        elif stype == "CF":
            walk_cf(r, None)
        elif stype == "BS":
            walk_bs(r)
    if stype == "BS":
        missing = [r for r in sheet.account_rows() if not r.section]
        if missing:
            sheet.errors.append(f"재무상태표 섹션(자산·부채·자본)을 정할 수 없는 행이 있습니다: "
                                f"{', '.join(str(r.row_no) for r in missing[:10])}행")


# ── 종류 감지(가로 연도형) ────────────────────────────────────────────

def detect_statement_type(sheet: ParsedSheet) -> str | None:
    """가로 연도형은 제목이 없다 — 행 라벨로 제안한다. 못 정하면 None(사용자 지정 필수)."""
    labels = [norm(r.label) for r in sheet.rows]
    if any("영업활동" in s and "현금흐름" in s for s in labels):
        return "CF"
    if any(s in {"자산총계", "부채총계", "자본총계", "부채와자본총계", "부채및자본총계"} for s in labels) \
            or {"자산", "부채"} <= set(labels):
        return "BS"
    if any("당기순이익" in s or "영업이익" in s or "법인세비용차감전" in s for s in labels):
        return "PL"
    return None


# ── 진단 ────────────────────────────────────────────────────────────

def subtotal_diffs(sheet: ParsedSheet) -> list[dict]:
    """원본 소계 불일치(순수 진단). DB 검증과 별개로 행 단위로 보여 주기 위한 것."""
    out = []
    for r in sheet.rows:
        if r.excluded or not r.is_subtotal:
            continue
        for y in sheet.periods:
            actual = r.amounts.get(y)
            if actual is None:
                continue
            expected = sum((effective(c, y) * c.sign for c in r.children if not c.excluded), ZERO)
            if actual != expected:
                out.append({"row_no": r.row_no, "label": r.label, "fiscal_year": y,
                            "expected": expected, "actual": actual, "diff": actual - expected})
    return out
