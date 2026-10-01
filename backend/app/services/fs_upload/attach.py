"""정산표 결합 업로드 — 공시 재무제표에 정산표(COA) 계정을 붙인다 (8-B2, ADR-0037 §3.2).

8-C STEP 0 실측(`prompts/ICFR_backend_fs-8c_20260929.md` 0.2·0.3): 스코핑 템플릿 BS·PL 은 **정산표(COA) 입도**다
(정확일치 BS 55/58·PL 44/45, 공시양식과는 6·1). 정산표의 매핑 열로 COA 잎을 합하면 공시 행 금액과
전부 일치한다(BS 58/58·PL 14/14). 그래서 계정 마스터는 **공시 행 = 부모, COA 계정 = 그 아래 잎인 단일 트리**다
(마스터 확정 D1). 붙이고 나면 공시 행은 소계가 되고 8-A 검증(소계 = 하위합)이 두 원천의 정합성을 확인한다.

규칙:
- 대상은 **이미 올린 공시 재무제표**(같은 종류·연결별도)의 연도뿐이다. 정산표의 다른 연도는 건너뛴다(경고).
- 대상 재무제표는 전부 draft 여야 한다 — final 이면 409(재오픈 후). 공시 행을 소계로 바꾸면 검증 결과가 바뀐다.
- 매핑 열 값 → (선택) `category_map` → 공시 계정 이름. **PL 분류명(매출액 등)은 공시 행 이름과 달라 대응표를
  입력으로 받는다 — 추정하지 않는다.** 대응이 없는 잎은 금액이 전부 0 일 때만 건너뛰고(경고), 아니면 막는다.
- 정산표의 중간 그룹(`당좌자산` 등)·합계 행은 계정으로 만들지 않는다 — `raw_meta.source_path` 에만 남긴다.
- 같은 공시 행 아래 같은 이름이 반복되면(`감가상각누계액` ×4) 직전 계정명을 붙여 구분한다
  (`감가상각누계액_건물`) — 스코핑 템플릿의 표기와 같다(8-C 매칭). 원문은 `raw_label` 에 그대로 남는다.
- 결합으로 만든 금액 행은 `raw_meta.attach = true` — 다시 붙일 때 기존 COA 계정을 찾는 표식이다.
"""
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial_statement import (
    FS_BASES,
    FS_BASIS_SEPARATE,
    FS_STATUS_FINAL,
    FS_UNITS,
    FsAccount,
    FsAmount,
    FsStatement,
)
from app.services import financial_statement as svc
from app.services import fs_suspense
from app.services.fs_upload.cells import norm, split_prefix
from app.services.fs_upload.parsed import KIND_HORIZONTAL, ROW_LEAF, ParsedRow, ParsedSheet

FINALIZE_REASON = "정산표 결합(8-B2) 후 자동 확정 — 최신 연도 검증 통과"
MIN_BRIDGE_MATCH = 0.5   # 매핑 열 후보: 값 종류의 절반 이상이 공시 계정과 맞아야 한다


def key(text: str | None) -> str:
    """이름 비교 키 — 접두 번호("I. 자본금")와 공백을 뗀다."""
    return norm(split_prefix(text or "")[1])


@dataclass
class AttachOptions:
    basis: str | None = None
    unit: int | None = None
    bridge_column: str | None = None
    category_map: dict[str, str] | None = None
    fiscal_years: list[int] | None = None
    finalize: bool = True
    filename: str | None = None


@dataclass
class AttachRow:
    row: ParsedRow
    name: str                                  # 계정명(반복 이름은 직전 계정명을 붙여 구분)
    bridge: str | None                         # 매핑 열 원문
    source_path: list[str]                     # 정산표 안의 상위 그룹(계정으로 만들지 않는다)
    target: FsAccount | None = None            # 부모가 될 공시 계정
    existing: FsAccount | None = None          # 이미 붙어 있는 COA 계정(재결합)
    skip_reason: str | None = None


@dataclass
class AttachPlan:
    basis: str | None = None
    unit: int | None = None
    bridge_column: str | None = None
    bridge_candidates: list[dict] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    statements: dict[int, FsStatement] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    rows: list[AttachRow] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.errors)

    def targets(self) -> list[FsAccount]:
        seen: dict[UUID, FsAccount] = {}
        for r in self.rows:
            if r.target is not None and r.skip_reason is None:
                seen.setdefault(r.target.id, r.target)
        return list(seen.values())


def _alive(model):
    return model.is_deleted == False  # noqa: E712


def _source_path(r: ParsedRow) -> list[str]:
    out, cur = [], r.parent
    while cur is not None:
        out.append(cur.label)
        cur = cur.parent
    return list(reversed(out))


def _leaf_rows(sheet: ParsedSheet) -> list[ParsedRow]:
    return [r for r in sheet.account_rows() if r.kind == ROW_LEAF and not r.children]


def _attached_ids(db: Session, stype: str) -> set[UUID]:
    """결합으로 만든 COA 계정 — 금액 행 `raw_meta.attach` 표식으로 찾는다(JSON 질의는 DB 마다 달라 파이썬에서 본다)."""
    rows = db.execute(select(FsAmount.account_id, FsAmount.raw_meta)
                      .join(FsAccount, FsAccount.id == FsAmount.account_id)
                      .where(FsAccount.statement_type == stype, _alive(FsAmount), _alive(FsAccount))).all()
    return {aid for aid, meta in rows if isinstance(meta, dict) and meta.get("attach")}


def plan(db: Session, sheet: ParsedSheet, opts: AttachOptions) -> AttachPlan:
    p = AttachPlan(errors=list(sheet.errors), warnings=list(sheet.warnings))
    if sheet.errors:
        return p
    if sheet.kind != KIND_HORIZONTAL:
        p.errors.append("정산표(가로 연도형)만 공시 재무제표에 붙일 수 있습니다")
        return p
    stype = sheet.statement_type

    if opts.basis is not None and opts.basis not in FS_BASES:
        p.errors.append(f"연결·별도 구분이 올바르지 않습니다: {opts.basis}")
        return p
    p.basis = opts.basis or FS_BASIS_SEPARATE

    # 대상 재무제표 — 이미 올린 공시 재무제표의 연도
    stmts = {s.fiscal_year: s for s in db.scalars(select(FsStatement).where(
        FsStatement.statement_type == stype, FsStatement.basis == p.basis, _alive(FsStatement))).all()}
    if opts.fiscal_years:
        bad = [y for y in opts.fiscal_years if y not in sheet.periods or y not in stmts]
        if bad:
            p.errors.append(f"정산표 열과 공시 재무제표가 모두 있는 연도가 아닙니다: {bad}")
        p.years = sorted({y for y in opts.fiscal_years if y in sheet.periods and y in stmts}, reverse=True)
    else:
        p.years = [y for y in sheet.periods if y in stmts]
        rest = [y for y in sheet.periods if y not in stmts]
        if rest:
            p.warnings.append(f"공시 재무제표가 없는 연도는 건너뜁니다: {rest}")
    if not p.years:
        p.errors.append("붙일 공시 재무제표가 없습니다 — 공시양식을 먼저 올리세요")
        return p
    p.statements = {y: stmts[y] for y in p.years}

    # 단위 — 정산표에는 단위 표기가 없다(실측). 지정값이 재무제표 단위와 같아야 한다
    unit = opts.unit if opts.unit is not None else sheet.unit
    if unit is None:
        p.errors.append("정산표 단위를 지정하세요(unit) — 붙일 재무제표와 같아야 합니다")
    elif unit not in FS_UNITS:
        p.errors.append(f"단위가 올바르지 않습니다: {unit}")
    else:
        diff = [y for y, s in p.statements.items() if s.unit != unit]
        if diff:
            p.errors.append(f"정산표 단위({unit})가 재무제표 단위와 다릅니다: {diff}")
    p.unit = unit

    for y, s in p.statements.items():
        if s.status == FS_STATUS_FINAL:
            p.conflicts.append({"fiscal_year": y, "statement_id": s.id, "status": s.status})

    # 공시 계정 후보 — 결합으로 만든 COA 계정은 제외. 같은 이름이면 트리에서 가장 위(부모)를 고른다
    accounts = list(db.scalars(select(FsAccount).where(FsAccount.statement_type == stype, _alive(FsAccount))).all())
    attached = _attached_ids(db, stype)
    by_id = {a.id: a for a in accounts}

    def depth(a: FsAccount) -> int:
        d, cur, seen = 0, a, set()
        while cur.parent_id and cur.parent_id in by_id and cur.id not in seen:
            seen.add(cur.id)
            d, cur = d + 1, by_id[cur.parent_id]
        return d

    names: dict[str, list[FsAccount]] = {}
    for a in accounts:
        if a.id not in attached:
            names.setdefault(key(a.name), []).append(a)
    if not names:
        p.errors.append("이 종류의 공시 계정이 없습니다 — 공시양식을 먼저 올리세요")
        return p

    cmap = {key(k): v for k, v in (opts.category_map or {}).items()}

    def resolve(value: str | None) -> FsAccount | None:
        if value is None:
            return None
        cands = names.get(key(cmap.get(key(value), value)), [])
        if not cands:
            return None
        top = min(depth(a) for a in cands)
        tops = [a for a in cands if depth(a) == top]
        return tops[0] if len(tops) == 1 else None

    # 매핑 열 — 지정 또는 공시 계정과 가장 많이 맞는 열
    leaves = _leaf_rows(sheet)
    cols = sorted({c for r in leaves for c in (r.meta.get("annotations") or {})})
    for c in cols:
        vals = {r.meta["annotations"][c] for r in leaves if c in (r.meta.get("annotations") or {})}
        hit = sum(1 for v in vals if resolve(v) is not None)
        p.bridge_candidates.append({"column": c, "values": len(vals), "matched": hit})
    if opts.bridge_column:
        if opts.bridge_column not in cols:
            p.errors.append(f"매핑 열 {opts.bridge_column} 에 값이 없습니다(있는 열: {cols})")
            return p
        p.bridge_column = opts.bridge_column
    else:
        ok = [c for c in p.bridge_candidates if c["values"] and c["matched"] / c["values"] >= MIN_BRIDGE_MATCH]
        if not ok:
            p.errors.append("공시 계정과 맞는 매핑 열을 찾지 못했습니다 — bridge_column 과 category_map 을 지정하세요 "
                            f"(열별 일치: {p.bridge_candidates})")
            return p
        p.bridge_column = max(ok, key=lambda c: (c["matched"] / c["values"], c["matched"]))["column"]

    # 행별 대응
    unmatched: Counter[str] = Counter()
    for r in leaves:
        bridge = (r.meta.get("annotations") or {}).get(p.bridge_column)
        ar = AttachRow(row=r, name=r.label, bridge=bridge, source_path=_source_path(r))
        zero = all(not r.amounts.get(y) for y in p.years)
        ar.target = resolve(bridge)
        if ar.target is None:
            if zero:
                ar.skip_reason = "대응 공시 계정 없음 · 대상 연도 금액 0"
            elif bridge is None:
                p.errors.append(f"{r.row_no}행 '{r.label}': 매핑 열({p.bridge_column}) 값이 없습니다")
            else:
                unmatched[bridge] += 1
        if r.errors:
            p.errors.append(f"{r.row_no}행 '{r.label}': {'; '.join(r.errors)}")
        p.rows.append(ar)
    for v, n in unmatched.items():
        p.errors.append(f"매핑 값 '{v}'({n}행)에 대응하는 공시 계정이 없습니다 — category_map 으로 지정하세요")
    p.unmatched = sorted(unmatched)
    for ar in p.rows:
        if ar.skip_reason:
            p.warnings.append(f"{ar.row.row_no}행 '{ar.row.label}' 건너뜀: {ar.skip_reason}")

    _disambiguate(p.rows)
    _check_targets(db, p, attached, accounts)
    return p


def _disambiguate(rows: list[AttachRow]) -> None:
    """같은 공시 계정 아래 반복 이름 → `이름_직전계정명`. 그래도 겹치면 순번."""
    by_target: dict[UUID, list[AttachRow]] = {}
    for ar in rows:
        if ar.target is not None and ar.skip_reason is None:
            by_target.setdefault(ar.target.id, []).append(ar)
    for group in by_target.values():
        counts = Counter(key(ar.row.label) for ar in group)
        prev: str | None = None
        for ar in group:
            if counts[key(ar.row.label)] > 1 and prev:
                ar.name = f"{ar.row.label}_{prev}"
            else:
                prev = ar.row.label
        seen: Counter[str] = Counter()
        for ar in group:
            seen[ar.name] += 1
            if seen[ar.name] > 1:
                ar.name = f"{ar.name}_{seen[ar.name]}"


def _check_targets(db: Session, p: AttachPlan, attached: set[UUID], accounts: list[FsAccount]) -> None:
    """부모가 될 공시 계정 검사 + 기존 COA 계정 찾기."""
    children: dict[UUID, list[FsAccount]] = {}
    for a in accounts:
        if a.parent_id:
            children.setdefault(a.parent_id, []).append(a)
    for t in p.targets():
        own = children.get(t.id, [])
        disclosure_kids = [c for c in own if c.id not in attached]
        if disclosure_kids:
            p.errors.append(f"'{t.name}' 은 공시 하위 계정이 있는 소계라 정산표 계정을 붙일 수 없습니다 "
                            "(매핑 열은 가장 아래 공시 행을 가리켜야 합니다)")
        # 이 계정에 금액이 있는 다른 연도 재무제표 — 소계가 되면 하위 0개로 검증이 깨진다(Q6a)
        other = db.scalars(select(FsStatement.fiscal_year).join(FsAmount, FsAmount.statement_id == FsStatement.id)
                           .where(FsAmount.account_id == t.id, _alive(FsAmount), _alive(FsStatement),
                                  FsStatement.basis == p.basis)).all()
        missing = sorted({y for y in other if y not in p.years})
        if missing and not t.is_subtotal:
            p.errors.append(f"'{t.name}' 은 {missing} 재무제표에도 쓰입니다 — 그 연도도 함께 붙여야 합니다"
                            "(정산표에 그 연도 열이 있어야 합니다)")
        existing = {c.name: c for c in own if c.id in attached}
        for ar in p.rows:
            if ar.target is t and ar.skip_reason is None:
                ar.existing = existing.get(ar.name)


def _raw_meta(ar: AttachRow, column: str, year: int) -> dict:
    r = ar.row
    meta: dict = {"attach": True, "source_path": ar.source_path, "bridge": {"column": column, "value": ar.bridge}}
    if "annotations" in r.meta:
        meta["annotations"] = r.meta["annotations"]
    if "adjustments" in r.meta and str(year) in r.meta["adjustments"]:
        meta["adjustments"] = r.meta["adjustments"][str(year)]
    if year in r.meta.get("float_noise", []):
        meta["float_noise"] = True
    return meta


def apply(db: Session, sheet: ParsedSheet, p: AttachPlan, actor_id: UUID, *, finalize: bool,
          suspense: bool = True) -> dict:
    """공시 계정을 소계로 바꾸고 COA 계정·금액을 넣는다. 충돌(final)은 호출 전에 409 로 막는다."""
    stype = sheet.statement_type
    for t in p.targets():
        svc.set_subtotal(db, t, True)
    acc: dict[str, FsAccount] = {}
    for ar in p.rows:
        if ar.skip_reason is not None or ar.target is None:
            continue
        a = ar.existing or svc.create_account(
            db, statement_type=stype, name=ar.name[:200], section=ar.target.section, parent_id=ar.target.id,
            sort_order=ar.row.row_no, is_subtotal=False, rollup_sign=1)
        acc[str(ar.row.row_no)] = a
    results = []
    latest = max(p.years)
    for y in p.years:
        st = p.statements[y]
        for ar in p.rows:
            a = acc.get(str(ar.row.row_no))
            amt: Decimal | None = ar.row.amounts.get(y)
            if a is None or amt is None:
                continue
            svc.set_amount(db, st, a, amt, raw_row_no=ar.row.row_no, raw_label=ar.row.raw_label[:300],
                           raw_indent=ar.row.indent, raw_value=ar.row.raw_values.get(y),
                           raw_meta=_raw_meta(ar, p.bridge_column, y))
        result = svc.validate(db, st)
        # 소계 불일치 → 임시계정(원본 차이)으로 받는다. 미해결 임시계정은 확정을 막는다(관리자 검토 후 해소)
        absorbed = fs_suspense.absorb(db, st, result, source=f"attach:{sheet.sheet_name}") if suspense else []
        if absorbed:
            result = svc.validate(db, st)
        finalized = False
        if finalize and y == latest and result["ok"]:
            svc.finalize(db, st, actor_id, FINALIZE_REASON)
            finalized = True
        results.append({"fiscal_year": y, "statement": st, "validation": result, "finalized": finalized,
                        "finalize_candidate": y == latest, "suspense": absorbed})
    return {"accounts": acc, "statements": results, "structure_warnings": []}
