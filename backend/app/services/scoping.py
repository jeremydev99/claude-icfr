"""스코핑 해석 — 템플릿 복사·필드 단위 배지·평가 산출·확정 스냅샷 (ADR-0034, 6-1).

화면·대시보드·확정 스냅샷이 **같은 평가**를 봐야 해서 한 곳에 둔다. 계산식 자체는
`services/scoping_calc.py`(순수 함수), 여기는 DB 에서 재료를 모아 그 함수에 넣는다.

**배지 규칙**(ADR-0034 §2.7)
- 템플릿에서 복사한 필드마다 `ScopingFieldOrigin(status=template)` 1행
- 사용자가 **값을 바꿔** 저장하면 `edited` 로 바뀐다 — 필드 단위다. 한 계정의 한 요소를
  고치면 그 요소만 떨어진다
- **같은 값 재저장은 수정이 아니다** — `set_field` 가 이전 값과 비교해 같으면 아무것도 안 한다
"""
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.role_assignment import TenantPolicy
from app.models.scoping import (
    BENCHMARK_ADJUSTED_PBT,
    BENCHMARK_GUIDE_RANGES,
    BENCHMARK_LABELS,
    BENCHMARKS,
    DEFAULT_QUAL_COMPARISON,
    DEFAULT_QUAL_THRESHOLD,
    ORIGIN_EDITED,
    ORIGIN_TARGET_ACCOUNT,
    ORIGIN_TARGET_BENCHMARK,
    ORIGIN_TARGET_SCOPING,
    ORIGIN_TARGET_TEXT,
    ORIGIN_TEMPLATE,
    POLICY_SCOPING_QUAL_COMPARISON,
    POLICY_SCOPING_QUAL_THRESHOLD,
    QUAL_COMPARISONS,
    QUAL_FACTORS,
    SMT_RATE_GUIDE_RANGE,
    STATEMENT_TYPES,
    Scoping,
    ScopingAccount,
    ScopingAdjustment,
    ScopingBenchmark,
    ScopingFieldOrigin,
    ScopingTemplate,
    ScopingTemplateAccount,
    ScopingTemplateText,
    ScopingText,
)
from app.services import scoping_calc as calc

# 필드 이름 규약 — 계정의 질적 요소는 "ratings.q1" 처럼 점으로 푼다(필드 단위 배지)
ACCOUNT_TEMPLATE_FIELDS = tuple(f"ratings.{f}" for f in QUAL_FACTORS) + ("qual_basis", "manual")


def _active(q, model):
    return q.filter(model.is_deleted == False)  # noqa: E712


# ── 정책 ───────────────────────────────────────────────────

def qual_policy(db: Session) -> tuple[Decimal, str]:
    """질적 판정 기준값·비교 방식. 없거나 해석 불가면 기본값(2, 이상).

    값 검증은 저장 시 한다(`api/role_assignment._assert_policy_value_valid`). 여기서 다시 거르는
    것은 검증 이전 값이 남아 있어도 판정이 터지지 않게 하려는 것이다.
    """
    rows = {
        p.policy_key: p.policy_value
        for p in _active(db.query(TenantPolicy), TenantPolicy).filter(
            TenantPolicy.policy_key.in_((POLICY_SCOPING_QUAL_THRESHOLD, POLICY_SCOPING_QUAL_COMPARISON)))
    }
    try:
        threshold = Decimal(rows.get(POLICY_SCOPING_QUAL_THRESHOLD, DEFAULT_QUAL_THRESHOLD))
    except ArithmeticError:
        threshold = Decimal(DEFAULT_QUAL_THRESHOLD)
    comparison = rows.get(POLICY_SCOPING_QUAL_COMPARISON, DEFAULT_QUAL_COMPARISON)
    if comparison not in QUAL_COMPARISONS:
        comparison = DEFAULT_QUAL_COMPARISON
    return threshold, comparison


# ── 템플릿 복사 ────────────────────────────────────────────

def _origin(db: Session, scoping: Scoping, target_type: str, target_id: UUID, field: str,
            version: int | None) -> None:
    db.add(ScopingFieldOrigin(scoping_id=scoping.id, target_type=target_type, target_id=target_id,
                              field=field, status=ORIGIN_TEMPLATE, template_version=version))


def create_from_template(db: Session, fiscal_year: int, template: ScopingTemplate) -> Scoping:
    """회계연도 스코핑을 만들고 템플릿 내용을 **복사**한다. 복사된 필드마다 배지를 단다.

    **금액은 복사하지 않는다** — 템플릿에 금액이 없다(2022 금액은 적재 단계에서 제외).
    """
    v = template.version
    s = Scoping(fiscal_year=fiscal_year, template_code=template.code, template_version=v,
                selected_benchmark=template.default_benchmark,
                smt_rate=Decimal(template.default_smt_rate))
    texts = _active(db.query(ScopingTemplateText), ScopingTemplateText).filter(
        ScopingTemplateText.template_id == template.id).order_by(ScopingTemplateText.sort_order).all()
    rationale = next((t.body for t in texts if t.key == "materiality.rationale"), None)
    s.rationale = rationale
    db.add(s)
    db.flush()

    _origin(db, s, ORIGIN_TARGET_SCOPING, s.id, "selected_benchmark", v)
    _origin(db, s, ORIGIN_TARGET_SCOPING, s.id, "smt_rate", v)
    if rationale:
        _origin(db, s, ORIGIN_TARGET_SCOPING, s.id, "rationale", v)

    for kind in BENCHMARKS:
        rate = template.default_rates.get(kind)
        b = ScopingBenchmark(scoping_id=s.id, kind=kind, rate=Decimal(rate) if rate else None)
        db.add(b)
        db.flush()
        if rate:
            _origin(db, s, ORIGIN_TARGET_BENCHMARK, b.id, "rate", v)

    for t in texts:
        if t.key == "materiality.rationale":
            continue   # 설정근거는 스코핑 필드(rationale)로 옮겼다 — 두 곳에 두지 않는다
        row = ScopingText(scoping_id=s.id, key=t.key, title=t.title, body=t.body, sort_order=t.sort_order)
        db.add(row)
        db.flush()
        _origin(db, s, ORIGIN_TARGET_TEXT, row.id, "body", v)

    for a in _active(db.query(ScopingTemplateAccount), ScopingTemplateAccount).filter(
            ScopingTemplateAccount.template_id == template.id).order_by(
            ScopingTemplateAccount.statement_type, ScopingTemplateAccount.sort_order):
        row = ScopingAccount(scoping_id=s.id, statement_type=a.statement_type, sort_order=a.sort_order,
                             group_label=a.group_label, name=a.name, ratings=dict(a.ratings or {}),
                             qual_basis=a.qual_basis, manual_conclusion=a.manual_conclusion,
                             manual_reason=a.manual_reason)
        db.add(row)
        db.flush()
        for f in QUAL_FACTORS:
            if (a.ratings or {}).get(f):
                _origin(db, s, ORIGIN_TARGET_ACCOUNT, row.id, f"ratings.{f}", v)
        if a.qual_basis:
            _origin(db, s, ORIGIN_TARGET_ACCOUNT, row.id, "qual_basis", v)
        if a.manual_conclusion:
            _origin(db, s, ORIGIN_TARGET_ACCOUNT, row.id, "manual", v)
    db.flush()
    return s


# ── 배지 ───────────────────────────────────────────────────

def origins_by_target(db: Session, scoping_id: UUID) -> dict[tuple[str, UUID], dict[str, str]]:
    """(대상 종류, 대상 id) → {필드: 상태}."""
    out: dict[tuple[str, UUID], dict[str, str]] = {}
    for o in _active(db.query(ScopingFieldOrigin), ScopingFieldOrigin).filter(
            ScopingFieldOrigin.scoping_id == scoping_id):
        out.setdefault((o.target_type, o.target_id), {})[o.field] = o.status
    return out


def badge_count(db: Session, scoping_id: UUID) -> int:
    """아직 템플릿 그대로인 필드 수 — 확정 경고에 쓴다."""
    return _active(db.query(ScopingFieldOrigin), ScopingFieldOrigin).filter(
        ScopingFieldOrigin.scoping_id == scoping_id,
        ScopingFieldOrigin.status == ORIGIN_TEMPLATE,
    ).count()


def mark_edited(db: Session, scoping_id: UUID, target_type: str, target_id: UUID, field: str) -> None:
    """그 필드의 배지를 뗀다. 출처 행이 없으면(처음부터 사용자 입력) 아무것도 안 한다.

    출처 행은 **대상이 다형이라 FK 가 없다**. 대상은 호출하는 핸들러가 이미 찾아서 검증했고,
    같은 트랜잭션 안에서만 부른다(`models/scoping.ScopingFieldOrigin`).
    """
    o = _active(db.query(ScopingFieldOrigin), ScopingFieldOrigin).filter(
        ScopingFieldOrigin.scoping_id == scoping_id,
        ScopingFieldOrigin.target_type == target_type,
        ScopingFieldOrigin.target_id == target_id,
        ScopingFieldOrigin.field == field,
    ).first()
    if o is not None and o.status == ORIGIN_TEMPLATE:
        o.status = ORIGIN_EDITED


def _norm(v):
    """비교용 정규화 — 앞뒤 공백·Decimal 자릿수 차이로 '바뀌었다'고 판정하지 않게 한다."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if isinstance(v, Decimal):
        return v.normalize()
    return v


def changed(old, new) -> bool:
    """**같은 값 재저장은 수정이 아니다**(ADR-0034 §2.7). 배지 판정은 이 함수만 쓴다."""
    return _norm(old) != _norm(new)


# ── 평가 ───────────────────────────────────────────────────

def _rate_str(v: Decimal | None) -> str | None:
    return None if v is None else format(Decimal(v).normalize(), "f")


def evaluate(db: Session, s: Scoping) -> dict:
    """스코핑 1건의 산출 결과 — 양적 중요성·계정별 판정·경고. **저장하지 않는다.**"""
    threshold, comparison = qual_policy(db)
    benches = {b.kind: b for b in _active(db.query(ScopingBenchmark), ScopingBenchmark).filter(
        ScopingBenchmark.scoping_id == s.id)}
    adjustments = _active(db.query(ScopingAdjustment), ScopingAdjustment).filter(
        ScopingAdjustment.scoping_id == s.id).order_by(ScopingAdjustment.created_at).all()
    adj_sum = [a.amount for a in adjustments]

    bench_rows = []
    for kind in BENCHMARKS:
        b = benches.get(kind)
        base = b.base_amount if b else None
        effective = calc.adjusted_base(base, adj_sum) if kind == BENCHMARK_ADJUSTED_PBT else base
        rate = b.rate if b else None
        bench_rows.append({
            "kind": kind, "label": BENCHMARK_LABELS[kind], "id": b.id if b else None,
            "base_amount": base, "effective_base": effective, "rate": _rate_str(rate),
            "amount": calc.benchmark_amount(effective, rate),
            "guide_range": BENCHMARK_GUIDE_RANGES.get(kind),
            "out_of_range": calc.out_of_range(rate, BENCHMARK_GUIDE_RANGES.get(kind)),
        })
    selected = next((r for r in bench_rows if r["kind"] == s.selected_benchmark), None)
    overall = calc.overall_materiality(selected["amount"]) if selected else None
    smt = calc.performance_materiality(overall, s.smt_rate)

    accounts = _active(db.query(ScopingAccount), ScopingAccount).filter(
        ScopingAccount.scoping_id == s.id).all()
    order = {t: i for i, t in enumerate(STATEMENT_TYPES)}
    accounts.sort(key=lambda a: (order.get(a.statement_type, 99), a.sort_order))
    acc_rows = []
    for a in accounts:
        quant = calc.quantitative(a.statement_type, a.current_amount, smt)
        avg = calc.qualitative_average(a.ratings)
        qual = calc.qualitative(a.ratings, threshold, comparison)
        computed = calc.conclusion(quant, qual)
        acc_rows.append({
            "account": a, "quant": quant, "qual_average": None if avg is None else str(avg),
            "qual": qual, "computed": computed, "final": calc.final_conclusion(computed, a.manual_conclusion),
        })

    warnings = []
    for r in bench_rows:
        if r["out_of_range"]:
            warnings.append(f"{r['label']} 비율 {r['rate']} 이 가이드 범위를 벗어났습니다")
    if calc.out_of_range(s.smt_rate, SMT_RATE_GUIDE_RANGE):
        warnings.append(f"수행중요성 설정율 {_rate_str(s.smt_rate)} 이 가이드 범위(50~75%)를 벗어났습니다")
    if not (s.rationale or "").strip():
        warnings.append("중요성 설정근거가 비어 있습니다 — 검토 요청·확정 전에 입력해야 합니다")

    return {
        "policy": {"threshold": str(threshold), "comparison": comparison},
        "benchmarks": bench_rows, "adjustments": adjustments,
        "selected_benchmark": s.selected_benchmark, "overall_materiality": overall,
        "smt": smt, "smt_rate": _rate_str(s.smt_rate),
        "smt_out_of_range": calc.out_of_range(s.smt_rate, SMT_RATE_GUIDE_RANGE),
        "accounts": acc_rows, "warnings": warnings,
    }


def snapshot(db: Session, s: Scoping) -> dict:
    """확정 스냅샷 — **그때의 정책과 결론을 값으로 굳힌다.** 이후 정책이 바뀌어도 이것은 그대로다."""
    ev = evaluate(db, s)
    return {
        "taken_at": datetime.now(UTC).isoformat(),
        "policy": ev["policy"],
        "selected_benchmark": ev["selected_benchmark"],
        "overall_materiality": ev["overall_materiality"],
        "smt": ev["smt"], "smt_rate": ev["smt_rate"],
        "accounts": {
            str(r["account"].id): {
                "name": r["account"].name, "statement_type": r["account"].statement_type,
                "quant": r["quant"], "qual": r["qual"], "computed": r["computed"],
                "manual": r["account"].manual_conclusion, "final": r["final"],
            }
            for r in ev["accounts"]
        },
    }
