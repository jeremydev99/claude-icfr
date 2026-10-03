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

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_icfr_staff
from app.minio_client import build_governance_key, upload_object
from app.models.governance import (
    ENTITY_SCOPING,
    EV_APPROVE,
    EV_EXTERNAL_APPROVE,
    EV_REOPEN_APPROVE,
    EV_REOPEN_REJECT,
    EV_REOPEN_REQUEST,
    EV_REVIEW_DONE,
    EV_REVIEW_RETURN,
    EV_SUBMIT,
    EV_WITHDRAW,
    EXTERNAL_BODIES,
    PATH_EXTERNAL,
    PATH_LEAD_THEN_MASTER,
    REOPEN_APPROVED,
    REOPEN_REJECTED,
    ExternalApproval,
    GovernanceEvent,
    GovernanceFile,
    ReopenRequest,
)
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
    ExternalApprovalRead,
    ExternalFileRead,
    GovernanceCan,
    GovernanceEventRead,
    GovernanceInfo,
    HistoryRead,
    Option,
    PersonRef,
    ReopenCreate,
    ReopenDecision,
    ReopenRead,
    ReviewRequest,
    ScopingCoverage,
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
from app.services import approval, scoping_coverage, scoping_fs
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
            id=a.id, fs_account_id=a.fs_account_id, statement_type=a.statement_type, sort_order=a.sort_order,
            group_label=a.group_label,
            name=a.name, current_amount=a.current_amount, prior_amount=a.prior_amount,
            ratings={k: v for k, v in (a.ratings or {}).items() if v}, qual_basis=a.qual_basis,
            manual_conclusion=a.manual_conclusion, manual_reason=a.manual_reason,
            quant=r["quant"], qual_average=r["qual_average"], change_rate=r["change_rate"], qual=r["qual"],
            computed=r["computed"], final=r["final"],
            snapshot_final=snap.get(str(a.id), {}).get("final") if snap else None,
            badges=origins.get((ORIGIN_TARGET_ACCOUNT, a.id), {}),
        ))
    gov = _governance(db, s, user_id)
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
        can_edit=gov.can.edit,
        governance=gov,
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


@router.get("/{scoping_id}/coverage", response_model=ScopingCoverage)
def get_coverage(scoping_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    """유의 계정 ↔ RCM 통제 커버리지(이름 대조 추정, 저장 안 함) — `services/scoping_coverage.py`."""
    return scoping_coverage.coverage(db, _get(db, scoping_id))


# ── 쓰기 (관리자 1~3단계, ADR-0038 — 작성 중일 때만) ─────────────

def _assert_range(lo, hi, label: str) -> None:
    if lo is not None and hi is not None and lo > hi:
        raise HTTPException(status_code=422, detail=f"{label}: 하한이 상한보다 큽니다")

def _editable(db: Session, scoping_id: UUID) -> Scoping:
    s = _get(db, scoping_id)
    if s.status == STATUS_CONFIRMED:
        raise HTTPException(status_code=409,
                            detail="확정된 스코핑은 수정할 수 없습니다 — 재오픈 요청이 승인되면 수정할 수 있습니다")
    if s.status == STATUS_REVIEW:
        # 검토·승인 중에 내용이 바뀌면 검토자가 본 것과 승인되는 것이 달라진다(ADR-0038)
        raise HTTPException(status_code=409,
                            detail="검토·승인 중에는 수정할 수 없습니다 — 요청자가 회수하거나 반려된 뒤 수정하세요")
    return s


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScopingDetail)
def create_scoping(body: ScopingCreate, user: User = Depends(require_icfr_staff),
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
    if body.source == "financial_statements":
        try:
            s, _summary = scoping_fs.create(db, body.fiscal_year, tpl)
        except scoping_fs.ScopingSourceError as e:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(e)) from None
    else:
        s = svc.create_from_template(db, body.fiscal_year, tpl)
    db.commit()
    return _detail(db, s, user.id)


@router.patch("/{scoping_id}", response_model=ScopingDetail)
def update_scoping(scoping_id: UUID, body: ScopingUpdate, user: User = Depends(require_icfr_staff),
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
                     user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> ScopingDetail:
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
def add_adjustment(scoping_id: UUID, body: AdjustmentCreate, user: User = Depends(require_icfr_staff),
                   db: Session = Depends(get_db)) -> ScopingDetail:
    s = _editable(db, scoping_id)
    db.add(ScopingAdjustment(scoping_id=s.id, amount=body.amount, reason=body.reason.strip()))
    db.commit()
    return _detail(db, s, user.id)


@router.delete("/{scoping_id}/adjustments/{adjustment_id}", response_model=ScopingDetail)
def delete_adjustment(scoping_id: UUID, adjustment_id: UUID, user: User = Depends(require_icfr_staff),
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
def update_text(scoping_id: UUID, key: str, body: TextUpdate, user: User = Depends(require_icfr_staff),
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
                   user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> ScopingDetail:
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


@router.post("/{scoping_id}/reload-from-fs", response_model=ScopingDetail)
def reload_from_fs(scoping_id: UUID, user: User = Depends(require_icfr_staff),
                   db: Session = Depends(get_db)) -> ScopingDetail:
    """작성 중 스코핑을 기준 연도 **확정 재무제표**로 다시 채운다 — 계정 행·당기/전기 금액·벤치마크 기준값.

    재무제표를 스코핑보다 나중에 올렸을 때의 경로다(2026-10-03). 기존 계정 행·배지는 교체되며, 이력에는 요약 1건
    (교체 행 수·채운 기준값·못 찾은 항목)이 남는다. 작성 중일 때만 — 검토·승인 중이나 확정이면 409.
    """
    s = _editable(db, scoping_id)
    tpl = db.query(ScopingTemplate).filter(ScopingTemplate.code == (s.template_code or DEFAULT_TEMPLATE_CODE),
                                           ScopingTemplate.is_deleted == False).order_by(  # noqa: E712
        ScopingTemplate.version.desc())
    if s.template_version is not None:
        tpl = tpl.filter(ScopingTemplate.version == s.template_version)
    template = tpl.first()
    if template is None:
        raise HTTPException(status_code=404, detail="스코핑 템플릿을 찾을 수 없습니다")
    try:
        summary = scoping_fs.reload_from_fs(db, s, template)
    except scoping_fs.ScopingSourceError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from None
    glog.record(db, s.id, "value_change", version=s.version, target="재무제표에서 다시 불러오기",
                reason=f"기준 연도 FY{s.base_fiscal_year or s.fiscal_year - 1} 확정 재무제표",
                after={"교체한 계정 행": summary["replaced_rows"], "새 계정 행": summary["rows"],
                       "템플릿 연결": summary["linked"], "기준값": summary["benchmarks"],
                       "못 찾은 기준값": summary["benchmark_missing"]})
    db.commit()
    return _detail(db, s, user.id)


@router.post("/{scoping_id}/confirm", response_model=ScopingDetail)
def confirm_review(scoping_id: UUID, body: ConfirmRequest, user: User = Depends(require_icfr_staff),
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


def _person(db: Session, uid) -> PersonRef | None:
    if uid is None:
        return None
    u = db.get(User, uid)
    return PersonRef(id=uid, name=u.display_name if u else "(삭제된 사용자)")


def _reopen_read(db: Session, r: ReopenRequest) -> ReopenRead:
    return ReopenRead(id=r.id, requested_by=_person(db, r.requested_by_id), requested_tier=r.requested_tier,
                      reason=r.reason, status=r.status, decided_by=_person(db, r.decided_by_id),
                      decided_at=r.decided_at, decision_reason=r.decision_reason, created_at=r.created_at)


def _governance(db: Session, s: Scoping, user_id: UUID) -> GovernanceInfo:
    c = approval.can(db, s, user_id)
    t = approval.user_tier(db, user_id)
    pend = approval.pending_reopen(db, s.id)
    exts = db.query(ExternalApproval).filter(ExternalApproval.entity_type == ENTITY_SCOPING,
                                             ExternalApproval.entity_id == s.id,
                                             ExternalApproval.is_deleted == False).order_by(  # noqa: E712
        ExternalApproval.created_at).all()
    ext_reads = []
    for e in exts:
        files = db.query(GovernanceFile).filter(GovernanceFile.external_approval_id == e.id,
                                                GovernanceFile.is_deleted == False).all()  # noqa: E712
        ext_reads.append(ExternalApprovalRead(
            id=e.id, purpose=e.purpose, approver_body=e.approver_body, approved_on=e.approved_on,
            reference=e.reference, recorded_by=_person(db, e.recorded_by_id), created_at=e.created_at,
            files=[ExternalFileRead(id=f.id, filename=f.filename, size_bytes=f.size_bytes) for f in files]))
    return GovernanceInfo(
        version=s.version or 1, my_tier=t, my_tier_label=approval.TIER_LABELS[t], review_path=s.review_path,
        preview_path=approval.path_for(t, approval.has_lead(db)) if s.status == STATUS_DRAFT and t else None,
        requested_by=_person(db, s.review_requested_by_id), requested_at=s.review_requested_at,
        reviewed_by=_person(db, s.reviewed_by_id), reviewed_at=s.reviewed_at,
        confirmed_by=_person(db, s.confirmed_by_id),
        pending_reopen=_reopen_read(db, pend) if pend else None, external_approvals=ext_reads,
        can=GovernanceCan(**{k: getattr(c, k) for k in GovernanceCan.model_fields}),
    )


def _history(db: Session, s: Scoping, frm: str, to: str, reason: str | None, actor_id: UUID,
             snapshot: dict | None = None) -> None:
    db.add(ScopingStatusHistory(scoping_id=s.id, from_status=frm, to_status=to, reason=reason, actor_id=actor_id,
                                badge_count=svc.badge_count(db, s.id), snapshot=snapshot))


def _confirm(db: Session, s: Scoping, by: UUID, reason: str) -> dict:
    """확정 처리 — 스냅샷·확정 기록. 상태 이력은 호출자가 남긴다."""
    snap = svc.snapshot(db, s)
    s.confirmed_snapshot, s.confirmed_at, s.confirmed_by_id = snap, datetime.now(UTC), by
    s.confirm_reason, s.confirm_badge_count = reason, svc.badge_count(db, s.id)
    s.status = STATUS_CONFIRMED
    return snap


def _clear_review(s: Scoping) -> None:
    s.review_requested_by_id = s.review_requested_at = s.review_path = None
    s.reviewed_by_id = s.reviewed_at = None


def _reopen(db: Session, s: Scoping, by: UUID, reason: str) -> None:
    """재오픈 실행 — 작성 중 + 버전 +1. 확정 스냅샷은 상태 이력·거버넌스 이력에 이미 있다."""
    _history(db, s, s.status, STATUS_DRAFT, reason, by)
    s.confirmed_snapshot = s.confirmed_at = s.confirmed_by_id = None
    s.confirm_reason = s.confirm_badge_count = None
    _clear_review(s)
    s.status = STATUS_DRAFT
    s.version = (s.version or 1) + 1


@router.post("/{scoping_id}/transition", response_model=ScopingDetail)
def transition(scoping_id: UUID, req: TransitionRequest, user: User = Depends(require_icfr_staff),
               db: Session = Depends(get_db)) -> ScopingDetail:
    """상태 전이 (ADR-0034 §2.2 + **ADR-0038 검토·승인 거버넌스**).

    - 작성 중 → 검토 중(**검토 요청**): 설정근거 필수. 요청자 단계로 **승인 경로**를 정해 저장한다
      (일반 → 책임 검토 → 마스터 승인 / 책임 → 마스터 승인 / 마스터 → 대표이사·이사회 외부 승인).
    - 검토 중 → 작성 중: 요청자 **회수** 또는 검토·승인자 **반려**(사유 필수).
    - 검토 중 → 확정(**승인**): 마스터관리자, **요청자·검토자 본인 불가**(자기 승인 금지), 확정 사유 필수.
      외부 승인 경로는 여기서 확정하지 않는다 — `POST /external-approval` 로 증빙과 함께 기록.
    - 확정 → 작성 중: **직접 불가** — `POST /reopen-requests` → 승인.
    """
    s = _get(db, scoping_id)
    if req.to_status not in TRANSITIONS.get(s.status, set()):
        raise HTTPException(status_code=409, detail=(
            f"'{STATUS_LABELS[s.status]}' 에서 '{STATUS_LABELS[req.to_status]}' 로 바꿀 수 없습니다"))
    reason = (req.reason or "").strip() or None
    c = approval.can(db, s, user.id)
    frm = s.status

    if s.status == STATUS_DRAFT and req.to_status == STATUS_REVIEW:
        if not (s.rationale or "").strip():
            raise HTTPException(status_code=409, detail="중요성 설정근거를 먼저 입력하세요 — 감사에서 묻는다")
        t = approval.user_tier(db, user.id)
        s.review_path = approval.path_for(t, approval.has_lead(db))
        s.review_requested_by_id, s.review_requested_at = user.id, datetime.now(UTC)
        s.reviewed_by_id = s.reviewed_at = None
        s.status = STATUS_REVIEW
        _history(db, s, frm, STATUS_REVIEW, reason, user.id)
        glog.record(db, s.id, EV_SUBMIT, version=s.version, reason=reason, after={"승인 경로": s.review_path})
    elif s.status == STATUS_REVIEW and req.to_status == STATUS_DRAFT:
        if c.withdraw:
            action = EV_WITHDRAW
        elif c.review_return:
            if not reason:
                raise HTTPException(status_code=422, detail="반려 사유가 필요합니다")
            action = EV_REVIEW_RETURN
        else:
            raise HTTPException(status_code=403, detail="요청자(회수) 또는 검토·승인 권한자(반려)만 되돌릴 수 있습니다")
        _clear_review(s)
        s.status = STATUS_DRAFT
        _history(db, s, frm, STATUS_DRAFT, reason, user.id)
        glog.record(db, s.id, action, version=s.version, reason=reason)
    elif s.status == STATUS_REVIEW and req.to_status == STATUS_CONFIRMED:
        if not c.approve:
            raise HTTPException(status_code=409 if approval.user_tier(db, user.id) == 3 else 403,
                                detail=c.why.get("approve", "승인할 수 없습니다"))
        if not reason:
            raise HTTPException(status_code=422, detail="확정 사유가 필요합니다")
        snap = _confirm(db, s, user.id, reason)
        _history(db, s, frm, STATUS_CONFIRMED, reason, user.id, snapshot=snap)
        glog.record(db, s.id, EV_APPROVE, version=s.version, reason=reason)
    else:   # 확정 → 작성 중
        raise HTTPException(status_code=409, detail="확정된 스코핑은 재오픈 요청 후 승인을 받아야 작성 중으로 돌아갑니다")
    db.commit()
    return _detail(db, s, user.id)


@router.post("/{scoping_id}/review", response_model=ScopingDetail)
def review(scoping_id: UUID, req: ReviewRequest, user: User = Depends(require_icfr_staff),
           db: Session = Depends(get_db)) -> ScopingDetail:
    """책임관리자 검토 — 일반관리자가 요청한 건만(경로 `lead_then_master`). 요청자 본인 불가."""
    s = _get(db, scoping_id)
    c = approval.can(db, s, user.id)
    if s.status != STATUS_REVIEW or s.review_path != PATH_LEAD_THEN_MASTER or s.reviewed_by_id is not None:
        raise HTTPException(status_code=409, detail="책임관리자 검토 단계가 아닙니다")
    if not c.review:
        raise HTTPException(status_code=409, detail=c.why.get("review", "검토할 수 없습니다"))
    reason = (req.reason or "").strip() or None
    if req.action == "done":
        s.reviewed_by_id, s.reviewed_at = user.id, datetime.now(UTC)
        glog.record(db, s.id, EV_REVIEW_DONE, version=s.version, reason=reason)
    else:
        if not reason:
            raise HTTPException(status_code=422, detail="반려 사유가 필요합니다")
        frm = s.status
        _clear_review(s)
        s.status = STATUS_DRAFT
        _history(db, s, frm, STATUS_DRAFT, reason, user.id)
        glog.record(db, s.id, EV_REVIEW_RETURN, version=s.version, reason=reason)
    db.commit()
    return _detail(db, s, user.id)


@router.post("/{scoping_id}/reopen-requests", response_model=ScopingDetail, status_code=status.HTTP_201_CREATED)
def request_reopen(scoping_id: UUID, body: ReopenCreate, user: User = Depends(require_icfr_staff),
                   db: Session = Depends(get_db)) -> ScopingDetail:
    """확정 스코핑 재오픈 요청 — 사유 필수, 미결 요청은 하나만."""
    s = _get(db, scoping_id)
    if s.status != STATUS_CONFIRMED:
        raise HTTPException(status_code=409, detail="확정된 스코핑만 재오픈을 요청할 수 있습니다")
    if approval.pending_reopen(db, s.id) is not None:
        raise HTTPException(status_code=409, detail="이미 결정 대기 중인 재오픈 요청이 있습니다")
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="재오픈 사유가 필요합니다")
    db.add(ReopenRequest(entity_type=ENTITY_SCOPING, entity_id=s.id, requested_by_id=user.id,
                         requested_tier=approval.user_tier(db, user.id), reason=reason))
    glog.record(db, s.id, EV_REOPEN_REQUEST, version=s.version, reason=reason)
    db.commit()
    return _detail(db, s, user.id)


@router.post("/{scoping_id}/reopen-requests/{request_id}/decide", response_model=ScopingDetail)
def decide_reopen(scoping_id: UUID, request_id: UUID, body: ReopenDecision, user: User = Depends(require_icfr_staff),
                  db: Session = Depends(get_db)) -> ScopingDetail:
    """재오픈 승인·거절 — 마스터관리자, **요청자 본인 불가**. 마스터의 요청은 외부 승인 증빙으로만(409)."""
    s = _get(db, scoping_id)
    r = approval.pending_reopen(db, s.id)
    if r is None or r.id != request_id:
        raise HTTPException(status_code=404, detail="결정 대기 중인 재오픈 요청이 없습니다")
    c = approval.can(db, s, user.id)
    if not c.reopen_decide:
        raise HTTPException(status_code=409 if approval.user_tier(db, user.id) == 3 else 403,
                            detail=c.why.get("reopen", "재오픈을 결정할 수 없습니다"))
    reason = (body.reason or "").strip() or None
    if not body.approve and not reason:
        raise HTTPException(status_code=422, detail="거절 사유가 필요합니다")
    r.status = REOPEN_APPROVED if body.approve else REOPEN_REJECTED
    r.decided_by_id, r.decided_at, r.decision_reason = user.id, datetime.now(UTC), reason
    glog.record(db, s.id, EV_REOPEN_APPROVE if body.approve else EV_REOPEN_REJECT, version=s.version,
                reason=reason, after={"요청 사유": r.reason})
    if body.approve:
        _reopen(db, s, user.id, f"재오픈 승인 — {r.reason}")
    db.commit()
    return _detail(db, s, user.id)


ALLOWED_EVIDENCE = {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/tiff"}
MAX_EVIDENCE_BYTES = 20 * 1024 * 1024


@router.post("/{scoping_id}/external-approval", response_model=ScopingDetail)
def external_approval(scoping_id: UUID, purpose: str = Form(...), approver_body: str = Form(...),
                      approved_on: str = Form(...), reference: str | None = Form(default=None),
                      files: list[UploadFile] = File(...), user: User = Depends(require_icfr_staff),
                      db: Session = Depends(get_db)) -> ScopingDetail:
    """대표이사·이사회 **외부 승인 기록**(ADR-0038 §2.2.1) — 마스터 작성분의 확정, 마스터 요청 재오픈의 승인.

    승인 행위가 아니라 이미 일어난 외부 승인의 기록이라 일반관리자 이상 누구나 등록한다. **증빙 파일 필수**
    (PDF·이미지, 각 20MB). 등록자·시각·파일이 이력에 남는다.
    """
    from datetime import date as _date
    s = _get(db, scoping_id)
    if purpose not in ("approve", "reopen"):
        raise HTTPException(status_code=422, detail="purpose 는 approve 또는 reopen 입니다")
    if approver_body not in EXTERNAL_BODIES:
        raise HTTPException(status_code=422, detail="승인 기관은 대표이사(ceo) 또는 이사회(board)입니다")
    try:
        on = _date.fromisoformat(approved_on)
    except ValueError:
        raise HTTPException(status_code=422, detail="승인일 형식이 올바르지 않습니다(YYYY-MM-DD)") from None
    real = [f for f in files if f.filename]
    if not real:
        raise HTTPException(status_code=422, detail="외부 승인 증빙(의사록·결재 문서 스캔)을 첨부하세요")
    c = approval.can(db, s, user.id)
    pend = approval.pending_reopen(db, s.id)
    if purpose == "approve" and not (s.status == STATUS_REVIEW and s.review_path == PATH_EXTERNAL and c.external_approve):
        raise HTTPException(status_code=409, detail="외부 승인 대상(마스터관리자가 검토 요청한 건)이 아닙니다")
    if purpose == "reopen" and not (pend is not None and c.reopen_external):
        raise HTTPException(status_code=409, detail="외부 승인이 필요한 재오픈 요청(마스터관리자 요청)이 없습니다")

    ea = ExternalApproval(entity_type=ENTITY_SCOPING, entity_id=s.id, purpose=purpose,
                          reopen_request_id=pend.id if purpose == "reopen" else None, approver_body=approver_body,
                          approved_on=on, reference=(reference or "").strip() or None, recorded_by_id=user.id)
    db.add(ea)
    db.flush()
    names = []
    for f in real:
        data = f.file.read(MAX_EVIDENCE_BYTES + 1)
        if len(data) > MAX_EVIDENCE_BYTES:
            raise HTTPException(status_code=413, detail=f"{f.filename}: 20MB 를 넘습니다")
        mime = f.content_type or "application/octet-stream"
        if mime not in ALLOWED_EVIDENCE:
            raise HTTPException(status_code=415, detail=f"{f.filename}: PDF·이미지 파일만 첨부할 수 있습니다")
        gf = GovernanceFile(external_approval_id=ea.id, filename=f.filename[:300], mime_type=mime,
                            size_bytes=len(data), minio_key="pending")
        db.add(gf)
        db.flush()
        gf.minio_key = build_governance_key(ENTITY_SCOPING, s.id, gf.id)
        upload_object(gf.minio_key, data, mime)
        names.append(f.filename)
    label = f"{EXTERNAL_BODIES[approver_body]} 승인 {on.isoformat()}" + (f" · {ea.reference}" if ea.reference else "")
    glog.record(db, s.id, EV_EXTERNAL_APPROVE, version=s.version, reason=label,
                after={"목적": "확정" if purpose == "approve" else "재오픈", "증빙": names})
    if purpose == "approve":
        frm = s.status
        snap = _confirm(db, s, user.id, label)
        _history(db, s, frm, STATUS_CONFIRMED, label, user.id, snapshot=snap)
    else:
        pend.status, pend.decided_by_id, pend.decided_at = REOPEN_APPROVED, user.id, datetime.now(UTC)
        pend.decision_reason = label
        _reopen(db, s, user.id, f"재오픈 외부 승인 — {pend.reason}")
    db.commit()
    return _detail(db, s, user.id)


@router.get("/{scoping_id}/events", response_model=list[GovernanceEventRead])
def list_events(scoping_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> list[GovernanceEventRead]:
    """변경·검토·승인 이력(최신순) — 지울 수 없는 기록(ADR-0038 §2.4). 조회는 전 역할."""
    s = _get(db, scoping_id)
    rows = db.query(GovernanceEvent).filter(GovernanceEvent.entity_type == ENTITY_SCOPING,
                                            GovernanceEvent.entity_id == s.id).order_by(
        GovernanceEvent.id.desc()).limit(2000).all()   # UUIDv7 = 기록 순서(같은 요청의 여러 건도 순서 보존)
    cache: dict = {}

    def person(uid):
        if uid not in cache:
            cache[uid] = _person(db, uid)
        return cache[uid]
    return [GovernanceEventRead(id=e.id, action=e.action, target=e.target, actor=person(e.actor_id), reason=e.reason,
                                before=e.before, after=e.after, version=e.version, created_at=e.created_at) for e in rows]

