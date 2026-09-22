"""스코핑 해석 — 템플릿 복사·필드 단위 배지·평가 산출·확정 스냅샷 (ADR-0034, 6-1).

화면·대시보드·확정 스냅샷이 **같은 평가**를 봐야 해서 한 곳에 둔다. 계산식 자체는
`services/scoping_calc.py`(순수 함수), 여기는 DB 에서 재료를 모아 그 함수에 넣는다.

**배지 규칙**(ADR-0034 §2.7)
- 템플릿에서 복사한 필드마다 `ScopingFieldOrigin(status=template)` 1행
- 사용자가 **값을 바꿔** 저장하면 `edited` 로 바뀐다 — 필드 단위다. 한 계정의 한 요소를
  고치면 그 요소만 떨어진다
- **같은 값 재저장은 수정이 아니다** — `changed` 가 이전 값과 비교해 같으면 아무것도 안 한다
- **검토 확인**(6-1b) — 템플릿 값에 동의하면 `confirmed`. 확정 경고는 `template` 만 센다
- `confirmed` 를 고치면 `edited` 가 된다. 확인 취소는 `confirmed → template`

**중요성 기준은 스코핑에 있다**(6-1b §3.2) — 비율 가이드 범위·설정율 범위·질적 기준값·비교 방식·
기준 연도. 테넌트 정책(`qual_policy`)은 새 연도를 만들 때 기본값으로만 쓴다.
"""
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.role_assignment import TenantPolicy
from app.models.scoping import (
    BENCHMARK_ADJUSTED_PBT,
    BENCHMARK_GUIDE_RANGES,
    BENCHMARK_LABELS,
    BENCHMARKS,
    CONFIRM_SCOPE_ACCOUNT,
    CONFIRM_SCOPE_MATERIALITY,
    CONFIRM_SCOPE_TEXT,
    DEFAULT_QUAL_COMPARISON,
    DEFAULT_QUAL_THRESHOLD,
    ORIGIN_CONFIRMED,
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


# ── 중요성 기준 (6-1b) ─────────────────────────────────────

def _dec(v) -> Decimal | None:
    return None if v is None or v == "" else Decimal(str(v))


def template_criteria(template: ScopingTemplate | None) -> dict:
    """템플릿의 중요성 기준 기본값. 옛 템플릿 행(default_criteria 없음)은 모델 상수로 대신한다."""
    c = (template.default_criteria if template is not None else None) or {}
    guides = c.get("benchmark_guides")
    if guides is None:
        guides = default_criteria_payload()["benchmark_guides"]
    smt = c.get("smt_guide") or list(SMT_RATE_GUIDE_RANGE)
    return {"benchmark_guides": guides, "smt_guide": smt}


def default_criteria_payload() -> dict:
    """템플릿 적재가 `default_criteria` 에 넣는 값 — 원천 Note 1·2. 매출액은 비워 둔다."""
    return {"benchmark_guides": {k: (list(v) if v else None) for k, v in BENCHMARK_GUIDE_RANGES.items()},
            "smt_guide": list(SMT_RATE_GUIDE_RANGE)}


def _range(low, high) -> tuple[str | None, str | None] | None:
    """(하한, 상한) 문자열. 둘 다 없으면 None — **범위가 없으면 경고하지 않는다.**"""
    if low is None and high is None:
        return None
    return (_rate_str(low), _rate_str(high))


def criteria(db: Session, s: Scoping) -> dict:
    """이 스코핑의 판정 기준. 값이 없으면(6-1b 이전에 확정된 스코핑) 기본값으로 대신한다 —
    그 경우 확정 판단은 스냅샷이 보존하므로 이것은 화면 표시용이다."""
    if s.qual_threshold is not None and s.qual_comparison in QUAL_COMPARISONS:
        threshold, comparison = Decimal(s.qual_threshold), s.qual_comparison
    else:
        threshold, comparison = qual_policy(db)
    return {
        "base_fiscal_year": s.base_fiscal_year if s.base_fiscal_year is not None else s.fiscal_year - 1,
        "qual_threshold": threshold, "qual_comparison": comparison,
        "smt_guide": _range(s.smt_guide_low, s.smt_guide_high),
    }


def change_rate(current: int | None, prior: int | None) -> str | None:
    """증감률 (기준 − 전년) / |전년|, 소수 4자리. 전년이 없거나 0 이면 산출하지 않는다.

    **양적 판정에는 쓰지 않는다** — 질적 6번 요소(금액 변화 정도)의 판단 근거로 보여 줄 뿐이다.
    """
    if current is None or prior is None or prior == 0:
        return None
    r = (Decimal(current) - Decimal(prior)) / abs(Decimal(prior))
    return str(r.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


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
    crit = template_criteria(template)
    threshold, comparison = qual_policy(db)   # 테넌트 정책 = 새 연도의 기본값(없으면 2 이상)
    smt_guide = crit["smt_guide"]
    s = Scoping(fiscal_year=fiscal_year, template_code=template.code, template_version=v,
                selected_benchmark=template.default_benchmark,
                smt_rate=Decimal(template.default_smt_rate),
                base_fiscal_year=fiscal_year - 1,
                smt_guide_low=_dec(smt_guide[0]), smt_guide_high=_dec(smt_guide[1]),
                qual_threshold=threshold, qual_comparison=comparison)
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
    # 기준도 기본값에서 왔으므로 배지를 단다 — 감사인 검토 전에는 "아직 아무도 보지 않은 기준"이다.
    # 기준 연도는 템플릿이 아니라 회계연도에서 나오므로 배지 대상이 아니다
    if s.smt_guide_low is not None or s.smt_guide_high is not None:
        _origin(db, s, ORIGIN_TARGET_SCOPING, s.id, "smt_guide", v)
    _origin(db, s, ORIGIN_TARGET_SCOPING, s.id, "qual_threshold", v)
    _origin(db, s, ORIGIN_TARGET_SCOPING, s.id, "qual_comparison", v)

    for kind in BENCHMARKS:
        rate = template.default_rates.get(kind)
        guide = crit["benchmark_guides"].get(kind)
        b = ScopingBenchmark(scoping_id=s.id, kind=kind, rate=Decimal(rate) if rate else None,
                             guide_low=_dec(guide[0]) if guide else None,
                             guide_high=_dec(guide[1]) if guide else None)
        db.add(b)
        db.flush()
        if rate:
            _origin(db, s, ORIGIN_TARGET_BENCHMARK, b.id, "rate", v)
        if guide:   # 매출액처럼 기본값이 비어 있으면 복사한 것이 없다 — 배지 없음
            _origin(db, s, ORIGIN_TARGET_BENCHMARK, b.id, "guide", v)

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

def _origins(db: Session, scoping_id: UUID):
    return _active(db.query(ScopingFieldOrigin), ScopingFieldOrigin).filter(
        ScopingFieldOrigin.scoping_id == scoping_id)


def origins_by_target(db: Session, scoping_id: UUID) -> dict[tuple[str, UUID], dict[str, str]]:
    """(대상 종류, 대상 id) → {필드: 상태}."""
    out: dict[tuple[str, UUID], dict[str, str]] = {}
    for o in _active(db.query(ScopingFieldOrigin), ScopingFieldOrigin).filter(
            ScopingFieldOrigin.scoping_id == scoping_id):
        out.setdefault((o.target_type, o.target_id), {})[o.field] = o.status
    return out


def badge_count(db: Session, scoping_id: UUID) -> int:
    """아직 템플릿 그대로인 필드 수 — 확정 경고에 쓴다. **`template` 만 센다**(confirmed 는 본 것이다)."""
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
    if o is not None and o.status in (ORIGIN_TEMPLATE, ORIGIN_CONFIRMED):
        o.status = ORIGIN_EDITED   # 확인한 값을 고쳐도 수정이다
        o.confirmed_by_id = o.confirmed_at = None


def confirm_targets(db: Session, s: Scoping, scope: str, target_id: UUID | None) -> list[tuple[str, UUID]]:
    """확인 범위 → (대상 종류, 대상 id) 목록. 대상 존재는 여기서 검증한다(출처 행에 FK 가 없다).
    없으면 LookupError."""
    if scope == CONFIRM_SCOPE_MATERIALITY:
        benches = _active(db.query(ScopingBenchmark), ScopingBenchmark).filter(
            ScopingBenchmark.scoping_id == s.id).all()
        return [(ORIGIN_TARGET_SCOPING, s.id)] + [(ORIGIN_TARGET_BENCHMARK, b.id) for b in benches]
    model, target_type = {CONFIRM_SCOPE_ACCOUNT: (ScopingAccount, ORIGIN_TARGET_ACCOUNT),
                          CONFIRM_SCOPE_TEXT: (ScopingText, ORIGIN_TARGET_TEXT)}[scope]
    if target_id is None or _active(db.query(model), model).filter(
            model.id == target_id, model.scoping_id == s.id).first() is None:
        raise LookupError(scope)
    return [(target_type, target_id)]


def set_confirmed(db: Session, s: Scoping, targets: list[tuple[str, UUID]], user_id: UUID,
                  undo: bool = False) -> int:
    """검토 확인(template → confirmed) 또는 확인 취소(confirmed → template). 바뀐 필드 수를 돌려준다.

    **edited 는 건드리지 않는다** — 회사가 고친 값은 확인 대상이 아니고, 취소해도 템플릿으로 돌아가지 않는다.
    """
    frm, to = (ORIGIN_CONFIRMED, ORIGIN_TEMPLATE) if undo else (ORIGIN_TEMPLATE, ORIGIN_CONFIRMED)
    now = datetime.now(UTC)
    n = 0
    for target_type, target_id in targets:
        for o in _origins(db, s.id).filter(ScopingFieldOrigin.target_type == target_type,
                                           ScopingFieldOrigin.target_id == target_id,
                                           ScopingFieldOrigin.status == frm):
            o.status = to
            o.confirmed_by_id, o.confirmed_at = (None, None) if undo else (user_id, now)
            n += 1
    return n


def origin_counts(db: Session, scoping_id: UUID) -> dict[str, int]:
    """상태별 필드 수 {template, confirmed, edited}."""
    out = {ORIGIN_TEMPLATE: 0, ORIGIN_CONFIRMED: 0, ORIGIN_EDITED: 0}
    for o in _origins(db, scoping_id):
        out[o.status] = out.get(o.status, 0) + 1
    return out


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

def _rate_str(v) -> str | None:
    return None if v is None else format(Decimal(str(v)).normalize(), "f")


def _pct(v: str | None) -> str:
    if v is None:
        return ""
    return format((Decimal(v) * 100).normalize(), "f") + "%"


def evaluate(db: Session, s: Scoping) -> dict:
    """스코핑 1건의 산출 결과 — 양적 중요성·계정별 판정·경고. **저장하지 않는다.**"""
    crit = criteria(db, s)
    threshold, comparison = crit["qual_threshold"], crit["qual_comparison"]
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
        guide = _range(b.guide_low, b.guide_high) if b else None
        bench_rows.append({
            "kind": kind, "label": BENCHMARK_LABELS[kind], "id": b.id if b else None,
            "base_amount": base, "effective_base": effective, "rate": _rate_str(rate),
            "amount": calc.benchmark_amount(effective, rate),
            "guide_range": list(guide) if guide else None,
            "out_of_range": calc.out_of_range(rate, guide),
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
            "change_rate": change_rate(a.current_amount, a.prior_amount),
            "qual": qual, "computed": computed, "final": calc.final_conclusion(computed, a.manual_conclusion),
        })

    warnings = []
    for r in bench_rows:
        if r["out_of_range"]:
            warnings.append(f"{r['label']} 비율 {r['rate']} 이 가이드 범위를 벗어났습니다")
    smt_guide = crit["smt_guide"]
    smt_out = calc.out_of_range(s.smt_rate, smt_guide)
    if smt_out:
        lo, hi = smt_guide
        warnings.append(f"수행중요성 설정율 {_rate_str(s.smt_rate)} 이 가이드 범위"
                        f"({_pct(lo)}~{_pct(hi)})를 벗어났습니다")
    if not (s.rationale or "").strip():
        warnings.append("중요성 설정근거가 비어 있습니다 — 검토 요청·확정 전에 입력해야 합니다")

    return {
        "policy": {"threshold": _rate_str(threshold), "comparison": comparison},
        "base_fiscal_year": crit["base_fiscal_year"],
        "smt_guide_range": list(smt_guide) if smt_guide else None,
        "benchmarks": bench_rows, "adjustments": adjustments,
        "selected_benchmark": s.selected_benchmark, "overall_materiality": overall,
        "smt": smt, "smt_rate": _rate_str(s.smt_rate),
        "smt_out_of_range": smt_out,
        "accounts": acc_rows, "warnings": warnings,
    }


def snapshot(db: Session, s: Scoping) -> dict:
    """확정 스냅샷 — **결론과 그 결론을 낸 기준을 값으로 굳힌다**(6-1b §3.3).

    확정 뒤 기준·정책·템플릿이 바뀌어도 "그 해에는 어떤 기준으로 무엇이 유의였나"가 그대로 보여야
    한다 — 감사인이 묻는 것이 정확히 이것이다. 그래서 결론만이 아니라 벤치마크 6종의 기준값·비율·
    산출액, 조정 항목, 가이드 범위, 설정율 범위, 질적 기준, 기준 연도, 계정별 금액·질적 평균까지 담는다.
    """
    ev = evaluate(db, s)
    return {
        "taken_at": datetime.now(UTC).isoformat(),
        "policy": ev["policy"],   # 질적 기준(기준값·비교 방식) — 6-1 키 이름 유지
        "base_fiscal_year": ev["base_fiscal_year"],
        "selected_benchmark": ev["selected_benchmark"],
        "benchmarks": [
            {k: r[k] for k in ("kind", "label", "base_amount", "effective_base", "rate", "amount",
                               "guide_range", "out_of_range")}
            for r in ev["benchmarks"]
        ],
        "adjustments": [{"amount": a.amount, "reason": a.reason} for a in ev["adjustments"]],
        "overall_materiality": ev["overall_materiality"],
        "smt": ev["smt"], "smt_rate": ev["smt_rate"], "smt_guide_range": ev["smt_guide_range"],
        "accounts": {
            str(r["account"].id): {
                "name": r["account"].name, "statement_type": r["account"].statement_type,
                "current_amount": r["account"].current_amount, "prior_amount": r["account"].prior_amount,
                "qual_average": r["qual_average"],
                "quant": r["quant"], "qual": r["qual"], "computed": r["computed"],
                "manual": r["account"].manual_conclusion, "final": r["final"],
            }
            for r in ev["accounts"]
        },
    }
