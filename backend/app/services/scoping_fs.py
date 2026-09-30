"""재무제표 기반 스코핑 생성 (8-E, ADR-0037 §6, 마스터 확정 A안 2026-09-30).

A안: **2026 스코핑은 그대로 두고, 다음 회계연도부터** 스코핑 계정 행을 템플릿 복사가 아니라 기준 연도의
**확정 재무제표 계정**에서 만든다. 템플릿은 8-C 링크(사람이 확정한 것)로 기본값만 공급한다.

- 기준 연도 = 스코핑 회계연도 − 1(`scopings.base_fiscal_year`). 별도재무제표.
- BS·PL: 기준 연도 **확정(final)** 재무제표 필수(없으면 오류). CF: 확정본이 없으면 템플릿 CF 행으로 대체(경고).
- 계정 행 = 그 재무제표 금액 트리의 **잎**(하위에 금액 행이 없는 계정). 정산표를 결합(8-B2)했으면 COA 계정이다 —
  스코핑 템플릿이 COA 입도이기 때문이다(8-C STEP 0 실측). 그룹 라벨 = 부모 계정(공시 행).
  임시계정(원본 차이) 행은 계정이 아니므로 뺀다.
- 금액 = 재무제표 금액 × 단위 → 원. **정수가 아니면 오류**(조용히 반올림하지 않는다 — ADR-0037 §2.7).
  당기 = 기준 연도 **확정본**, 전기 = 기준 연도 − 1 재무제표(확정본 우선, 없으면 작성 중인 것 — 전기 숫자는 보통
  당기 감사 재무제표의 비교 열에서 들어와 작성 중으로 남는다. 없으면 비움).
- 기본값: 확정된 템플릿 링크가 있는 계정만 템플릿 계정의 질적 평가값·판단 근거·수동 판정을 복사하고 배지를 단다.
  링크 없는 계정은 비워 두고 경고한다(`scoping.evaluate`).
- 주석(NOTE)은 재무제표에 없으므로 템플릿에서 복사한다(기존과 같다).
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial_statement import (
    FS_BASIS_SEPARATE,
    FS_STATUS_FINAL,
    FsAccount,
    FsStatement,
)
from app.models.scoping import (
    ORIGIN_TARGET_ACCOUNT,
    QUAL_FACTORS,
    Scoping,
    ScopingAccount,
    ScopingTemplate,
    ScopingTemplateAccount,
)
from app.services import financial_statement as fs
from app.services import scoping as svc
from app.services.fs_template_match import active_links

REQUIRED = ("BS", "PL")
OPTIONAL = ("CF",)


class ScopingSourceError(ValueError):
    """재무제표 기반 생성 불가 — API 422."""


def _final(db: Session, year: int, stype: str) -> FsStatement | None:
    return db.scalars(select(FsStatement).where(
        FsStatement.fiscal_year == year, FsStatement.statement_type == stype,
        FsStatement.basis == FS_BASIS_SEPARATE, FsStatement.status == FS_STATUS_FINAL,
        FsStatement.is_deleted == False)).first()  # noqa: E712


def _prior(db: Session, year: int, stype: str) -> FsStatement | None:
    """전기 재무제표 — 확정본 우선, 없으면 작성 중인 것."""
    return _final(db, year, stype) or db.scalars(select(FsStatement).where(
        FsStatement.fiscal_year == year, FsStatement.statement_type == stype,
        FsStatement.basis == FS_BASIS_SEPARATE, FsStatement.is_deleted == False)).first()  # noqa: E712


def _won(amount: Decimal | None, unit: int, label: str) -> int | None:
    if amount is None:
        return None
    v = amount * unit
    if v != v.to_integral_value():
        raise ScopingSourceError(f"'{label}' 금액 {amount} × 단위 {unit} 이 정수 원이 아닙니다")
    return int(v)


def leaf_rows(db: Session, st: FsStatement) -> list[tuple[FsAccount, Decimal | None, FsAccount | None]]:
    """(계정, 금액, 부모 계정) — 트리 순서, 금액 트리의 잎만, 임시계정 제외."""
    rows = fs.statement_rows(db, st)
    amount_of = {a.id: r.amount for r, a in rows if not fs.is_suspense(r)}
    suspense = {a.id for r, a in rows if fs.is_suspense(r)}
    tree = fs.account_tree_rows(db, st.statement_type, st.fiscal_year)
    by_id = {a.id: a for a, _ in tree}
    has_child_row = {a.parent_id for a, _ in tree if a.id in amount_of and a.parent_id}
    ordered: list[FsAccount] = []

    def walk(nodes):
        for n in nodes:
            ordered.append(by_id[n["id"]])
            walk(n["children"])
    walk(fs.build_tree(tree, lambda a, d: {"id": a.id}))
    return [(a, amount_of[a.id], by_id.get(a.parent_id)) for a in ordered
            if a.id in amount_of and a.id not in has_child_row and a.id not in suspense]


def fill_from_financial_statements(db: Session, s: Scoping, template: ScopingTemplate) -> dict:
    """스코핑 계정 행을 재무제표에서 만든다. 요약을 돌려준다."""
    base = s.fiscal_year - 1
    finals = {t: _final(db, base, t) for t in REQUIRED + OPTIONAL}
    missing = [t for t in REQUIRED if finals[t] is None]
    if missing:
        raise ScopingSourceError(
            f"기준 연도({base}) 별도재무제표 {', '.join(missing)} 가 확정되지 않았습니다 — 재무제표 화면에서 올리고 확정하세요")
    links = {lk.account_id: lk.template_account_id for lk in active_links(db, template)}
    tmpl = {t.id: t for t in db.scalars(select(ScopingTemplateAccount).where(
        ScopingTemplateAccount.template_id == template.id, ScopingTemplateAccount.is_deleted == False)).all()}  # noqa: E712
    v = template.version
    summary = {"rows": 0, "linked": 0, "template_fallback": []}

    for stype in REQUIRED + OPTIONAL:
        st = finals[stype]
        if st is None:
            continue
        prior = _prior(db, base - 1, stype)
        prior_amount = {a.id: r.amount for r, a in fs.statement_rows(db, prior)} if prior else {}
        for i, (acc, amt, parent) in enumerate(leaf_rows(db, st), start=1):
            t = tmpl.get(links.get(acc.id))
            row = ScopingAccount(
                scoping_id=s.id, fs_account_id=acc.id, statement_type=stype, sort_order=i,
                group_label=parent.name if parent else None, name=acc.name,
                current_amount=_won(amt, st.unit, acc.name),
                prior_amount=_won(prior_amount.get(acc.id), prior.unit, acc.name) if prior else None,
                ratings=dict(t.ratings or {}) if t else {}, qual_basis=t.qual_basis if t else None,
                manual_conclusion=t.manual_conclusion if t else None, manual_reason=t.manual_reason if t else None)
            db.add(row)
            db.flush()
            summary["rows"] += 1
            if t is None:
                continue
            summary["linked"] += 1
            for f in QUAL_FACTORS:
                if (t.ratings or {}).get(f):
                    svc._origin(db, s, ORIGIN_TARGET_ACCOUNT, row.id, f"ratings.{f}", v)
            if t.qual_basis:
                svc._origin(db, s, ORIGIN_TARGET_ACCOUNT, row.id, "qual_basis", v)
            if t.manual_conclusion:
                svc._origin(db, s, ORIGIN_TARGET_ACCOUNT, row.id, "manual", v)

    fallback = {"NOTE"} | {t for t in OPTIONAL if finals[t] is None}
    svc.copy_template_accounts(db, s, template, statement_types=fallback)
    summary["template_fallback"] = sorted(fallback)
    return summary


def create(db: Session, fiscal_year: int, template: ScopingTemplate) -> tuple[Scoping, dict]:
    holder: dict = {}

    def fill(db_: Session, s: Scoping) -> None:
        holder.update(fill_from_financial_statements(db_, s, template))
    s = svc.create_from_template(db, fiscal_year, template, fill_accounts=fill)
    return s, holder
