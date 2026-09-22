"""스코핑 API — ADR-0034, 6-1.

**권한**(ADR-0034 §2.10): 작성·수정·상태 전이는 전부 `icfr_manager`. 조회는 전원(`external_auditor`
포함). `require_write` 로 기본 처리하지 않는다 — 그러면 external_auditor 만 막히고 일반 사용자가
쓴다(13.9-35·41).

**확정되면 수정할 수 없다**(§2.2) — 모든 쓰기가 409. 재오픈(확정 → 작성 중)은 사유가 필요하고
이력에 남는다.

**산출값은 저장하지 않는다** — 매 조회가 `services/scoping.evaluate` 로 계산한다.
확정 시점에만 `snapshot` 으로 결론과 기준을 굳혀 저장한다.

**중요성 기준은 스코핑 필드다**(6-1b) — 비율 가이드 범위·설정율 범위·질적 기준·기준 연도를
PATCH 로 바꾼다. 테넌트 정책은 새 연도 생성 때 기본값으로만 쓴다.
"""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_manager, tenant_roles
from app.models.role_assignment import ROLE_ICFR_MANAGER
from app.models.scoping import (
    BENCHMARK_GUIDE_RANGES,
    BENCHMARK_LABELS,
    BENCHMARKS,
    CONFIRM_SCOPES,
    DEFAULT_TEMPLATE_CODE,
    ORIGIN_LABELS,
    ORIGIN_TARGET_ACCOUNT,
    ORIGIN_TARGET_BENCHMARK,
    ORIGIN_TARGET_SCOPING,
    ORIGIN_TARGET_TEXT,
    QUAL_COMPARISONS,
    QUAL_FACTOR_LABELS,
    QUAL_FACTORS,
    QUANT_APPLICABLE_STATEMENTS,
    RATING_LABELS,
    RATINGS,
    SMT_RATE_GUIDE_RANGE,
    STATEMENT_LABELS,
    STATUS_CONFIRMED,
    STATUS_DRAFT,
    STATUS_LABELS,
    STATUS_REVIEW,
    TRANSITIONS,
    Scoping,
    ScopingAccount,
    ScopingAdjustment,
    ScopingBenchmark,
    ScopingStatusHistory,
    ScopingTemplate,
    ScopingText,
)
from app.models.user import User
from app.schemas.scoping import (
    AccountRead,
    AccountUpdate,
    AdjustmentCreate,
    AdjustmentRead,
    BenchmarkRow,
    BenchmarkUpdate,
    ConfirmRequest,
    HistoryRead,
    Option,
    ScopingCreate,
    ScopingDetail,
    ScopingListItem,
    ScopingMeta,
    ScopingSummary,
    ScopingUpdate,
    TemplateRead,
    TextRead,
    TextUpdate,
    TransitionRequest,
)
from app.services import scoping as svc

router = APIRouter(prefix="/api/scoping", tags=["scoping"])


def _opts(labels: dict[str, str]) -> list[Option]:
    return [Option(value=k, label=v) for k, v in labels.items()]


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {"module": "scoping", "name_kr": "Scoping", "phase_1_status": "6-1 스코핑 코어",
            "next": ["계정↔프로세스 연계·GITC·재무제표 업로드(6-2)"], "available_in_phase_1": True}


@router.get("/meta", response_model=ScopingMeta)
def get_meta(user: CurrentUser = None) -> ScopingMeta:
    """선택지·가이드 범위를 서버가 준다 — 화면이 목록을 따로 들면 상수와 어긋난다(13.9-40)."""
    return ScopingMeta(
        statement_types=_opts(STATEMENT_LABELS), benchmarks=_opts(BENCHMARK_LABELS),
        qual_factors=_opts(QUAL_FACTOR_LABELS), ratings=_opts(RATING_LABELS),
        statuses=_opts(STATUS_LABELS), origin_statuses=_opts(ORIGIN_LABELS),
        qual_comparisons=_opts(QUAL_COMPARISONS),
        benchmark_guide_ranges={k: (list(v) if v else None) for k, v in BENCHMARK_GUIDE_RANGES.items()},
        smt_rate_guide_range=list(SMT_RATE_GUIDE_RANGE),
        confirm_scopes=list(CONFIRM_SCOPES),
        quant_applicable=sorted(QUANT_APPLICABLE_STATEMENTS),
    )


@router.get("/templates", response_model=list[TemplateRead])
def list_templates(user: CurrentUser = None, db: Session = Depends(get_db)) -> list[ScopingTemplate]:
    return db.query(ScopingTemplate).filter(ScopingTemplate.is_deleted == False).order_by(  # noqa: E712
        ScopingTemplate.code, ScopingTemplate.version).all()


# ── 조회 ───────────────────────────────────────────────────

def _get(db: Session, scoping_id: UUID) -> Scoping:
    s = db.query(Scoping).filter(Scoping.id == scoping_id, Scoping.is_deleted == False).first()  # noqa: E712
    if s is None:
        raise HTTPException(status_code=404, detail="스코핑을 찾을 수 없습니다")
    return s


def _detail(db: Session, s: Scoping, user_id: UUID) -> ScopingDetail:
    ev = svc.evaluate(db, s)
    origins = svc.origins_by_target(db, s.id)
    snap = (s.confirmed_snapshot or {}).get("accounts", {}) if s.status == STATUS_CONFIRMED else {}

    benches = []
    for r in ev["benchmarks"]:
        o = origins.get((ORIGIN_TARGET_BENCHMARK, r["id"]), {}) if r["id"] else {}
        benches.append(BenchmarkRow(**{k: v for k, v in r.items() if k != "id"},
                                    badge=o.get("rate"), guide_badge=o.get("guide")))

    texts = db.query(ScopingText).filter(ScopingText.scoping_id == s.id,
                                         ScopingText.is_deleted == False).order_by(  # noqa: E712
        ScopingText.sort_order).all()
    accounts = []
    for r in ev["accounts"]:
        a = r["account"]
        accounts.append(AccountRead(
            id=a.id, statement_type=a.statement_type, sort_order=a.sort_order, group_label=a.group_label,
            name=a.name, current_amount=a.current_amount, prior_amount=a.prior_amount,
            ratings={k: v for k, v in (a.ratings or {}).items() if v}, qual_basis=a.qual_basis,
            manual_conclusion=a.manual_conclusion, manual_reason=a.manual_reason,
            quant=r["quant"], qual_average=r["qual_average"], change_rate=r["change_rate"], qual=r["qual"],
            computed=r["computed"], final=r["final"],
            snapshot_final=snap.get(str(a.id), {}).get("final") if snap else None,
            badges=origins.get((ORIGIN_TARGET_ACCOUNT, a.id), {}),
        ))
    history = db.query(ScopingStatusHistory).filter(
        ScopingStatusHistory.scoping_id == s.id,
        ScopingStatusHistory.is_deleted == False,  # noqa: E712
    ).order_by(ScopingStatusHistory.created_at).all()
    return ScopingDetail(
        id=s.id, fiscal_year=s.fiscal_year, status=s.status, template_code=s.template_code,
        template_version=s.template_version, policy=ev["policy"],
        base_fiscal_year=ev["base_fiscal_year"], smt_guide_range=ev["smt_guide_range"], benchmarks=benches,
        adjustments=[AdjustmentRead.model_validate(a) for a in ev["adjustments"]],
        selected_benchmark=ev["selected_benchmark"], overall_materiality=ev["overall_materiality"],
        smt=ev["smt"], smt_rate=ev["smt_rate"], smt_out_of_range=ev["smt_out_of_range"],
        rationale=s.rationale, scoping_badges=origins.get((ORIGIN_TARGET_SCOPING, s.id), {}),
        texts=[TextRead(id=t.id, key=t.key, title=t.title, body=t.body,
                        badge=origins.get((ORIGIN_TARGET_TEXT, t.id), {}).get("body")) for t in texts],
        accounts=accounts, warnings=ev["warnings"], badge_count=svc.badge_count(db, s.id),
        origin_counts=svc.origin_counts(db, s.id),
        confirmed_at=s.confirmed_at, confirm_reason=s.confirm_reason,
        confirm_badge_count=s.confirm_badge_count, confirmed_snapshot=s.confirmed_snapshot,
        review_auditor=s.review_auditor, review_date=s.review_date, review_opinion=s.review_opinion,
        review_evidence_ref=s.review_evidence_ref,
        history=[HistoryRead.model_validate(h) for h in history],
        can_edit=s.status != STATUS_CONFIRMED and ROLE_ICFR_MANAGER in tenant_roles(db, user_id),
    )


@router.get("", response_model=list[ScopingListItem])
def list_scopings(user: CurrentUser = None, db: Session = Depends(get_db)) -> list[Scoping]:
    return db.query(Scoping).filter(Scoping.is_deleted == False).order_by(  # noqa: E712
        Scoping.fiscal_year.desc()).all()


@router.get("/summary", response_model=ScopingSummary)
def get_summary(user: CurrentUser = None, db: Session = Depends(get_db)) -> ScopingSummary:
    """대시보드 카드 — 가장 최근 회계연도. **미평가를 따로 센다**(0 을 가리지 않는다)."""
    s = db.query(Scoping).filter(Scoping.is_deleted == False).order_by(  # noqa: E712
        Scoping.fiscal_year.desc()).first()
    if s is None:
        return ScopingSummary(exists=False)
    by = {t: {"Y": 0, "N": 0, "unevaluated": 0} for t in STATEMENT_LABELS}
    # 확정 상태면 스냅샷으로 센다 — 화면(계정 표)과 같은 기준. 정책이 바뀌어도 확정 결론은 그대로다
    if s.status == STATUS_CONFIRMED and s.confirmed_snapshot:
        snap = s.confirmed_snapshot
        rows = [(v["statement_type"], v["final"]) for v in snap.get("accounts", {}).values()]
        overall, smt = snap.get("overall_materiality"), snap.get("smt")
    else:
        ev = svc.evaluate(db, s)
        rows = [(r["account"].statement_type, r["final"]) for r in ev["accounts"]]
        overall, smt = ev["overall_materiality"], ev["smt"]
    for stype, final in rows:
        by[stype][final if final in ("Y", "N") else "unevaluated"] += 1
    return ScopingSummary(exists=True, fiscal_year=s.fiscal_year, status=s.status,
                          overall_materiality=overall, smt=smt,
                          badge_count=svc.badge_count(db, s.id), by_statement=by)


@router.get("/{scoping_id}", response_model=ScopingDetail)
def get_scoping(scoping_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> ScopingDetail:
    return _detail(db, _get(db, scoping_id), user.id)


# ── 쓰기 (전부 icfr_manager) ───────────────────────────────

def _assert_range(lo, hi, label: str) -> None:
    if lo is not None and hi is not None and lo > hi:
        raise HTTPException(status_code=422, detail=f"{label}: 하한이 상한보다 큽니다")

def _editable(db: Session, scoping_id: UUID) -> Scoping:
    s = _get(db, scoping_id)
    if s.status == STATUS_CONFIRMED:
        raise HTTPException(status_code=409,
                            detail="확정된 스코핑은 수정할 수 없습니다. 재오픈(작성 중으로 전환)한 뒤 수정하세요")
    return s


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScopingDetail)
def create_scoping(body: ScopingCreate, user: User = Depends(require_icfr_manager),
                   db: Session = Depends(get_db)) -> ScopingDetail:
    """회계연도 스코핑 생성 — 템플릿을 **복사**한다. 버전을 안 주면 그 코드의 최신 버전."""
    if db.query(Scoping).filter(Scoping.fiscal_year == body.fiscal_year,
                                Scoping.is_deleted == False).first() is not None:  # noqa: E712
        raise HTTPException(status_code=409, detail=f"{body.fiscal_year} 회계연도 스코핑이 이미 있습니다")
    q = db.query(ScopingTemplate).filter(ScopingTemplate.code == (body.template_code or DEFAULT_TEMPLATE_CODE),
                                         ScopingTemplate.is_deleted == False)  # noqa: E712
    if body.template_version is not None:
        q = q.filter(ScopingTemplate.version == body.template_version)
    tpl = q.order_by(ScopingTemplate.version.desc()).first()
    if tpl is None:
        raise HTTPException(status_code=404,
                            detail="템플릿을 찾을 수 없습니다 — 운영에서는 seeds.seed_scoping_template 적재가 먼저다")
    s = svc.create_from_template(db, body.fiscal_year, tpl)
    db.commit()
    return _detail(db, s, user.id)


@router.patch("/{scoping_id}", response_model=ScopingDetail)
def update_scoping(scoping_id: UUID, body: ScopingUpdate, user: User = Depends(require_icfr_manager),
                   db: Session = Depends(get_db)) -> ScopingDetail:
    s = _editable(db, scoping_id)
    changes = body.model_dump(exclude_unset=True)
    for field in ("selected_benchmark", "smt_rate", "qual_threshold", "qual_comparison", "base_fiscal_year"):
        # 판정 기준은 비울 수 없다 — 비우면 무엇으로 판정했는지가 사라진다
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"'{field}' 는 비울 수 없습니다")
    lo = changes.get("smt_guide_low", s.smt_guide_low)
    hi = changes.get("smt_guide_high", s.smt_guide_high)
    _assert_range(lo, hi, "수행중요성 설정율 가이드 범위")
    guide_changed = False
    for field, value in changes.items():
        if svc.changed(getattr(s, field), value):
            setattr(s, field, value)
            if field in ("smt_guide_low", "smt_guide_high"):
                guide_changed = True   # 범위는 두 칸이 한 필드(배지 하나)다
            elif field != "base_fiscal_year" and not field.startswith("review_"):
                svc.mark_edited(db, s.id, ORIGIN_TARGET_SCOPING, s.id, field)
    if guide_changed:
        svc.mark_edited(db, s.id, ORIGIN_TARGET_SCOPING, s.id, "smt_guide")
    db.commit()
    return _detail(db, s, user.id)


@router.patch("/{scoping_id}/benchmarks/{kind}", response_model=ScopingDetail)
def update_benchmark(scoping_id: UUID, kind: str, body: BenchmarkUpdate,
                     user: User = Depends(require_icfr_manager), db: Session = Depends(get_db)) -> ScopingDetail:
    if kind not in BENCHMARKS:
        raise HTTPException(status_code=404, detail=f"알 수 없는 벤치마크 '{kind}'")
    s = _editable(db, scoping_id)
    b = db.query(ScopingBenchmark).filter(ScopingBenchmark.scoping_id == s.id, ScopingBenchmark.kind == kind,
                                          ScopingBenchmark.is_deleted == False).first()  # noqa: E712
    if b is None:
        b = ScopingBenchmark(scoping_id=s.id, kind=kind)
        db.add(b)
        db.flush()
    changes = body.model_dump(exclude_unset=True)
    if "base_amount" in changes and svc.changed(b.base_amount, changes["base_amount"]):
        b.base_amount = changes["base_amount"]   # 금액은 템플릿에 없으므로 배지 대상이 아니다
    if "rate" in changes and svc.changed(b.rate, changes["rate"]):
        b.rate = changes["rate"]
        svc.mark_edited(db, s.id, ORIGIN_TARGET_BENCHMARK, b.id, "rate")
    if "guide_low" in changes or "guide_high" in changes:
        lo = changes.get("guide_low", b.guide_low)
        hi = changes.get("guide_high", b.guide_high)
        _assert_range(lo, hi, f"{BENCHMARK_LABELS[kind]} 비율 가이드 범위")
        if svc.changed(b.guide_low, lo) or svc.changed(b.guide_high, hi):
            b.guide_low, b.guide_high = lo, hi
            svc.mark_edited(db, s.id, ORIGIN_TARGET_BENCHMARK, b.id, "guide")
    db.commit()
    return _detail(db, s, user.id)


@router.post("/{scoping_id}/adjustments", status_code=status.HTTP_201_CREATED, response_model=ScopingDetail)
def add_adjustment(scoping_id: UUID, body: AdjustmentCreate, user: User = Depends(require_icfr_manager),
                   db: Session = Depends(get_db)) -> ScopingDetail:
    s = _editable(db, scoping_id)
    db.add(ScopingAdjustment(scoping_id=s.id, amount=body.amount, reason=body.reason.strip()))
    db.commit()
    return _detail(db, s, user.id)


@router.delete("/{scoping_id}/adjustments/{adjustment_id}", response_model=ScopingDetail)
def delete_adjustment(scoping_id: UUID, adjustment_id: UUID, user: User = Depends(require_icfr_manager),
                      db: Session = Depends(get_db)) -> ScopingDetail:
    s = _editable(db, scoping_id)
    a = db.query(ScopingAdjustment).filter(ScopingAdjustment.id == adjustment_id,
                                           ScopingAdjustment.scoping_id == s.id,
                                           ScopingAdjustment.is_deleted == False).first()  # noqa: E712
    if a is None:
        raise HTTPException(status_code=404, detail="조정 항목을 찾을 수 없습니다")
    a.is_deleted = True
    db.commit()
    return _detail(db, s, user.id)


@router.patch("/{scoping_id}/texts/{key}", response_model=ScopingDetail)
def update_text(scoping_id: UUID, key: str, body: TextUpdate, user: User = Depends(require_icfr_manager),
                db: Session = Depends(get_db)) -> ScopingDetail:
    s = _editable(db, scoping_id)
    t = db.query(ScopingText).filter(ScopingText.scoping_id == s.id, ScopingText.key == key,
                                     ScopingText.is_deleted == False).first()  # noqa: E712
    if t is None:
        raise HTTPException(status_code=404, detail=f"문구 '{key}' 를 찾을 수 없습니다")
    if svc.changed(t.body, body.body):
        t.body = body.body
        svc.mark_edited(db, s.id, ORIGIN_TARGET_TEXT, t.id, "body")
    db.commit()
    return _detail(db, s, user.id)


@router.patch("/{scoping_id}/accounts/{account_id}", response_model=ScopingDetail)
def update_account(scoping_id: UUID, account_id: UUID, body: AccountUpdate,
                   user: User = Depends(require_icfr_manager), db: Session = Depends(get_db)) -> ScopingDetail:
    """계정 평가 수정. **배지는 바뀐 필드만 떨어진다** — 질적 요소 하나를 고치면 그 요소만."""
    s = _editable(db, scoping_id)
    a = db.query(ScopingAccount).filter(ScopingAccount.id == account_id, ScopingAccount.scoping_id == s.id,
                                        ScopingAccount.is_deleted == False).first()  # noqa: E712
    if a is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다")
    changes = body.model_dump(exclude_unset=True)

    for field in ("current_amount", "prior_amount"):
        if field in changes and svc.changed(getattr(a, field), changes[field]):
            setattr(a, field, changes[field])

    if "ratings" in changes and changes["ratings"] is not None:
        ratings = dict(a.ratings or {})
        for factor, value in changes["ratings"].items():
            if factor not in QUAL_FACTORS:
                raise HTTPException(status_code=422, detail=f"알 수 없는 질적 요소 '{factor}'")
            if value is not None and value not in RATINGS:
                raise HTTPException(status_code=422, detail=f"평가값은 {', '.join(RATINGS)} 중 하나여야 합니다")
            if svc.changed(ratings.get(factor), value):
                if value is None:
                    ratings.pop(factor, None)
                else:
                    ratings[factor] = value
                svc.mark_edited(db, s.id, ORIGIN_TARGET_ACCOUNT, a.id, f"ratings.{factor}")
        a.ratings = ratings   # JSON 은 새 객체를 넣어야 변경이 감지된다

    if "qual_basis" in changes and svc.changed(a.qual_basis, changes["qual_basis"]):
        a.qual_basis = changes["qual_basis"]
        svc.mark_edited(db, s.id, ORIGIN_TARGET_ACCOUNT, a.id, "qual_basis")

    # 수동 판정 — **사유 필수.** 결론을 비우면 사유도 함께 비운다(사유만 남는 상태를 만들지 않는다)
    if "manual_conclusion" in changes or "manual_reason" in changes:
        new_c = changes.get("manual_conclusion", a.manual_conclusion)
        new_r = changes.get("manual_reason", a.manual_reason)
        if new_c is None:
            new_r = None
        elif not (new_r or "").strip():
            raise HTTPException(status_code=422, detail="수동 판정에는 사유가 필요합니다")
        if svc.changed(a.manual_conclusion, new_c) or svc.changed(a.manual_reason, new_r):
            a.manual_conclusion, a.manual_reason = new_c, (new_r.strip() if new_r else None)
            svc.mark_edited(db, s.id, ORIGIN_TARGET_ACCOUNT, a.id, "manual")
    db.commit()
    return _detail(db, s, user.id)


@router.post("/{scoping_id}/confirm", response_model=ScopingDetail)
def confirm_review(scoping_id: UUID, body: ConfirmRequest, user: User = Depends(require_icfr_manager),
                   db: Session = Depends(get_db)) -> ScopingDetail:
    """검토 확인 / 확인 취소 (6-1b §3.1). 확정 상태면 409.

    템플릿 값에 **동의한다**는 표시다 — 값은 바뀌지 않고 상태만 `template → confirmed` 가 된다.
    누가·언제 확인했는지 남는다. 확정 경고 숫자는 `template` 만 세므로, 다 보면 0 이 된다.
    """
    s = _editable(db, scoping_id)
    try:
        targets = svc.confirm_targets(db, s, body.scope, body.target_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="확인할 대상을 찾을 수 없습니다") from None
    svc.set_confirmed(db, s, targets, user.id, undo=body.undo)
    db.commit()
    return _detail(db, s, user.id)


@router.post("/{scoping_id}/transition", response_model=ScopingDetail)
def transition(scoping_id: UUID, req: TransitionRequest, user: User = Depends(require_icfr_manager),
               db: Session = Depends(get_db)) -> ScopingDetail:
    """상태 전이 (ADR-0034 §2.2).

    - 작성 중 → 검토 중: 설정근거 필수
    - 검토 중 → 확정: 설정근거·**확정 사유** 필수. **배지 남은 개수를 기록하고 결론 스냅샷을 남긴다.**
      배지가 남아 있어도 막지 않는다 — 개수를 드러내는 것이 목적이다
    - 검토 중 → 작성 중: 되돌림(사유 선택)
    - 확정 → 작성 중: **재오픈. 사유 필수**, 이력 기록. 확정 스냅샷은 이력에 남기고 비운다
    """
    s = _get(db, scoping_id)
    if req.to_status not in TRANSITIONS.get(s.status, set()):
        raise HTTPException(status_code=409, detail=(
            f"'{STATUS_LABELS[s.status]}' 에서 '{STATUS_LABELS[req.to_status]}' 로 바꿀 수 없습니다"))
    reason = (req.reason or "").strip() or None
    needs_rationale = req.to_status in (STATUS_REVIEW, STATUS_CONFIRMED)
    if needs_rationale and not (s.rationale or "").strip():
        raise HTTPException(status_code=409, detail="중요성 설정근거를 먼저 입력하세요 — 감사에서 묻는다")
    if req.to_status == STATUS_CONFIRMED and not reason:
        raise HTTPException(status_code=422, detail="확정 사유가 필요합니다")
    if s.status == STATUS_CONFIRMED and req.to_status == STATUS_DRAFT and not reason:
        raise HTTPException(status_code=422, detail="재오픈 사유가 필요합니다")

    badges = svc.badge_count(db, s.id)
    hist = ScopingStatusHistory(scoping_id=s.id, from_status=s.status, to_status=req.to_status,
                                reason=reason, actor_id=user.id, badge_count=badges)
    if req.to_status == STATUS_CONFIRMED:
        snap = svc.snapshot(db, s)
        s.confirmed_snapshot, s.confirmed_at, s.confirmed_by_id = snap, datetime.now(UTC), user.id
        s.confirm_reason, s.confirm_badge_count = reason, badges
        hist.snapshot = snap
    elif s.status == STATUS_CONFIRMED:
        s.confirmed_snapshot = s.confirmed_at = s.confirmed_by_id = None
        s.confirm_reason = s.confirm_badge_count = None
    s.status = req.to_status
    db.add(hist)
    db.commit()
    return _detail(db, s, user.id)
