"""재무제표 업로드 preview / commit (8-B, ADR-0037 §3).

**preview 는 저장하지 않는다.** 단 commit 과 같은 코드 경로로 DB 에 넣어 본 뒤 **롤백**한다 —
preview 의 검증 결과가 commit 후 8-A `validate()` 결과와 같은 함수에서 나오게 하기 위해서다
(별도 계산을 두면 둘이 어긋날 수 있다).

마스터 확정 (STEP 0 Q1~Q8, 2026-09-29 "권장안대로"):
- Q3 해당 종류 계정 마스터가 **비어 있으면 전부 신규**. 비어 있지 않으면 `mapping`(행→account_id|new)이
  **모든 계정 행에 명시돼야** commit(없으면 409 + `suggested_mapping`). 자동 매칭은 제안일 뿐이다.
- Q4 **최신 연도만, 검증 통과 시 final**(`finalize=false`로 끔). 실패하면 draft 로 남기고 결과를 돌려준다.
- Q5 공시양식형은 **당기만** 저장, `include_prior=true`면 전기도(draft). 가로 연도형은 전 연도.
- Q6 같은 (연도·종류·연결별도) 재무제표가 있으면 **409, 덮어쓰지 않는다.**
- Q8 원본 소계 불일치는 draft 저장 허용 — 확정만 8-A 관문이 막는다.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial_statement import (
    FS_BASES,
    FS_BASIS_CONSOLIDATED,
    FS_BASIS_SEPARATE,
    FS_UNITS,
    FsAccount,
    FsStatement,
)
from app.services import financial_statement as svc
from app.services import fs_approval, fs_suspense
from app.services.fs_upload.cells import norm
from app.services.fs_upload.parsed import KIND_DISCLOSURE, KIND_HORIZONTAL, ParsedRow, ParsedSheet
from app.services.fs_upload.structure import subtotal_diffs

NEW = "new"


@dataclass
class UploadOptions:
    basis: str | None = None
    unit: int | None = None
    fiscal_years: list[int] | None = None
    include_prior: bool = False
    tolerance: Decimal = Decimal(0)
    finalize: bool = True
    mapping: dict[str, str] | None = None
    filename: str | None = None
    suspense: bool = True       # 소계 불일치를 임시계정으로 받는다(마스터 지시 2026-09-30)


@dataclass
class Plan:
    """업로드 판정 — preview·commit 공통."""
    basis: str | None = None
    unit: int | None = None
    years: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)        # 422
    warnings: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)    # 409
    master_empty: bool = True
    suggested: dict[str, str] = field(default_factory=dict)
    mapping: dict[str, str] = field(default_factory=dict)  # 실제로 쓸 대응(명시 또는 제안)
    mapping_required: bool = False                          # 409

    @property
    def blocked(self) -> bool:
        return bool(self.errors)


def _key(r: ParsedRow) -> str:
    return str(r.row_no)


def _path(r: ParsedRow) -> tuple[str, ...]:
    out = []
    cur: ParsedRow | None = r
    while cur is not None:
        out.append(norm(cur.label))
        cur = cur.parent
    return tuple(reversed(out))


def _account_paths(accounts: list[FsAccount]) -> dict[tuple[str, ...], list[FsAccount]]:
    by_id = {a.id: a for a in accounts}
    out: dict[tuple[str, ...], list[FsAccount]] = {}
    for a in accounts:
        parts, cur, seen = [], a, set()
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            parts.append(norm(cur.name))
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        out.setdefault(tuple(reversed(parts)), []).append(a)
    return out


def _alive_accounts(db: Session, statement_type: str) -> list[FsAccount]:
    return list(db.scalars(select(FsAccount).where(FsAccount.statement_type == statement_type,
                                                   FsAccount.is_deleted == False)).all())  # noqa: E712


def plan(db: Session, sheet: ParsedSheet, opts: UploadOptions) -> Plan:
    p = Plan(errors=list(sheet.errors), warnings=list(sheet.warnings))
    if sheet.errors:
        return p

    # 연결·별도 — 제목의 "연결"과 지정값이 어긋나면 막는다
    hint = FS_BASIS_CONSOLIDATED if sheet.consolidated_hint else None
    if opts.basis is not None and opts.basis not in FS_BASES:
        p.errors.append(f"연결·별도 구분이 올바르지 않습니다: {opts.basis}")
    elif opts.basis is not None and hint is not None and opts.basis != hint:
        p.errors.append("시트 제목은 연결재무제표인데 별도로 지정했습니다")
    p.basis = opts.basis or hint or FS_BASIS_SEPARATE

    # 단위 — 감지 못 하면 지정 필수, 추정하지 않는다
    if sheet.unit_word is not None and sheet.unit is None:
        p.errors.append(f"지원하지 않는 단위입니다: {sheet.unit_word} (원·천원·백만원만)")
    elif opts.unit is not None and opts.unit not in FS_UNITS:
        p.errors.append(f"단위가 올바르지 않습니다: {opts.unit}")
    elif opts.unit is not None and sheet.unit is not None and opts.unit != sheet.unit:
        p.errors.append(f"지정한 단위({opts.unit})가 시트 표기({sheet.unit_word})와 다릅니다")
    elif opts.unit is None and sheet.unit is None:
        p.errors.append("시트에서 단위 표기를 찾지 못했습니다 — unit(1·1000·1000000)을 지정하세요")
    p.unit = opts.unit if opts.unit is not None else sheet.unit

    if opts.tolerance < 0:
        p.errors.append("허용 오차는 0 이상이어야 합니다")

    # 연도
    if opts.fiscal_years:
        bad = [y for y in opts.fiscal_years if y not in sheet.periods]
        if bad:
            p.errors.append(f"시트에 없는 회계연도입니다: {bad} (있는 연도 {sheet.periods})")
        p.years = sorted({y for y in opts.fiscal_years if y in sheet.periods}, reverse=True)
    elif sheet.kind == KIND_DISCLOSURE:
        p.years = sheet.periods[:2] if opts.include_prior else sheet.periods[:1]
    else:
        p.years = list(sheet.periods)

    # 금액 오류가 있는 행
    bad_rows = [r for r in sheet.account_rows() if r.errors]
    for r in bad_rows[:20]:
        p.errors.append(f"{r.row_no}행 '{r.label}': {'; '.join(r.errors)}")
    if len(bad_rows) > 20:
        p.errors.append(f"… 금액 오류 행 {len(bad_rows) - 20}건 더")

    # 기존 재무제표 (Q6)
    if p.basis in FS_BASES:
        for y in p.years:
            st = db.scalars(select(FsStatement).where(
                FsStatement.fiscal_year == y, FsStatement.statement_type == sheet.statement_type,
                FsStatement.basis == p.basis, FsStatement.is_deleted == False)).first()  # noqa: E712
            if st is not None:
                p.conflicts.append({"fiscal_year": y, "statement_id": st.id, "status": st.status})

    # 계정 대응 (Q3)
    existing = _alive_accounts(db, sheet.statement_type)
    p.master_empty = not existing
    rows = sheet.account_rows()
    if p.master_empty:
        p.suggested = {_key(r): NEW for r in rows}
    else:
        paths = _account_paths(existing)
        for r in rows:
            # 정산표(가로 연도형) 단독 업로드는 소계 여부가 같은 계정만 제안한다 — 결합(8-B2)으로 소계가 된 공시 행에
            # 정산표 잎을 대응시키면 하위 0개 소계가 된다(2026-09-30 로컬 화면 검증 중 발견).
            # **공시양식은 제외** — 다음 연도 공시를 올릴 때는 결합으로 소계가 된 기존 공시 행을 그대로 써야 한다
            # (그 뒤 같은 연도 정산표를 결합한다). 필터하면 중복 계정이 생긴다.
            cands = paths.get(_path(r), [])
            if sheet.kind == KIND_HORIZONTAL:
                cands = [a for a in cands if a.is_subtotal == r.is_subtotal]
            p.suggested[_key(r)] = str(cands[0].id) if len(cands) == 1 else NEW
    if opts.mapping is None:
        p.mapping = dict(p.suggested)
        p.mapping_required = not p.master_empty
    else:
        p.mapping = {k: str(v) for k, v in opts.mapping.items()}
        missing = [k for k in (_key(r) for r in rows) if k not in p.mapping]
        extra = [k for k in p.mapping if k not in {_key(r) for r in rows}]
        if missing:
            p.errors.append(f"mapping 에 없는 행이 있습니다: {', '.join(missing[:20])}")
        if extra:
            p.errors.append(f"mapping 에 계정 행이 아닌 행 번호가 있습니다: {', '.join(extra[:20])}")
        ids = {str(a.id): a for a in existing}
        used: dict[str, str] = {}
        for k, v in p.mapping.items():
            if v == NEW:
                continue
            if v not in ids:
                p.errors.append(f"{k}행 mapping 의 계정을 찾을 수 없습니다(같은 종류의 계정이어야 합니다): {v}")
            elif v in used:
                p.errors.append(f"{used[v]}행과 {k}행이 같은 계정에 대응됩니다")
            else:
                used[v] = k
    return p


# ── 적용 (commit·preview 공통) ─────────────────────────────────────

def _raw_meta(r: ParsedRow, year: int) -> dict | None:
    meta: dict = {}
    for k in ("notes", "annotations"):
        if k in r.meta:
            meta[k] = r.meta[k]
    if "col" in r.meta and str(year) in r.meta["col"]:
        meta["col"] = r.meta["col"][str(year)]
    if "adjustments" in r.meta and str(year) in r.meta["adjustments"]:
        meta["adjustments"] = r.meta["adjustments"][str(year)]
    if year in r.meta.get("float_noise", []):
        meta["float_noise"] = True
    if r.flags:
        meta["flags"] = list(r.flags)
    meta["row_kind"] = r.kind
    return meta


def apply(db: Session, sheet: ParsedSheet, p: Plan, opts: UploadOptions, actor_id: UUID,
          *, finalize: bool) -> dict:
    """계정·재무제표·금액을 쓴다. 충돌 연도는 건너뛴다(commit 은 호출 전에 409 로 막는다).

    반환: {"accounts": {row_key: FsAccount}, "statements": [결과], "structure_warnings": [...]}
    """
    stype = sheet.statement_type
    existing = {str(a.id): a for a in _alive_accounts(db, stype)}
    acc: dict[str, FsAccount] = {}
    warns: list[str] = []

    def walk(r: ParsedRow, parent_acc: FsAccount | None) -> None:
        target = p.mapping.get(_key(r), NEW)
        if target == NEW:
            a = svc.create_account(db, statement_type=stype, name=r.label[:200], section=r.section,
                                   parent_id=parent_acc.id if parent_acc else None, sort_order=r.row_no,
                                   is_subtotal=r.is_subtotal, rollup_sign=r.sign)
        else:
            a = existing[target]
            want_parent = parent_acc.id if parent_acc else None
            if a.parent_id != want_parent or a.rollup_sign != r.sign or a.is_subtotal != r.is_subtotal:
                warns.append(f"{r.row_no}행 '{r.label}': 기존 계정 구조(부모·부호·소계)와 파일 구조가 다릅니다 "
                             "— 기존 계정 구조를 그대로 둡니다")
        acc[_key(r)] = a
        for c in r.children:
            if not c.excluded:
                walk(c, a)

    for root in sheet.roots:
        if not root.excluded:
            walk(root, None)

    conflict_years = {c["fiscal_year"] for c in p.conflicts}
    results = []
    latest = max((y for y in p.years if y not in conflict_years), default=None)
    for y in p.years:
        if y in conflict_years:
            continue
        st = svc.create_statement(db, fiscal_year=y, statement_type=stype, basis=p.basis, unit=p.unit,
                                  tolerance=opts.tolerance, source_kind=sheet.kind,
                                  source_filename=(opts.filename or None) and opts.filename[:300],
                                  source_sheet=sheet.sheet_name[:200])
        for r in sheet.account_rows():
            amt = r.amounts.get(y)
            if amt is None:
                continue
            svc.set_amount(db, st, acc[_key(r)], amt, raw_row_no=r.row_no, raw_label=r.raw_label[:300],
                           raw_indent=r.indent, raw_value=r.raw_values.get(y), raw_meta=_raw_meta(r, y))
        result = svc.validate(db, st)
        # 소계 불일치 → 임시계정(원본 차이)으로 받는다. 미해결 임시계정은 확정을 막는다(관리자 검토 후 해소)
        absorbed = fs_suspense.absorb(db, st, result, source=f"upload:{sheet.sheet_name}") if opts.suspense else []
        if absorbed:
            result = svc.validate(db, st)
        # "확정" 옵션 = 검토 요청(ADR-0038 2-2) — 업로드가 결재 없이 확정하는 경로는 없다
        submitted = False
        if finalize and y == latest and result["ok"]:
            db.flush()
            submitted = fs_approval.submit_after_upload(db, st, actor_id)
        results.append({"fiscal_year": y, "statement": st, "validation": result, "review_requested": submitted,
                        "finalize_candidate": y == latest, "suspense": absorbed})
    return {"accounts": acc, "statements": results, "structure_warnings": warns}


def diffs(sheet: ParsedSheet) -> list[dict]:
    return subtotal_diffs(sheet) if not sheet.errors else []
