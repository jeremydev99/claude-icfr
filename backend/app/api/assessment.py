"""평가 회차·활동·승인 API — 3-2, ADR-0032 §2.1~2.7.

ADR-0020 준수 — 서비스 클래스 없이 직접 함수와 명시적 분기만.
ADR-0025 준수 — 수동 tenant 필터를 걸지 않는다.

**권한 검사는 통제 단위다.** "이 사람이 평가자인가"가 아니라 "이 통제에서 이 사람이
평가자인가"를 본다(ADR-0031 §2.2). 3-1 의 `role_resolver` 를 그대로 쓰며 판정 로직을
복제하지 않는다.
"""
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api import _approval_view as av
from app.core import governance_log as glog
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import (
    can_view_all,
    is_assessor,
    require_icfr_manager,
    require_icfr_staff,
    require_write,
    tenant_roles,
)
from app.models.assessment import (
    ACTIVITY_DESIGN,
    ACTIVITY_DRAFT,
    ACTIVITY_RULES,
    ACTIVITY_SUBMITTED,
    ACTIVITY_TEST,
    APPROVAL_ASSESSOR,
    APPROVAL_DEPT,
    CYCLE_APPROVED,
    CYCLE_CLOSED,
    CYCLE_DESIGN,
    CYCLE_OPEN,
    CYCLE_OPERATION,
    SAMPLE_ACTIVITY_KINDS,
    ActivityApproval,
    ActivitySample,
    AssessmentActivity,
    AssessmentCycle,
    CycleTarget,
)
from app.models.evidence import LINK_TARGET_SAMPLE, EvidenceFile, EvidenceLink
from app.models.governance import (
    ENTITY_ASSESSMENT_CYCLE,
    EV_APPROVE,
    EV_CYCLE_CLOSE,
    EV_EXTERNAL_APPROVE,
    ExternalApproval,
    GovernanceFile,
)
from app.models.role_assignment import (
    ROLE_ASSESSOR,
    ROLE_CONTROL_OWNER,
    ROLE_DEPT_APPROVER,
)
from app.models.user import User
from app.schemas.assessment import (
    ActivityCreate,
    ActivityRead,
    ActivityUpdate,
    ApprovalCreate,
    ApprovalRead,
    CycleCloseRequest,
    CycleCloseResult,
    CycleCreate,
    CycleGovernance,
    CycleRead,
    CycleTargetRead,
    CycleUpdate,
    IncompleteControl,
    PeriodSuggestion,
    SampleEvidence,
    SampleRead,
    SampleWrite,
    WorklistRow,
)
from app.schemas.scoping import ExternalApprovalRead, ExternalFileRead, GovernanceEventRead
from app.services import approval_flow, sampling
from app.services import cycle_approval as cap
from app.services.assessment_period import (
    current_fiscal_year,
    current_period_index,
    fiscal_year_start_month,
    suggest_period,
)
from app.services.control_resolver import resolve_controls, resolve_processes
from app.services.role_resolver import (
    _assignments_by_target,
    is_dept_approval_skipped,
    resolve_control_process_id,
    resolve_roles_for_control,
)

router = APIRouter(prefix="/api/assessment", tags=["assessment"])

# 회차 종류별 "완료" 판정에 필요한 활동 — 마감 시 미완 판정 기준 (§2.5)
_REQUIRED_ACTIVITIES = {
    CYCLE_DESIGN: ("design", "design_assessment"),
    CYCLE_OPERATION: ("test", "operation_assessment"),
}


def _names(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    return {u.id: u.display_name for u in db.query(User).filter(User.id.in_(ids)).all()}


def _get_cycle_or_404(db: Session, cycle_id: UUID) -> AssessmentCycle:
    obj = db.query(AssessmentCycle).filter(
        AssessmentCycle.id == cycle_id,
        AssessmentCycle.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="AssessmentCycle not found")
    return obj


def _to_cycle_read(db: Session, obj: AssessmentCycle, with_count: bool = True) -> CycleRead:
    row = CycleRead.model_validate(obj)
    names = _names(db, {i for i in (obj.closed_by_id, obj.approved_by_id) if i})
    row.closed_by_name = names.get(obj.closed_by_id) if obj.closed_by_id else None
    row.approved_by_name = names.get(obj.approved_by_id) if obj.approved_by_id else None
    if with_count:
        row.target_count = db.query(CycleTarget).filter(
            CycleTarget.cycle_id == obj.id,
            CycleTarget.is_deleted == False,  # noqa: E712
        ).count()
    return row


def _assert_open(cycle: AssessmentCycle) -> None:
    """마감·최종승인된 회차는 더 이상 기록을 받지 않는다.

    마감 후에도 쓸 수 있으면 "그때 무엇이 완료됐는가"가 사후에 달라진다 —
    미완 사유를 남기고 마감한 의미가 사라진다.
    """
    if cycle.status != CYCLE_OPEN:
        raise HTTPException(
            status_code=409,
            detail=f"마감된 회차에는 기록할 수 없습니다 (상태: {cycle.status})",
        )


def _dept_approval_enabled(db: Session) -> bool:
    """정책 토글. 미설정이면 켜짐이 기본이다(ADR-0031 §2.6 — 부서승인은 선택 단계). 판정은 공용 함수 하나."""
    from app.services.approval import dept_approval_enabled
    return dept_approval_enabled(db)


def _role_holder(db: Session, control_id: UUID, role_name: str) -> UUID | None:
    """이 **통제에서** 해당 역할을 가진 사람. 통제 단위 판정(ADR-0031 §2.2)."""
    process_id = resolve_control_process_id(db, control_id)
    resolved = resolve_roles_for_control(db, control_id, process_id)
    return next((r["user_id"] for r in resolved if r["role_name"] == role_name), None)


# ── 회차 ──────────────────────────────────────────────────

@router.get("/period-suggestion", response_model=PeriodSuggestion)
def get_period_suggestion(frequency: str, period_index: int | None = None,
                          fiscal_year: int | None = None, user: CurrentUser = None,
                          db: Session = Depends(get_db)) -> PeriodSuggestion:
    """기간 제안값. 회차 생성 화면이 미리 받아 채워 넣는다 — **강제가 아니다**(§2.2)."""
    start_month = fiscal_year_start_month(db)
    today = date.today()
    fy = fiscal_year if fiscal_year else current_fiscal_year(today, start_month)
    idx = period_index if period_index else current_period_index(frequency, today, start_month, fy)
    ps, pe = suggest_period(frequency, start_month, fy, idx)
    return PeriodSuggestion(period_start=ps, period_end=pe, fiscal_year=fy,
                            period_index=idx, fiscal_year_start_month=start_month)


@router.get("/cycles")
def list_cycles(kind: str | None = None, status_filter: str | None = None,
                skip: int = 0, limit: int = 100, user: CurrentUser = None,
                db: Session = Depends(get_db)) -> dict:
    q = db.query(AssessmentCycle).filter(AssessmentCycle.is_deleted == False)  # noqa: E712
    if kind:
        q = q.filter(AssessmentCycle.kind == kind)
    if status_filter:
        q = q.filter(AssessmentCycle.status == status_filter)
    total = q.count()
    items = q.order_by(AssessmentCycle.period_start.desc()).offset(skip).limit(limit).all()
    return {"items": [_to_cycle_read(db, c) for c in items],
            "total": total, "skip": skip, "limit": limit}


@router.post("/cycles", status_code=status.HTTP_201_CREATED, response_model=CycleRead)
def create_cycle(body: CycleCreate, user: User = Depends(require_write),
                 db: Session = Depends(get_db)) -> CycleRead:
    """회차 생성 — **`assessor` 만 만들 수 있다**(ADR-0032 §2.1).

    통제책임자는 만들 수 없다. 평가 일정을 실무부서가 정하면 평가자 독립성이 무너진다.
    여기서 `assessor` 판정은 **어느 통제에서든 평가자로 배정된 적이 있는가**로 본다 —
    회차는 특정 통제에 속하지 않으므로 통제 단위 판정을 쓸 수 없다.

    **대상 통제는 이 시점에 스냅샷으로 고정한다.** 주기가 나중에 바뀌어도 과거 회차
    대상은 달라지지 않는다(모델 docstring 참조).
    """
    _assert_can_create_cycle(db, user)

    start_month = fiscal_year_start_month(db)
    today = date.today()
    fy = body.fiscal_year or current_fiscal_year(today, start_month)
    idx = body.period_index or current_period_index(body.frequency, today, start_month, fy)
    default_start, default_end = suggest_period(body.frequency, start_month, fy, idx)

    period_start = body.period_start or default_start
    period_end = body.period_end or default_end
    if period_end < period_start:
        raise HTTPException(status_code=409, detail="평가 종료일이 시작일보다 빠릅니다")

    dup = db.query(AssessmentCycle).filter(
        AssessmentCycle.kind == body.kind,
        AssessmentCycle.name == body.name,
        AssessmentCycle.is_deleted == False,  # noqa: E712
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail=f"회차명 '{body.name}' 은 이미 사용 중입니다")

    cycle = AssessmentCycle(
        kind=body.kind, frequency=body.frequency, name=body.name,
        period_start=period_start, period_end=period_end, due_date=body.due_date,
        status=CYCLE_OPEN,
    )
    db.add(cycle)
    db.flush()

    # 대상 스냅샷 — 회차 주기와 일치하는 **유효 평가주기**를 가진 통제
    for c in resolve_controls(db):
        if c.get("assessment_frequency") == body.frequency:
            db.add(CycleTarget(cycle_id=cycle.id, control_id=c["id"],
                               control_code=c.get("code")))
    db.commit()
    db.refresh(cycle)
    return _to_cycle_read(db, cycle)


def _assert_can_create_cycle(db: Session, user: User) -> None:
    """회차 생성 자격 — 어느 통제에서든 `assessor` 로 배정돼 있어야 한다(판정은 core/permissions)."""
    if not is_assessor(db, user.id):
        raise HTTPException(
            status_code=403,
            detail="평가 회차는 평가자(전담부서)만 생성할 수 있습니다",
        )


@router.get("/cycles/{cycle_id}", response_model=CycleRead)
def get_cycle(cycle_id: UUID, user: CurrentUser = None,
              db: Session = Depends(get_db)) -> CycleRead:
    return _to_cycle_read(db, _get_cycle_or_404(db, cycle_id))


@router.get("/cycles/{cycle_id}/export")
def export_cycle(cycle_id: UUID, mine: bool = False, user: CurrentUser = None, db: Session = Depends(get_db)):
    """회차 엑셀 내보내기(13.9-122) — 통제 1건 = 시트 1장, 증빙 이미지(PDF 는 페이지 이미지)를 붙인다.
    `mine=true` 면 내가 통제책임자인 통제만. 규칙은 `services/assessment_export`."""
    from urllib.parse import quote

    from fastapi.responses import Response

    from app.services import assessment_export as ax

    cycle = _get_cycle_or_404(db, cycle_id)
    try:
        data, n = ax.build(db, cycle, owner_id=user.id if mine else None)
    except ax.ExportError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    fname = f"{cycle.name}{'_내담당' if mine else ''}_운영평가_{n}건.xlsx"
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})


@router.patch("/cycles/{cycle_id}", response_model=CycleRead)
def update_cycle(cycle_id: UUID, body: CycleUpdate, user: User = Depends(require_write),
                 db: Session = Depends(get_db)) -> CycleRead:
    cycle = _get_cycle_or_404(db, cycle_id)
    _assert_open(cycle)
    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(cycle, f, v)
    if cycle.period_end < cycle.period_start:
        raise HTTPException(status_code=409, detail="평가 종료일이 시작일보다 빠릅니다")
    db.commit()
    db.refresh(cycle)
    return _to_cycle_read(db, cycle)


@router.get("/cycles/{cycle_id}/targets")
def list_cycle_targets(cycle_id: UUID, skip: int = 0, limit: int = 500,
                       user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    """회차 대상 스냅샷. **생성 시점의 사실**이며 이후 주기가 바뀌어도 불변이다."""
    _get_cycle_or_404(db, cycle_id)
    q = db.query(CycleTarget).filter(
        CycleTarget.cycle_id == cycle_id,
        CycleTarget.is_deleted == False,  # noqa: E712
    )
    total = q.count()
    items = q.order_by(CycleTarget.control_code).offset(skip).limit(limit).all()
    return {"items": [CycleTargetRead.model_validate(t) for t in items],
            "total": total, "skip": skip, "limit": limit}


# ── 활동 기록 (§2.3) ──────────────────────────────────────

def _to_activity_read(db: Session, obj: AssessmentActivity,
                      approvals: list[ActivityApproval] | None = None) -> ActivityRead:
    row = ActivityRead.model_validate(obj)
    row.performed_by_name = _names(db, {obj.performed_by_id}).get(obj.performed_by_id)
    if approvals is None:
        approvals = db.query(ActivityApproval).filter(
            ActivityApproval.activity_id == obj.id,
            ActivityApproval.is_deleted == False,  # noqa: E712
        ).all()
    ap_names = _names(db, {a.approved_by_id for a in approvals})
    rows = []
    for a in approvals:
        r = ApprovalRead.model_validate(a)
        r.approved_by_name = ap_names.get(a.approved_by_id)
        rows.append(r)
    row.approvals = rows
    if obj.activity_kind in SAMPLE_ACTIVITY_KINDS:
        row.samples = _sample_reads(db, [obj.id]).get(obj.id, [])
    return row


@router.get("/cycles/{cycle_id}/activities")
def list_activities(cycle_id: UUID, control_id: UUID | None = None,
                    skip: int = 0, limit: int = 200, user: CurrentUser = None,
                    db: Session = Depends(get_db)) -> dict:
    """활동 기록. 수행자·수행시각이 함께 나온다 — 감사추적의 실체다(§2.8)."""
    _get_cycle_or_404(db, cycle_id)
    q = db.query(AssessmentActivity).filter(
        AssessmentActivity.cycle_id == cycle_id,
        AssessmentActivity.is_deleted == False,  # noqa: E712
    )
    if control_id:
        q = q.filter(AssessmentActivity.control_id == control_id)
    total = q.count()
    items = q.order_by(AssessmentActivity.performed_at).offset(skip).limit(limit).all()
    return {"items": [_to_activity_read(db, a) for a in items],
            "total": total, "skip": skip, "limit": limit}


@router.post("/cycles/{cycle_id}/activities", status_code=status.HTTP_201_CREATED,
             response_model=ActivityRead)
def create_activity(cycle_id: UUID, body: ActivityCreate, user: User = Depends(require_write),
                    db: Session = Depends(get_db)) -> ActivityRead:
    """활동 기록 — **권한은 통제 단위로 본다**(ADR-0031 §2.2).

    "이 사람이 평가자인가"가 아니라 "이 통제에서 이 사람이 평가자인가"다.
    통제 A 의 평가자가 통제 B 에서 평가를 남길 수 없다.
    """
    cycle = _get_cycle_or_404(db, cycle_id)
    _assert_open(cycle)

    required_role, required_kind = ACTIVITY_RULES[body.activity_kind]
    if cycle.kind != required_kind:
        raise HTTPException(
            status_code=409,
            detail=f"'{body.activity_kind}' 활동은 {required_kind} 회차에만 기록할 수 있습니다",
        )

    target = db.query(CycleTarget).filter(
        CycleTarget.cycle_id == cycle_id,
        CycleTarget.control_id == body.control_id,
        CycleTarget.is_deleted == False,  # noqa: E712
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="이 회차의 대상 통제가 아닙니다")

    if _role_holder(db, body.control_id, required_role) != user.id:
        raise HTTPException(
            status_code=403,
            detail=f"이 통제의 {required_role} 만 '{body.activity_kind}' 을 기록할 수 있습니다",
        )

    now = datetime.now(UTC)
    if body.activity_kind not in SAMPLE_ACTIVITY_KINDS:
        obj = AssessmentActivity(
            cycle_id=cycle_id, control_id=body.control_id, activity_kind=body.activity_kind,
            result=body.result, note=body.note, performed_by_id=user.id, performed_at=now,
            status=ACTIVITY_SUBMITTED, submitted_at=now,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return _to_activity_read(db, obj, approvals=[])

    # 샘플 활동(설계·테스트) — 작성 중으로 시작, 필요 수만큼 빈 샘플 줄을 만든다(§2.10)
    if _draft_of(db, cycle_id, body.control_id, body.activity_kind) is not None:
        raise HTTPException(status_code=409, detail="이 통제에 작성 중인 기록이 이미 있습니다 — 그 기록을 이어서 작성하세요")
    control = _control(db, body.control_id)
    obj = AssessmentActivity(
        cycle_id=cycle_id, control_id=body.control_id, activity_kind=body.activity_kind,
        result=body.result, note=body.note, performed_by_id=user.id, performed_at=now,
        status=ACTIVITY_DRAFT,
        test_methods=body.test_methods or (control or {}).get("test_methods"),
        population=body.population or (control or {}).get("population"),
        procedure=body.procedure or (control or {}).get("test_procedure"),
    )
    db.add(obj)
    db.flush()
    for i in range(1, sampling.required_samples(cycle.kind, control) + 1):
        db.add(ActivitySample(activity_id=obj.id, seq=i))
    db.commit()
    db.refresh(obj)
    return _to_activity_read(db, obj, approvals=[])


# ── 승인 (§2.4) ───────────────────────────────────────────

@router.post("/activities/{activity_id}/approvals", status_code=status.HTTP_201_CREATED,
             response_model=ApprovalRead)
def approve_activity(activity_id: UUID, body: ApprovalCreate,
                     user: User = Depends(require_write),
                     db: Session = Depends(get_db)) -> ApprovalRead:
    """부서승인 / 평가자 승인. **최종승인은 여기가 아니다** — 회차 전체 대상이다(§2.6).

    부서승인이 건너뛰어지는 경로는 둘이며 구분해 처리한다.
    - 정책 토글 `dept_approval_enabled` 가 false → **전체** 스킵
    - 해당 통제가 `dept_approval_skipped` → **그 통제만** 스킵
      (통제책임자가 곧 부서 책임자라 검토 단계가 없다, ADR-0031 §2.4 정정)

    둘 다 "승인할 것이 없는" 상태이므로 승인 요청 자체를 409 로 거부한다 —
    없는 단계에 승인 기록을 만들면 그 회차가 무엇을 거쳤는지 왜곡된다.
    """
    activity = db.query(AssessmentActivity).filter(
        AssessmentActivity.id == activity_id,
        AssessmentActivity.is_deleted == False,  # noqa: E712
    ).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="AssessmentActivity not found")
    _assert_open(_get_cycle_or_404(db, activity.cycle_id))

    if body.stage == APPROVAL_DEPT:
        if not _dept_approval_enabled(db):
            raise HTTPException(
                status_code=409,
                detail="부서승인 단계가 비활성화되어 있습니다 (정책: dept_approval_enabled)",
            )
        process_id = resolve_control_process_id(db, activity.control_id)
        if is_dept_approval_skipped(
            resolve_roles_for_control(db, activity.control_id, process_id)
        ):
            raise HTTPException(
                status_code=409,
                detail="이 통제는 통제책임자가 부서 책임자를 겸해 부서승인 단계가 없습니다",
            )
        required_role = ROLE_DEPT_APPROVER
    else:
        required_role = ROLE_ASSESSOR

    if _role_holder(db, activity.control_id, required_role) != user.id:
        raise HTTPException(
            status_code=403, detail=f"이 통제의 {required_role} 만 승인할 수 있습니다")

    if activity.status != ACTIVITY_SUBMITTED:
        raise HTTPException(status_code=409, detail="제출되지 않은 기록은 승인할 수 없습니다")

    # 직무분리(2026-10-16, 조사 1) — 역할 보유만 보면 배정이 바뀐 뒤 작성자가 자기 기록을 승인할 수 있다.
    # 판정은 **기록 기준**: 작성자 본인 · 같은 기록의 다른 단계를 이미 승인한 사람은 승인하지 못한다
    prior = {ap.approved_by_id for ap in db.query(ActivityApproval).filter(
        ActivityApproval.activity_id == activity_id,
        ActivityApproval.is_deleted == False).all()}  # noqa: E712
    sod = _sod_block(activity.performed_by_id, prior, user.id)
    if sod:
        raise HTTPException(status_code=403, detail=sod)

    dup = db.query(ActivityApproval).filter(
        ActivityApproval.activity_id == activity_id,
        ActivityApproval.stage == body.stage,
        ActivityApproval.is_deleted == False,  # noqa: E712
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="이미 승인된 단계입니다")

    obj = ActivityApproval(
        activity_id=activity_id, stage=body.stage, approved_by_id=user.id,
        approved_at=datetime.now(UTC), note=body.note,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    row = ApprovalRead.model_validate(obj)
    row.approved_by_name = _names(db, {user.id}).get(user.id)
    return row


def _sod_block(performed_by: UUID, prior_approvers: set[UUID], user_id: UUID) -> str | None:
    """직무분리로 이 사람이 이 기록을 승인할 수 없으면 그 이유. 승인 API 와 worklist 가 같이 쓴다."""
    if performed_by == user_id:
        return "본인이 작성한 테스트는 승인할 수 없습니다(직무분리)"
    if user_id in prior_approvers:
        return "같은 테스트의 다른 단계를 이미 승인했습니다(직무분리)"
    return None


# ── 마감·최종승인 (§2.5·§2.6) ─────────────────────────────

def _incomplete_controls(db: Session, cycle: AssessmentCycle) -> list[IncompleteControl]:
    """미완 통제 — 회차 종류가 요구하는 활동이 없는 대상.

    **무엇이 없어서 미완인지 함께 낸다.** "3건 미완" 만으로는 담당자가 다음 행동을
    정할 수 없다.
    """
    targets = db.query(CycleTarget).filter(
        CycleTarget.cycle_id == cycle.id,
        CycleTarget.is_deleted == False,  # noqa: E712
    ).all()
    done: dict[UUID, set[str]] = {}
    for a in db.query(AssessmentActivity).filter(
        AssessmentActivity.cycle_id == cycle.id,
        AssessmentActivity.status == ACTIVITY_SUBMITTED,   # 작성 중은 완료가 아니다(§2.10)
        AssessmentActivity.is_deleted == False,  # noqa: E712
    ).all():
        done.setdefault(a.control_id, set()).add(a.activity_kind)

    required = _REQUIRED_ACTIVITIES[cycle.kind]
    result = []
    for t in targets:
        missing = [k for k in required if k not in done.get(t.control_id, set())]
        if missing:
            result.append(IncompleteControl(control_id=t.control_id,
                                            control_code=t.control_code, missing=missing))
    return result


@router.get("/cycles/{cycle_id}/incomplete")
def get_incomplete(cycle_id: UUID, user: CurrentUser = None,
                   db: Session = Depends(get_db)) -> dict:
    """마감 전에 미완 목록을 미리 본다 — 409 를 받고서야 알게 되지 않도록."""
    cycle = _get_cycle_or_404(db, cycle_id)
    items = _incomplete_controls(db, cycle)
    return {"items": items, "total": len(items), "skip": 0, "limit": len(items)}


@router.post("/cycles/{cycle_id}/close", response_model=CycleCloseResult)
def close_cycle(cycle_id: UUID, body: CycleCloseRequest, user: User = Depends(require_write),
                db: Session = Depends(get_db)) -> CycleCloseResult:
    """회차 마감 — **미완이 있어도 마감할 수 있되 사유가 필수다**(ADR-0032 §2.5).

    막으면 회차가 영원히 안 닫히고, 조용히 허용하면 무엇이 빠졌는지 남지 않는다.
    사유 없이 시도하면 **미완 목록과 함께** 409 를 돌려준다(3-1 이해상충과 같은 흐름).

    **마감 단위는 회차다**(§2.4). 통제 단위 마감은 두지 않는다.
    """
    cycle = _get_cycle_or_404(db, cycle_id)
    if cycle.status != CYCLE_OPEN:
        raise HTTPException(status_code=409, detail=f"이미 마감된 회차입니다 (상태: {cycle.status})")
    _assert_can_create_cycle(db, user)   # 마감도 전담부서 권한

    incomplete = _incomplete_controls(db, cycle)
    if incomplete and not body.incomplete_reason:
        shown = ", ".join(i.control_code or str(i.control_id) for i in incomplete[:5])
        more = " 외" if len(incomplete) > 5 else ""
        raise HTTPException(
            status_code=409,
            detail=(f"미완 통제 {len(incomplete)}건이 있습니다({shown}{more}). "
                    "사유를 입력해야 마감할 수 있습니다"),
        )

    cycle.status = CYCLE_CLOSED
    cycle.closed_at = datetime.now(UTC)
    cycle.closed_by_id = user.id
    cycle.incomplete_reason = body.incomplete_reason if incomplete else None
    glog.record(db, cycle.id, EV_CYCLE_CLOSE, version=None, reason=cycle.incomplete_reason,
                after={"미완 통제": len(incomplete)}, entity_type=ENTITY_ASSESSMENT_CYCLE)
    db.commit()
    db.refresh(cycle)
    return CycleCloseResult(cycle=_to_cycle_read(db, cycle), incomplete=incomplete)


@router.post("/cycles/{cycle_id}/approve", response_model=CycleRead)
def approve_cycle(cycle_id: UUID, user: User = Depends(require_icfr_manager),
                  db: Session = Depends(get_db)) -> CycleRead:
    """최종승인 — `icfr_manager` 가 **회차 전체**에 대해 한다(ADR-0032 §2.6).

    **마감되지 않은 회차는 승인할 수 없다.** 마감이 "이 회차의 작업은 여기까지"를
    확정하는 절차이므로, 그 전에 승인하면 승인 후에도 내용이 바뀔 수 있다.
    **마감자는 승인할 수 없다**(ADR-0038 2-4, 자기 승인 금지). 마감자 외 마스터가 없으면
    `POST /external-approval` 로 대표이사·이사회 승인 증빙을 등록한다. 재오픈은 없다 — 이후 개선은 새 회차로.
    """
    cycle = _get_cycle_or_404(db, cycle_id)
    if cycle.status == CYCLE_OPEN:
        raise HTTPException(
            status_code=409, detail="마감되지 않은 회차는 최종승인할 수 없습니다")
    if cycle.status == CYCLE_APPROVED:
        raise HTTPException(status_code=409, detail="이미 최종승인된 회차입니다")
    c = cap.can(db, cycle, user.id)
    if not c.approve:
        raise HTTPException(status_code=409, detail=c.why.get("approve", "최종승인할 수 없습니다"))

    cycle.status = CYCLE_APPROVED
    cycle.approved_at = datetime.now(UTC)
    cycle.approved_by_id = user.id
    glog.record(db, cycle.id, EV_APPROVE, version=None, entity_type=ENTITY_ASSESSMENT_CYCLE,
                after={"미확정 미비점": cap.unconfirmed_deficiencies(db, cap.fiscal_year_of(db, cycle))})
    db.commit()
    db.refresh(cycle)
    return _to_cycle_read(db, cycle)


# ── 최종승인 결재 (ADR-0038 2-4) ──────────────────────────

def _cycle_governance(db: Session, cycle: AssessmentCycle, user_id: UUID) -> CycleGovernance:
    c = cap.can(db, cycle, user_id)
    exts = []
    for e in db.query(ExternalApproval).filter(ExternalApproval.entity_type == ENTITY_ASSESSMENT_CYCLE,
                                               ExternalApproval.entity_id == cycle.id,
                                               ExternalApproval.is_deleted == False).all():  # noqa: E712
        files = db.query(GovernanceFile).filter(GovernanceFile.external_approval_id == e.id,
                                                GovernanceFile.is_deleted == False).all()  # noqa: E712
        exts.append(ExternalApprovalRead(
            id=e.id, purpose=e.purpose, approver_body=e.approver_body, approved_on=e.approved_on,
            reference=e.reference, recorded_by=av.person(db, e.recorded_by_id), created_at=e.created_at,
            files=[ExternalFileRead(id=f.id, filename=f.filename, size_bytes=f.size_bytes) for f in files]))
    fy = cap.fiscal_year_of(db, cycle)
    return CycleGovernance(
        cycle=_to_cycle_read(db, cycle), can_approve=c.approve, can_external_approve=c.external_approve, why=c.why,
        incomplete_count=len(_incomplete_controls(db, cycle)) if cycle.status != CYCLE_OPEN else 0,
        fiscal_year=fy, unconfirmed_deficiencies=cap.unconfirmed_deficiencies(db, fy),
        legacy_approved=cap.legacy_approved(db, cycle), external_approvals=exts)


@router.get("/cycles/{cycle_id}/governance", response_model=CycleGovernance)
def get_cycle_governance(cycle_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> CycleGovernance:
    """최종승인 결재 정보 — 승인 가능 여부와 못 하는 이유, 경고(미완·미확정 미비점), 외부 승인 기록."""
    return _cycle_governance(db, _get_cycle_or_404(db, cycle_id), user.id)


@router.post("/cycles/{cycle_id}/external-approval", response_model=CycleGovernance)
def external_approve_cycle(cycle_id: UUID, approver_body: str = Form(...), approved_on: str = Form(...),
                           reference: str | None = Form(default=None), files: list[UploadFile] = File(...),
                           user: User = Depends(require_icfr_staff), db: Session = Depends(get_db)) -> CycleGovernance:
    """마감자 외 마스터관리자가 없을 때 — 대표이사·이사회 **승인 증빙**을 등록해 최종승인한다(ADR-0038 §2.2.1)."""
    cycle = _get_cycle_or_404(db, cycle_id)
    c = cap.can(db, cycle, user.id)
    if not c.external_approve:
        raise HTTPException(status_code=409, detail=(
            "외부 승인 대상이 아닙니다 — " + c.why.get("approve", "마스터관리자가 최종승인합니다")))
    ev = [approval_flow.EvidenceFile(filename=f.filename or "", content_type=f.content_type,
                                     data=f.file.read(approval_flow.MAX_EVIDENCE_BYTES + 1)) for f in files]
    try:
        on, real = approval_flow.check_external("approve", approver_body, approved_on, ev)
        label, names = approval_flow.store_external(db, ENTITY_ASSESSMENT_CYCLE, cycle.id, user.id, purpose="approve",
                                                    approver_body=approver_body, on=on, reference=reference,
                                                    files=real)
    except approval_flow.FlowError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    glog.record(db, cycle.id, EV_EXTERNAL_APPROVE, version=None, reason=label, entity_type=ENTITY_ASSESSMENT_CYCLE,
                after={"목적": "최종승인", "증빙": names})
    cycle.status = CYCLE_APPROVED
    cycle.approved_at = datetime.now(UTC)
    cycle.approved_by_id = None          # 승인자는 회사 밖(대표이사·이사회) — 기록자는 외부 승인 기록에 남는다
    db.commit()
    return _cycle_governance(db, cycle, user.id)


@router.get("/cycles/{cycle_id}/governance-events", response_model=list[GovernanceEventRead])
def list_cycle_events(cycle_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> list[GovernanceEventRead]:
    """마감·최종승인 이력(최신순) — 지울 수 없는 기록."""
    return av.events(db, ENTITY_ASSESSMENT_CYCLE, _get_cycle_or_404(db, cycle_id).id)


# ── 작성·샘플·제출 (ADR-0032 §2.10, 2026-10-15) ────────────
# 설계·테스트 활동은 작성 중(draft)으로 시작한다. 수행자 본인만 고치고, 필요 샘플을 다 채워야 제출된다.
# 제출 후에는 고칠 수 없다 — 다시 하려면 새 활동(재수행). 판정은 전부 서버가 한다.

def _control(db: Session, control_id: UUID) -> dict | None:
    return next((c for c in resolve_controls(db) if c["id"] == control_id), None)


def _draft_of(db: Session, cycle_id: UUID, control_id: UUID, kind: str) -> AssessmentActivity | None:
    return db.query(AssessmentActivity).filter(
        AssessmentActivity.cycle_id == cycle_id, AssessmentActivity.control_id == control_id,
        AssessmentActivity.activity_kind == kind, AssessmentActivity.status == ACTIVITY_DRAFT,
        AssessmentActivity.is_deleted == False,  # noqa: E712
    ).first()


def _sample_links(db: Session, sample_ids: list[UUID]) -> dict[str, list[tuple[EvidenceLink, EvidenceFile]]]:
    """샘플 id(문자열) → [(연결, 파일)] — 지워진 연결·파일은 뺀다."""
    if not sample_ids:
        return {}
    rows = db.query(EvidenceLink, EvidenceFile).join(EvidenceFile, EvidenceFile.id == EvidenceLink.file_id).filter(
        EvidenceLink.linked_entity_type == LINK_TARGET_SAMPLE,
        EvidenceLink.linked_entity_id.in_([str(i) for i in sample_ids]),
        EvidenceLink.is_deleted == False,  # noqa: E712
        EvidenceFile.is_deleted == False,  # noqa: E712
    ).order_by(EvidenceFile.created_at).all()
    out: dict[str, list] = {}
    for link, f in rows:
        out.setdefault(link.linked_entity_id, []).append((link, f))
    return out


def _samples(db: Session, activity_ids: list[UUID]) -> list[ActivitySample]:
    if not activity_ids:
        return []
    return db.query(ActivitySample).filter(
        ActivitySample.activity_id.in_(activity_ids),
        ActivitySample.is_deleted == False,  # noqa: E712
    ).order_by(ActivitySample.seq).all()


def _sample_reads(db: Session, activity_ids: list[UUID]) -> dict[UUID, list[SampleRead]]:
    samples = _samples(db, activity_ids)
    links = _sample_links(db, [s.id for s in samples])
    out: dict[UUID, list[SampleRead]] = {}
    for smp in samples:
        r = SampleRead.model_validate(smp)
        r.evidence = [SampleEvidence(link_id=lk.id, file_id=f.id, filename=f.filename, title=f.title)
                      for lk, f in links.get(str(smp.id), [])]
        out.setdefault(smp.activity_id, []).append(r)
    return out


def _sample_done(r: SampleRead) -> bool:
    """제출 조건을 채운 샘플 — 샘플 식별·결과·증빙 1개 이상."""
    return bool((r.label or "").strip()) and r.result is not None and bool(r.evidence)


def _get_activity_or_404(db: Session, activity_id: UUID) -> AssessmentActivity:
    obj = db.query(AssessmentActivity).filter(
        AssessmentActivity.id == activity_id,
        AssessmentActivity.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="AssessmentActivity not found")
    return obj


def _editable_draft(db: Session, activity: AssessmentActivity, user: User) -> AssessmentCycle:
    """작성 중 활동을 고칠 수 있는가 — 회차 진행 중 + 작성 중 + **수행자 본인 + 지금도 이 통제의 수행 역할**."""
    cycle = _get_cycle_or_404(db, activity.cycle_id)
    _assert_open(cycle)
    if activity.status != ACTIVITY_DRAFT:
        raise HTTPException(status_code=409, detail="제출된 기록은 고칠 수 없습니다 — 다시 하려면 새 기록(재수행)을 만드세요")
    required_role, _ = ACTIVITY_RULES[activity.activity_kind]
    if activity.performed_by_id != user.id or _role_holder(db, activity.control_id, required_role) != user.id:
        raise HTTPException(status_code=403, detail="작성한 통제책임자 본인만 고칠 수 있습니다")
    return cycle


def _get_sample_or_404(db: Session, sample_id: UUID) -> ActivitySample:
    obj = db.query(ActivitySample).filter(
        ActivitySample.id == sample_id,
        ActivitySample.is_deleted == False,  # noqa: E712
    ).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="ActivitySample not found")
    return obj


def _sample_read(db: Session, smp: ActivitySample) -> SampleRead:
    return next(r for r in _sample_reads(db, [smp.activity_id]).get(smp.activity_id, []) if r.id == smp.id)


@router.get("/activities/{activity_id}", response_model=ActivityRead)
def get_activity(activity_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> ActivityRead:
    return _to_activity_read(db, _get_activity_or_404(db, activity_id))


@router.patch("/activities/{activity_id}", response_model=ActivityRead)
def update_activity(activity_id: UUID, body: ActivityUpdate, user: User = Depends(require_write),
                    db: Session = Depends(get_db)) -> ActivityRead:
    obj = _get_activity_or_404(db, activity_id)
    _editable_draft(db, obj, user)
    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, f, (v.strip() or None) if isinstance(v, str) else v)
    db.commit()
    db.refresh(obj)
    return _to_activity_read(db, obj)


@router.delete("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_draft(activity_id: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> None:
    """작성 중 기록 버리기 — 샘플·샘플 증빙 연결도 함께(소프트 삭제). 증빙 파일은 회차 × 통제에 그대로 남는다."""
    obj = _get_activity_or_404(db, activity_id)
    _editable_draft(db, obj, user)
    samples = _samples(db, [obj.id])
    for lst in _sample_links(db, [s.id for s in samples]).values():
        for link, _f in lst:
            link.is_deleted = True
    for smp in samples:
        smp.is_deleted = True
    obj.is_deleted = True
    db.commit()


@router.post("/activities/{activity_id}/samples", status_code=status.HTTP_201_CREATED, response_model=SampleRead)
def add_sample(activity_id: UUID, body: SampleWrite, user: User = Depends(require_write),
               db: Session = Depends(get_db)) -> SampleRead:
    """샘플 추가 — 필요 수보다 **더** 보는 것은 허용한다."""
    obj = _get_activity_or_404(db, activity_id)
    _editable_draft(db, obj, user)
    seq = max((s.seq for s in _samples(db, [obj.id])), default=0) + 1
    smp = ActivitySample(activity_id=obj.id, seq=seq, **body.model_dump())
    db.add(smp)
    db.commit()
    db.refresh(smp)
    return _sample_read(db, smp)


@router.patch("/samples/{sample_id}", response_model=SampleRead)
def update_sample(sample_id: UUID, body: SampleWrite, user: User = Depends(require_write),
                  db: Session = Depends(get_db)) -> SampleRead:
    smp = _get_sample_or_404(db, sample_id)
    _editable_draft(db, _get_activity_or_404(db, smp.activity_id), user)
    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(smp, f, (v.strip() or None) if isinstance(v, str) else v)
    db.commit()
    db.refresh(smp)
    return _sample_read(db, smp)


@router.delete("/samples/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sample(sample_id: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> None:
    """샘플 줄 삭제 — **필요 수 아래로는 줄일 수 없다**(마스터 결정: 적게 제출 불가)."""
    smp = _get_sample_or_404(db, sample_id)
    activity = _get_activity_or_404(db, smp.activity_id)
    cycle = _editable_draft(db, activity, user)
    need = sampling.required_samples(cycle.kind, _control(db, activity.control_id))
    if len(_samples(db, [activity.id])) <= need:
        raise HTTPException(status_code=409, detail=f"필요 샘플 수({need}건)보다 줄일 수 없습니다")
    for lst in _sample_links(db, [smp.id]).values():
        for link, _f in lst:
            link.is_deleted = True
    smp.is_deleted = True
    db.commit()


@router.post("/activities/{activity_id}/submit", response_model=ActivityRead)
def submit_activity(activity_id: UUID, user: User = Depends(require_write),
                    db: Session = Depends(get_db)) -> ActivityRead:
    """제출 — 필요 샘플 수만큼 **샘플 식별·결과·증빙**이 다 채워져야 한다. 적게는 제출할 수 없다."""
    obj = _get_activity_or_404(db, activity_id)
    cycle = _editable_draft(db, obj, user)
    need = sampling.required_samples(cycle.kind, _control(db, obj.control_id))
    reads = _sample_reads(db, [obj.id]).get(obj.id, [])
    done = sum(1 for r in reads if _sample_done(r))
    if done < need:
        raise HTTPException(status_code=409, detail=(
            f"필요 샘플 {need}건 중 {done}건만 완료됐습니다 — 샘플마다 식별·결과·증빙을 채워야 제출할 수 있습니다"))
    partial = [r.seq for r in reads if not _sample_done(r)]
    if partial:
        raise HTTPException(status_code=409, detail=(
            f"샘플 {', '.join(map(str, partial))}번이 비어 있습니다 — 채우거나 줄을 지우세요"))
    if obj.result not in ("pass", "fail", "na"):
        raise HTTPException(status_code=409, detail="테스트 결론(적정·미흡·해당 없음)을 선택해야 제출할 수 있습니다")
    obj.status = ACTIVITY_SUBMITTED
    obj.submitted_at = datetime.now(UTC)
    obj.required_samples = need
    db.commit()
    db.refresh(obj)
    return _to_activity_read(db, obj)


# ── 내 평가 목록 (2026-10-15) ─────────────────────────────

_OWNER_KIND = {CYCLE_DESIGN: ACTIVITY_DESIGN, CYCLE_OPERATION: ACTIVITY_TEST}


@router.get("/cycles/{cycle_id}/worklist", response_model=list[WorklistRow])
def get_worklist(cycle_id: UUID, mine: bool = True, user: CurrentUser = None,
                 db: Session = Depends(get_db)) -> list[WorklistRow]:
    """회차 대상 통제 + 내 역할 + 진행 상태.

    `mine=true`(기본) — 내가 통제책임자·평가자·부서승인자인 통제만.
    `mine=false` — 전체. 내부회계 관리자(1~3단계)·외부감사인·외부자문만(마스터 결정 Q3: 통제책임자는 본인 담당만).
    """
    cycle = _get_cycle_or_404(db, cycle_id)
    if not mine and not can_view_all(tenant_roles(db, user.id)):
        raise HTTPException(status_code=403, detail="전체 보기는 내부회계 관리자·외부감사인만 할 수 있습니다")
    kind = _OWNER_KIND[cycle.kind]
    targets = db.query(CycleTarget).filter(CycleTarget.cycle_id == cycle_id,
                                           CycleTarget.is_deleted == False).order_by(  # noqa: E712
        CycleTarget.control_code).all()
    controls = {c["id"]: c for c in resolve_controls(db)}
    proc_ids = {p["code"]: p["id"] for p in resolve_processes(db)}
    assignments = _assignments_by_target(db)
    dept_on = _dept_approval_enabled(db)

    rows: list[tuple[CycleTarget, dict | None, dict[str, UUID], bool]] = []
    for t in targets:
        c = controls.get(t.control_id)
        resolved = resolve_roles_for_control(db, t.control_id, proc_ids.get((c or {}).get("process_code")),
                                             assignments=assignments)
        holders = {r["role_name"]: r["user_id"] for r in resolved}
        if mine and user.id not in {holders.get(ROLE_CONTROL_OWNER), holders.get(ROLE_ASSESSOR),
                                    holders.get(ROLE_DEPT_APPROVER)}:
            continue
        rows.append((t, c, holders, dept_on and not is_dept_approval_skipped(resolved)))

    ids = [t.control_id for t, *_ in rows]
    acts = db.query(AssessmentActivity).filter(
        AssessmentActivity.cycle_id == cycle_id, AssessmentActivity.control_id.in_(ids),
        AssessmentActivity.activity_kind == kind, AssessmentActivity.is_deleted == False,  # noqa: E712
    ).order_by(AssessmentActivity.performed_at).all() if ids else []
    by_control: dict[UUID, list[AssessmentActivity]] = {}
    for a in acts:
        by_control.setdefault(a.control_id, []).append(a)
    latest = {cid: lst[-1] for cid, lst in by_control.items()}
    samples = _sample_reads(db, [a.id for a in latest.values()])
    stages: dict[UUID, set[str]] = {}
    approvers: dict[UUID, set[UUID]] = {}
    if latest:
        for ap in db.query(ActivityApproval).filter(
                ActivityApproval.activity_id.in_([a.id for a in latest.values()]),
                ActivityApproval.is_deleted == False).all():  # noqa: E712
            stages.setdefault(ap.activity_id, set()).add(ap.stage)
            approvers.setdefault(ap.activity_id, set()).add(ap.approved_by_id)
    ev_count: dict[UUID, int] = {}
    if ids:
        for (cid,) in db.query(EvidenceFile.control_id).filter(
                EvidenceFile.cycle_id == cycle_id, EvidenceFile.control_id.in_(ids),
                EvidenceFile.is_deleted == False).all():  # noqa: E712
            ev_count[cid] = ev_count.get(cid, 0) + 1
    owner_names = _names(db, {h[ROLE_CONTROL_OWNER] for _, _, h, _ in rows if h.get(ROLE_CONTROL_OWNER)})
    role_of = {APPROVAL_DEPT: ROLE_DEPT_APPROVER, APPROVAL_ASSESSOR: ROLE_ASSESSOR}

    out = []
    for t, c, holders, dept_needed in rows:
        c = c or {}
        a = latest.get(t.control_id)
        need_stages = ([APPROVAL_DEPT] if dept_needed else []) + [APPROVAL_ASSESSOR]
        state, pending, can, sod = "not_started", [], [], None
        if a is not None and a.status == ACTIVITY_DRAFT:
            state = "draft"
        elif a is not None:
            pending = [s for s in need_stages if s not in stages.get(a.id, set())]
            state = "submitted" if pending else "approved"
            if cycle.status == CYCLE_OPEN:
                mine_pending = [s for s in pending if holders.get(role_of[s]) == user.id]
                sod = _sod_block(a.performed_by_id, approvers.get(a.id, set()), user.id) if mine_pending else None
                can = [] if sod else mine_pending
        owner_id = holders.get(ROLE_CONTROL_OWNER)
        out.append(WorklistRow(
            control_id=t.control_id, control_code=t.control_code or c.get("code"),
            control_name=c.get("name"), process_code=c.get("process_code"),
            frequency=c.get("frequency"), auto_manual=c.get("auto_manual"),
            owner_id=owner_id, owner_name=owner_names.get(owner_id) if owner_id else None,
            my_roles=[r for r in (ROLE_CONTROL_OWNER, ROLE_ASSESSOR, ROLE_DEPT_APPROVER) if holders.get(r) == user.id],
            activity_kind=kind,
            required_samples=(a.required_samples if a is not None and a.required_samples
                              else sampling.required_samples(cycle.kind, c or None)),
            sample_basis=sampling.basis(cycle.kind, c or None),
            rcm_test_methods=c.get("test_methods"), rcm_population=c.get("population"),
            rcm_test_procedure=c.get("test_procedure"), rcm_control_status=c.get("control_status"),
            state=state, activity_id=a.id if a else None, activity_count=len(by_control.get(t.control_id, [])),
            samples_done=sum(1 for r in samples.get(a.id, []) if _sample_done(r)) if a else 0,
            evidence_count=ev_count.get(t.control_id, 0), pending_stages=pending, can_approve=can,
            sod_blocked=sod,
        ))
    return out
