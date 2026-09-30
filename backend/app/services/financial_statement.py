"""재무제표·계정 트리 서비스 — ADR-0037, 8-A.

세 가지를 한다.

1. **트리** — 재귀 CTE 로 계정 트리·자손을 조회한다. ORM `select().cte(recursive=True)` 로 쓴다 —
   tenant 자동 필터(`with_loader_criteria`)가 anchor·재귀부 양쪽에 걸린다. `text()` 원시 SQL 은
   자동 필터를 우회하므로 쓰지 않는다.
2. **쓰기 함수** — 계정·재무제표·금액. 8-A 에는 쓰기 API 가 없고 8-B 파서가 이 함수를 부른다
   (마스터 확정 Q5). 순환 부모·섹션 불일치·확정 후 수정은 여기서 막는다.
3. **검증** — 확정을 막는 관문이다(§2.8). 자산=부채+자본, 소계=하위합, 단위·구조 규칙.
   **계정명 문자열을 비교하지 않는다** — `section`·`is_subtotal`·`rollup_sign`·트리 구조만 본다.
   차액은 **재무제표 단위 그대로**다(원으로 환산하지 않는다).
"""
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import literal, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.financial_statement import (
    FS_AMOUNT_SCALE,
    FS_BASES,
    FS_DEFAULT_CURRENCY,
    FS_ROLLUP_SIGNS,
    FS_SECTION_ASSET,
    FS_SECTION_EQUITY,
    FS_SECTION_LIABILITY,
    FS_SECTION_LIABILITY_EQUITY,
    FS_SECTIONS_BY_STATEMENT,
    FS_SOURCE_KINDS,
    FS_STATEMENT_BS,
    FS_STATEMENT_TYPES,
    FS_STATUS_DRAFT,
    FS_STATUS_FINAL,
    FS_UNITS,
    FsAccount,
    FsAmount,
    FsStatement,
    FsStatementStatusEvent,
)

# ── 검증 규칙 코드 — 응답·이력에 그대로 나간다 ─────────────────────
RULE_BALANCE = "balance"                          # 자산 = 부채 + 자본
RULE_BALANCE_MISSING_SECTION = "balance_missing_section"  # 자산 또는 부채·자본 측이 통째로 없음
RULE_SUBTOTAL = "subtotal"                        # 소계 = Σ(하위 × rollup_sign)
RULE_SUBTOTAL_NO_CHILDREN = "subtotal_no_children"        # Q6(a) 소계인데 하위 0개 → 실패
RULE_SUBTOTAL_AMOUNT_MISSING = "subtotal_amount_missing"  # Q6(b) 하위는 있으나 소계 금액 비어 있음 → skipped
RULE_INVALID_UNIT = "invalid_unit"
RULE_ACCOUNT_STATEMENT_MISMATCH = "account_statement_mismatch"
RULE_ACCOUNT_NOT_VALID_FOR_YEAR = "account_not_valid_for_year"
RULE_INVALID_SECTION = "invalid_section"
RULE_EMPTY_STATEMENT = "empty_statement"
RULE_SUSPENSE_UNRESOLVED = "suspense_unresolved"  # 원본 차이를 담은 임시계정이 아직 검토되지 않음 → 확정 거부


def is_suspense(row: FsAmount) -> bool:
    """임시계정(원본 차이) 금액 행 — `raw_meta.suspense` 표식으로만 판정한다(계정명 비교 없음)."""
    return isinstance(row.raw_meta, dict) and bool(row.raw_meta.get("suspense"))


def is_unresolved_suspense(row: FsAmount) -> bool:
    return is_suspense(row) and not row.raw_meta.get("resolved") and bool(row.amount)


class FsError(ValueError):
    """입력 오류 — API 에서는 422."""


class FsConflictError(Exception):
    """상태 충돌(확정 후 수정 등) — API 에서는 409."""


class FsNotFoundError(LookupError):
    """대상 없음 — API 에서는 404."""


class FsValidationError(Exception):
    """검증 실패로 확정 거부. `result` 에 항목별 오류가 있다."""

    def __init__(self, result: dict):
        super().__init__("검증에 실패해 확정할 수 없습니다")
        self.result = result


def _alive(model):
    return model.is_deleted == False  # noqa: E712


def _valid_in(model, fiscal_year: int):
    return (or_(model.valid_from_year.is_(None), model.valid_from_year <= fiscal_year)
            & or_(model.valid_to_year.is_(None), model.valid_to_year >= fiscal_year))


def is_valid_for_year(account: FsAccount, fiscal_year: int) -> bool:
    return ((account.valid_from_year is None or account.valid_from_year <= fiscal_year)
            and (account.valid_to_year is None or account.valid_to_year >= fiscal_year))


# ── 트리 (재귀 CTE) ─────────────────────────────────────────────────

def descendant_ids(db: Session, account_id: UUID) -> set[UUID]:
    """자기 자신을 뺀 모든 자손 id. 순환 검사에 쓴다."""
    tree = (select(FsAccount.id).where(FsAccount.parent_id == account_id, _alive(FsAccount))
            .cte("fs_descendants", recursive=True))
    child = aliased(FsAccount)
    tree = tree.union_all(select(child.id).join(tree, child.parent_id == tree.c.id).where(_alive(child)))
    return set(db.scalars(select(tree.c.id)).all())


def account_tree_rows(db: Session, statement_type: str, fiscal_year: int | None = None
                      ) -> list[tuple[FsAccount, int]]:
    """재무제표 종류의 계정 트리를 (계정, 깊이) 로 돌려준다. 루트 깊이 0.

    `fiscal_year` 를 주면 그 연도에 유효한 계정만 — **유효하지 않은 부모 아래 가지는 통째로 빠진다**
    (CTE 재귀부가 유효 계정만 따라 내려간다). 순서는 호출자가 `build_tree` 로 정한다.
    """
    anchor = select(FsAccount.id, literal(0).label("depth")).where(
        FsAccount.statement_type == statement_type, FsAccount.parent_id.is_(None), _alive(FsAccount))
    if fiscal_year is not None:
        anchor = anchor.where(_valid_in(FsAccount, fiscal_year))
    tree = anchor.cte("fs_tree", recursive=True)
    child = aliased(FsAccount)
    step = select(child.id, (tree.c.depth + 1).label("depth")).join(
        tree, child.parent_id == tree.c.id).where(_alive(child))
    if fiscal_year is not None:
        step = step.where(_valid_in(child, fiscal_year))
    tree = tree.union_all(step)
    rows = db.execute(select(FsAccount, tree.c.depth).join(tree, FsAccount.id == tree.c.id)).all()
    return [(a, d) for a, d in rows]


def build_tree(rows: list[tuple[FsAccount, int]], payload) -> list[dict]:
    """(계정, 깊이) 목록을 중첩 트리로. 형제는 `sort_order` 순. `payload(account, depth)` 가 노드 dict."""
    by_parent: dict[UUID | None, list[tuple[FsAccount, int]]] = {}
    ids = {a.id for a, _ in rows}
    for a, d in rows:
        by_parent.setdefault(a.parent_id if a.parent_id in ids else None, []).append((a, d))

    def walk(pid):
        out = []
        for a, d in sorted(by_parent.get(pid, []), key=lambda x: (x[0].sort_order, x[0].created_at)):
            node = payload(a, d)
            node["children"] = walk(a.id)
            out.append(node)
        return out
    return walk(None)


# ── 쓰기 함수 (8-B 가 부른다) ───────────────────────────────────────

def get_account(db: Session, account_id: UUID) -> FsAccount:
    a = db.scalars(select(FsAccount).where(FsAccount.id == account_id, _alive(FsAccount))).first()
    if a is None:
        raise FsNotFoundError("계정을 찾을 수 없습니다")
    return a


def get_statement(db: Session, statement_id: UUID) -> FsStatement:
    s = db.scalars(select(FsStatement).where(FsStatement.id == statement_id, _alive(FsStatement))).first()
    if s is None:
        raise FsNotFoundError("재무제표를 찾을 수 없습니다")
    return s


def _check_parent(db: Session, account: FsAccount, parent_id: UUID | None) -> None:
    """부모 지정 검사 — 자기 자신·자기 자손 거부, 같은 재무제표 종류, BS 섹션 호환."""
    if parent_id is None:
        return
    if account.id is not None and parent_id == account.id:
        raise FsError("자기 자신을 부모로 지정할 수 없습니다")
    parent = get_account(db, parent_id)
    if parent.statement_type != account.statement_type:
        raise FsError("부모 계정의 재무제표 종류가 다릅니다")
    if account.id is not None and parent_id in descendant_ids(db, account.id):
        raise FsError("자기 자손을 부모로 지정할 수 없습니다 — 순환이 생깁니다")
    if account.statement_type == FS_STATEMENT_BS:
        # BS 는 섹션을 넘어 매달 수 없다 — 섹션 합계가 두 번 잡힌다. 부채와자본 아래만 부채·자본 허용
        ok = (parent.section == account.section
              or (parent.section == FS_SECTION_LIABILITY_EQUITY
                  and account.section in (FS_SECTION_LIABILITY, FS_SECTION_EQUITY)))
        if not ok:
            raise FsError("재무상태표에서는 다른 섹션 계정 아래에 둘 수 없습니다")


def create_account(db: Session, *, statement_type: str, name: str, section: str,
                   parent_id: UUID | None = None, sort_order: int = 0, code: str | None = None,
                   is_subtotal: bool = False, rollup_sign: int = 1,
                   valid_from_year: int | None = None, valid_to_year: int | None = None) -> FsAccount:
    if statement_type not in FS_STATEMENT_TYPES:
        raise FsError(f"재무제표 종류가 올바르지 않습니다: {statement_type}")
    if section not in FS_SECTIONS_BY_STATEMENT[statement_type]:
        raise FsError(f"'{statement_type}' 에 쓸 수 없는 섹션입니다: {section}")
    if rollup_sign not in FS_ROLLUP_SIGNS:
        raise FsError("합산 부호는 1 또는 -1 이어야 합니다")
    if valid_from_year is not None and valid_to_year is not None and valid_from_year > valid_to_year:
        raise FsError("유효 시작 연도가 종료 연도보다 늦습니다")
    a = FsAccount(statement_type=statement_type, name=name, section=section, sort_order=sort_order,
                  code=code, is_subtotal=is_subtotal, rollup_sign=rollup_sign,
                  valid_from_year=valid_from_year, valid_to_year=valid_to_year)
    _check_parent(db, a, parent_id)
    a.parent_id = parent_id
    db.add(a)
    db.flush()
    return a


def set_parent(db: Session, account: FsAccount, parent_id: UUID | None) -> None:
    """부모 변경. 자기 자신·자기 자손이면 거부(`FsError`)."""
    _check_parent(db, account, parent_id)
    account.parent_id = parent_id
    db.flush()


def set_subtotal(db: Session, account: FsAccount, is_subtotal: bool) -> None:
    """소계 여부 변경 — 8-B2 가 공시 행 아래에 정산표 계정을 붙일 때 그 공시 행을 소계로 바꾼다.

    **이 계정에 금액 행이 있는 확정 재무제표가 있으면 거부**(`FsConflictError`) — 확정 후 검증 결과가
    바뀌면 안 된다(§2.10). 호출자는 draft 재무제표에 하위 금액도 함께 넣어야 한다(Q6a).
    """
    if account.is_subtotal == is_subtotal:
        return
    final = db.scalars(select(FsStatement.fiscal_year).join(FsAmount, FsAmount.statement_id == FsStatement.id)
                       .where(FsAmount.account_id == account.id, _alive(FsAmount), _alive(FsStatement),
                              FsStatement.status == FS_STATUS_FINAL)).all()
    if final:
        raise FsConflictError(f"확정된 재무제표({', '.join(str(y) for y in sorted(set(final)))})가 쓰는 계정입니다 "
                              "— 재오픈 후 변경하세요")
    account.is_subtotal = is_subtotal
    db.flush()


def retire_account(db: Session, account: FsAccount, last_year: int) -> None:
    """폐지 — 행을 지우지 않고 유효 종료 연도를 둔다(§2.10). 과거 연도 금액은 그대로 조회된다."""
    if account.valid_from_year is not None and last_year < account.valid_from_year:
        raise FsError("유효 시작 연도보다 이른 연도로 폐지할 수 없습니다")
    account.valid_to_year = last_year
    db.flush()


def _check_amount(value: Decimal | None, label: str) -> Decimal | None:
    """소수 자릿수 초과는 거부한다 — 조용히 반올림하지 않는다(마스터 확정 Q1)."""
    if value is None:
        return None
    d = Decimal(value) if not isinstance(value, Decimal) else value
    if not d.is_finite():
        raise FsError(f"{label} 값이 올바르지 않습니다")
    if d != d.quantize(Decimal(1).scaleb(-FS_AMOUNT_SCALE)):
        raise FsError(f"{label} 은 소수 {FS_AMOUNT_SCALE}자리까지만 저장합니다: {d}")
    return d


def create_statement(db: Session, *, fiscal_year: int, statement_type: str, basis: str,
                     unit: int = 1, currency: str = FS_DEFAULT_CURRENCY, tolerance: Decimal | int = 0,
                     source_kind: str | None = None, source_filename: str | None = None,
                     source_sheet: str | None = None) -> FsStatement:
    if statement_type not in FS_STATEMENT_TYPES:
        raise FsError(f"재무제표 종류가 올바르지 않습니다: {statement_type}")
    if basis not in FS_BASES:
        raise FsError(f"연결·별도 구분이 올바르지 않습니다: {basis}")
    if unit not in FS_UNITS:
        raise FsError(f"단위가 올바르지 않습니다: {unit}")
    if source_kind is not None and source_kind not in FS_SOURCE_KINDS:
        raise FsError(f"원천 형태가 올바르지 않습니다: {source_kind}")
    tol = _check_amount(Decimal(tolerance), "허용 오차")
    if tol < 0:
        raise FsError("허용 오차는 0 이상이어야 합니다")
    s = FsStatement(fiscal_year=fiscal_year, statement_type=statement_type, basis=basis, unit=unit,
                    currency=currency, tolerance=tol, status=FS_STATUS_DRAFT, source_kind=source_kind,
                    source_filename=source_filename, source_sheet=source_sheet)
    db.add(s)
    db.flush()
    return s


def _ensure_draft(statement: FsStatement) -> None:
    if statement.status != FS_STATUS_DRAFT:
        raise FsConflictError("확정된 재무제표는 수정할 수 없습니다 — 재오픈 후 수정하세요")


def set_tolerance(db: Session, statement: FsStatement, tolerance: Decimal | int) -> None:
    _ensure_draft(statement)
    tol = _check_amount(Decimal(tolerance), "허용 오차")
    if tol < 0:
        raise FsError("허용 오차는 0 이상이어야 합니다")
    statement.tolerance = tol
    db.flush()


def set_amount(db: Session, statement: FsStatement, account: FsAccount, amount: Decimal | int | None, *,
               raw_row_no: int | None = None, raw_label: str | None = None, raw_indent: int | None = None,
               raw_value: str | None = None, raw_meta: dict | None = None) -> FsAmount:
    """금액 1행 저장(있으면 갱신). 금액은 **공시 표시 그대로**(괄호=음수). 확정 상태면 거부."""
    _ensure_draft(statement)
    if account.statement_type != statement.statement_type:
        raise FsError("계정의 재무제표 종류가 재무제표와 다릅니다")
    if not is_valid_for_year(account, statement.fiscal_year):
        raise FsError(f"{statement.fiscal_year} 회계연도에 유효하지 않은 계정입니다")
    value = _check_amount(Decimal(amount) if amount is not None else None, "금액")
    row = db.scalars(select(FsAmount).where(FsAmount.statement_id == statement.id,
                                            FsAmount.account_id == account.id, _alive(FsAmount))).first()
    if row is None:
        row = FsAmount(statement_id=statement.id, account_id=account.id)
        db.add(row)
    row.amount = value
    row.raw_row_no, row.raw_label, row.raw_indent = raw_row_no, raw_label, raw_indent
    row.raw_value, row.raw_meta = raw_value, raw_meta
    db.flush()
    return row


# ── 검증 ────────────────────────────────────────────────────────────

def statement_rows(db: Session, statement: FsStatement) -> list[tuple[FsAmount, FsAccount]]:
    return [(r, a) for r, a in db.execute(
        select(FsAmount, FsAccount).join(FsAccount, FsAccount.id == FsAmount.account_id)
        .where(FsAmount.statement_id == statement.id, _alive(FsAmount))).all()]


def _item(rule: str, account: FsAccount | None, *, expected=None, actual=None, diff=None) -> dict:
    # 계정명은 **표시용으로만** 싣는다. 판정에 쓰지 않는다
    return {"rule": rule,
            "account_id": account.id if account else None,
            "account_code": account.code if account else None,
            "account_name": account.name if account else None,
            "expected": expected, "actual": actual, "diff": diff}


def validate(db: Session, statement: FsStatement) -> dict:
    """재무제표 검증. `errors` 가 비어야 확정할 수 있다.

    반환:
    - `errors`  — 확정을 막는 항목. 어긋난 계정·기대값·실제값·차액(재무제표 단위)
    - `skipped` — 확정을 막지 않지만 검사하지 못한 소계(Q6(b)). 건수가 확정 이력에 남는다
    - `checks`  — 수행한 금액 비교 전부(통과 포함). 허용 오차로 확정할 때 이력에 차액을 남긴다

    **금액 트리**: 금액 행이 있는 계정 + 그 조상. 금액 행이 없는 조상(중간 제목)은 금액 없는
    노드로 넣어, 윗 소계가 그 아래 금액을 빠뜨리지 않게 한다.
    **유효 금액**: 금액이 있으면 그 값, 비어 있으면 하위 유효 금액 × rollup_sign 합, 하위도 없으면 0.
    """
    tol: Decimal = statement.tolerance or Decimal("0")
    errors: list[dict] = []
    skipped: list[dict] = []
    checks: list[dict] = []

    if statement.unit not in FS_UNITS:
        errors.append(_item(RULE_INVALID_UNIT, None, actual=statement.unit))

    rows = statement_rows(db, statement)
    if not rows:
        errors.append(_item(RULE_EMPTY_STATEMENT, None))
    amount_of: dict[UUID, Decimal | None] = {}
    for r, a in rows:
        amount_of[a.id] = r.amount
        if a.statement_type != statement.statement_type:
            errors.append(_item(RULE_ACCOUNT_STATEMENT_MISMATCH, a))
        if not is_valid_for_year(a, statement.fiscal_year):
            errors.append(_item(RULE_ACCOUNT_NOT_VALID_FOR_YEAR, a))
        if a.section not in FS_SECTIONS_BY_STATEMENT.get(statement.statement_type, ()):
            errors.append(_item(RULE_INVALID_SECTION, a))
        if is_unresolved_suspense(r):
            # 합계는 맞지만 원본 차이를 임시계정에 넣어 둔 상태 — ICFR 관리자 검토 전에는 확정하지 않는다
            errors.append(_item(RULE_SUSPENSE_UNRESOLVED, a, actual=r.amount))

    # 금액 행 계정 + 조상 (같은 종류 계정 전체를 한 번에 읽어 위로 걷는다)
    all_accounts = {a.id: a for a in db.scalars(select(FsAccount).where(
        FsAccount.statement_type == statement.statement_type, _alive(FsAccount))).all()}
    for _, a in rows:
        all_accounts.setdefault(a.id, a)
    present: dict[UUID, FsAccount] = {}
    for _, a in rows:
        cur, seen = a, set()
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            present[cur.id] = cur
            cur = all_accounts.get(cur.parent_id) if cur.parent_id else None
    children: dict[UUID, list[FsAccount]] = {}
    for a in present.values():
        if a.parent_id in present:
            children.setdefault(a.parent_id, []).append(a)

    memo: dict[UUID, Decimal] = {}

    def rolled(a: FsAccount) -> Decimal:
        return sum((effective(c) * c.rollup_sign for c in children.get(a.id, [])), Decimal("0"))

    def effective(a: FsAccount) -> Decimal:
        if a.id not in memo:
            memo[a.id] = Decimal("0")   # 데이터에 순환이 있어도 무한 재귀하지 않게
            amt = amount_of.get(a.id)
            memo[a.id] = amt if amt is not None else rolled(a)
        return memo[a.id]

    # 소계 = 하위합 — 금액 행이 있는 소계만 (금액 행 없는 조상은 제목일 뿐이다)
    for _, a in sorted(rows, key=lambda x: (x[1].sort_order, str(x[1].id))):
        if not a.is_subtotal:
            continue
        if not children.get(a.id):
            errors.append(_item(RULE_SUBTOTAL_NO_CHILDREN, a, actual=amount_of[a.id]))
            continue
        if amount_of[a.id] is None:
            skipped.append(_item(RULE_SUBTOTAL_AMOUNT_MISSING, a, expected=rolled(a)))
            continue
        expected, actual = rolled(a), amount_of[a.id]
        diff = actual - expected
        checks.append(_item(RULE_SUBTOTAL, a, expected=expected, actual=actual, diff=diff))
        if abs(diff) > tol:
            errors.append(_item(RULE_SUBTOTAL, a, expected=expected, actual=actual, diff=diff))

    # 자산 = 부채 + 자본 (BS). 섹션 합계 = 부모가 없거나 부모 섹션이 다른 최상위 노드의 유효 금액 합
    if statement.statement_type == FS_STATEMENT_BS and rows:
        totals = {FS_SECTION_ASSET: [], FS_SECTION_LIABILITY: [], FS_SECTION_EQUITY: []}
        for a in present.values():
            parent = present.get(a.parent_id) if a.parent_id else None
            if a.section in totals and (parent is None or parent.section != a.section):
                totals[a.section].append(effective(a))
        if not totals[FS_SECTION_ASSET] or not (totals[FS_SECTION_LIABILITY] or totals[FS_SECTION_EQUITY]):
            errors.append(_item(RULE_BALANCE_MISSING_SECTION, None))
        else:
            asset = sum(totals[FS_SECTION_ASSET], Decimal("0"))
            le = sum(totals[FS_SECTION_LIABILITY], Decimal("0")) + sum(totals[FS_SECTION_EQUITY], Decimal("0"))
            diff = asset - le
            checks.append(_item(RULE_BALANCE, None, expected=le, actual=asset, diff=diff))
            if abs(diff) > tol:
                errors.append(_item(RULE_BALANCE, None, expected=le, actual=asset, diff=diff))

    return {"statement_id": statement.id, "ok": not errors, "unit": statement.unit,
            "currency": statement.currency, "tolerance": tol,
            "errors": errors, "skipped": skipped, "checks": checks}


# ── 상태 전환 ───────────────────────────────────────────────────────

def _s(v: Decimal | None) -> str | None:
    return None if v is None else str(v)


def finalize(db: Session, statement: FsStatement, actor_id: UUID, reason: str | None = None) -> dict:
    """draft → final. **검증 실패면 거부**(`FsValidationError`) — 경고만 남기고 통과시키지 않는다.

    이력 행에 허용 오차와 skipped 건수를 남긴다. 허용 오차가 0 이 아니면 비교별 실제 차액도 남긴다.
    """
    if statement.status != FS_STATUS_DRAFT:
        raise FsConflictError("이미 확정된 재무제표입니다")
    result = validate(db, statement)
    if not result["ok"]:
        raise FsValidationError(result)
    tol = result["tolerance"]
    diffs = None
    if tol != 0:
        diffs = [{"rule": c["rule"], "account_id": _s(c["account_id"]), "diff": _s(c["diff"])}
                 for c in result["checks"]]
    now = datetime.now(UTC)
    db.add(FsStatementStatusEvent(
        statement_id=statement.id, from_status=FS_STATUS_DRAFT, to_status=FS_STATUS_FINAL,
        reason=(reason or "").strip() or None, actor_id=actor_id, occurred_at=now,
        tolerance=tol, skipped_count=len(result["skipped"]), tolerance_diffs=diffs))
    statement.status, statement.finalized_at, statement.finalized_by_id = FS_STATUS_FINAL, now, actor_id
    db.flush()
    return result


def reopen(db: Session, statement: FsStatement, actor_id: UUID, reason: str | None) -> None:
    """final → draft. **사유 필수.** 이력 행을 남기고 현재 확정 정보를 비운다."""
    if statement.status != FS_STATUS_FINAL:
        raise FsConflictError("확정된 재무제표만 재오픈할 수 있습니다")
    reason = (reason or "").strip()
    if not reason:
        raise FsError("재오픈 사유가 필요합니다")
    db.add(FsStatementStatusEvent(
        statement_id=statement.id, from_status=FS_STATUS_FINAL, to_status=FS_STATUS_DRAFT,
        reason=reason, actor_id=actor_id, occurred_at=datetime.now(UTC)))
    statement.status, statement.finalized_at, statement.finalized_by_id = FS_STATUS_DRAFT, None, None
    db.flush()


def status_events(db: Session, statement_id: UUID) -> list[FsStatementStatusEvent]:
    return list(db.scalars(select(FsStatementStatusEvent).where(
        FsStatementStatusEvent.statement_id == statement_id, _alive(FsStatementStatusEvent))
        .order_by(FsStatementStatusEvent.occurred_at, FsStatementStatusEvent.created_at)).all())
