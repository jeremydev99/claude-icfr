from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api import _approval_view as av
from app.core.deps import CurrentUser, get_db
from app.core.permissions import require_icfr_staff, require_write
from app.models.governance import AS_CONFIRMED, ENTITY_DEFICIENCY
from app.models.remediation import (
    Deficiency,
    DesignAssessment,
    RemediationPlan,
    RemediationStatusHistory,
)
from app.models.user import User
from app.schemas.remediation import (
    DeficiencyApproval,
    DeficiencyCreate,
    DeficiencyRead,
    DeficiencyUpdate,
    DesignAssessmentCreate,
    DesignAssessmentRead,
    DesignAssessmentUpdate,
    RemediationPlanCreate,
    RemediationPlanRead,
    RemediationPlanUpdate,
    RemediationStatusHistoryRead,
    RemediationTransitionRequest,
)
from app.schemas.scoping import GovernanceEventRead, ReviewRequest, TransitionRequest
from app.services import approval_flow
from app.services import deficiency_approval as dap
from app.services.control_resolver import resolve_assertion_target

router = APIRouter(prefix="/api/remediation", tags=["remediation"])

ALLOWED_TRANSITIONS: dict = {
    "planned": {"in_progress"},
    "in_progress": {"completed"},
    "completed": {"approved"},
    "approved": set(),
}


# ── 승인 후 잠금·본인 승인 금지 (13.9-94, ADR-0038 2단계 선행 조치) ──
# 결재선은 ADR-0038 2단계에서 붙인다. 여기서는 승인 후 수정·삭제와 자기 승인만 막는다.
def _assert_plan_not_approved(plan: RemediationPlan) -> None:
    if plan.status == "approved":
        raise HTTPException(status_code=409, detail="승인된 개선계획은 수정·삭제할 수 없습니다")


def _assert_not_self_approval(db: Session, plan: RemediationPlan, user_id: UUID) -> None:
    """개선 책임자(owner)·완료 처리자는 승인할 수 없다 — 자기 승인 금지(ADR-0038 §2.2)."""
    h = (db.query(RemediationStatusHistory)
         .filter(RemediationStatusHistory.remediation_plan_id == plan.id,
                 RemediationStatusHistory.to_status == "completed")
         .order_by(RemediationStatusHistory.changed_at.desc()).first())
    if user_id in (plan.owner_id, h.changed_by_id if h else None):
        raise HTTPException(status_code=409,
                            detail="개선 책임자·완료 처리자는 승인할 수 없습니다 — 자기 승인 금지")


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "remediation",
        "name_kr": "개선계획",
        "phase_0_status": "최소 CRUD 완료",
        "phase_1_features": ["미비점 CRUD", "단순 심각도 3단계", "개선계획 서술형", "종결 처리",
                             "설계평가 (DesignAssessment)", "4단계 워크플로 + 이력"],
        "available_in_phase_1": True,
    }


# ── Deficiencies ───────────────────────────────────────────

@router.get("/deficiencies")
def list_deficiencies(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(Deficiency).filter(Deficiency.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [_read(db, i) for i in items], "total": total, "skip": skip, "limit": limit}


def _read(db: Session, d: Deficiency) -> DeficiencyRead:
    r = DeficiencyRead.model_validate(d)
    r.approval_status = dap.approval_status(db, d)
    return r


def _get_def(db: Session, deficiency_id: UUID) -> Deficiency:
    obj = db.query(Deficiency).filter(Deficiency.id == deficiency_id, Deficiency.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Deficiency not found")
    return obj


@router.post("/deficiencies", status_code=status.HTTP_201_CREATED, response_model=DeficiencyRead)
def create_deficiency(body: DeficiencyCreate, user: User = Depends(require_write), db: Session = Depends(get_db)) -> Deficiency:
    baseline_control_id = instance_control_id = None
    if body.control_id is not None:
        target = resolve_assertion_target(db, body.control_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Control not found")
        baseline_control_id, instance_control_id = target
    obj = Deficiency(
        **body.model_dump(),
        baseline_control_id=baseline_control_id,
        instance_control_id=instance_control_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _read(db, obj)


@router.get("/deficiencies/{deficiency_id}", response_model=DeficiencyRead)
def get_deficiency(deficiency_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> DeficiencyRead:
    return _read(db, _get_def(db, deficiency_id))


# 비울 수 없는 칸 — 명시적 null 은 422
_NOT_NULL = {"severity", "description", "status", "fiscal_year"}


@router.patch("/deficiencies/{deficiency_id}", response_model=DeficiencyRead)
def update_deficiency(deficiency_id: UUID, body: DeficiencyUpdate, user: User = Depends(require_write),
                      db: Session = Depends(get_db)) -> DeficiencyRead:
    """수정 — 보낸 칸만 바꾼다(`final_conclusion` 은 null 로 비울 수 있다). **검토 중·확정이면 평가 내용(심각도·설명·
    결론·통제 연결 등)은 409**, 개선 진행 상태(`status`)는 계속 바꿀 수 있다(ADR-0038 2-3)."""
    obj = _get_def(db, deficiency_id)
    changes = body.model_dump(exclude_unset=True)
    nulls = sorted(k for k, v in changes.items() if v is None and k in _NOT_NULL)
    if nulls:
        raise HTTPException(status_code=422, detail=f"비울 수 없는 항목입니다: {', '.join(nulls)}")
    try:
        dap.ensure_editable(db, obj, set(changes))
    except approval_flow.FlowError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    for field, val in changes.items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return _read(db, obj)


@router.delete("/deficiencies/{deficiency_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deficiency(deficiency_id: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> None:
    obj = db.query(Deficiency).filter(Deficiency.id == deficiency_id, Deficiency.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Deficiency not found")
    # soft delete라 FK 제약이 작동하지 않으므로, 활성 개선계획 존재 시 삭제 차단 (409)
    active_plans = db.query(RemediationPlan).filter(
        RemediationPlan.deficiency_id == deficiency_id,
        RemediationPlan.is_deleted == False,  # noqa: E712
    ).count()
    if active_plans > 0:
        raise HTTPException(status_code=409, detail="연결된 개선계획이 있어 삭제할 수 없습니다")
    if dap.approval_status(db, obj) != "draft":
        raise HTTPException(status_code=409, detail="검토 중이거나 확정된 미비점은 삭제할 수 없습니다")
    obj.is_deleted = True
    db.commit()


# ── 미비점 평가 결재 (ADR-0038 2-3) — 재오픈 없음 ──────────────────

def _approval(db: Session, d: Deficiency, user_id: UUID) -> DeficiencyApproval:
    st = approval_flow.view_state(db, dap.hooks(db, d))
    legacy = st.status == AS_CONFIRMED and st.confirmed_by_id is None
    return DeficiencyApproval(
        deficiency=_read(db, d), legacy_confirmed=legacy,
        governance=av.governance_info(db, st, user_id, legacy_confirmed_by=d.confirmed_by_id if legacy else None,
                                      no_reopen=dap.NO_REOPEN))


def _flow(db: Session, fn) -> None:
    try:
        fn()
    except approval_flow.FlowError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    db.commit()


@router.get("/deficiencies/{deficiency_id}/approval", response_model=DeficiencyApproval)
def get_deficiency_approval(deficiency_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> DeficiencyApproval:
    return _approval(db, _get_def(db, deficiency_id), user.id)


@router.post("/deficiencies/{deficiency_id}/transition", response_model=DeficiencyApproval)
def transition_deficiency(deficiency_id: UUID, req: TransitionRequest, user: User = Depends(require_icfr_staff),
                          db: Session = Depends(get_db)) -> DeficiencyApproval:
    """평가 결론 결재 — draft→review(검토 요청: 심각도·최종 결론 필수) / review→draft(회수·반려) /
    review→confirmed(마스터 승인, 요청자·검토자 불가). 확정 후 재오픈 없음."""
    d = _get_def(db, deficiency_id)
    h = dap.hooks(db, d)
    reason = (req.reason or "").strip() or None
    cur = approval_flow.view_state(db, h).status
    if cur == "draft" and req.to_status == "review":
        _flow(db, lambda: approval_flow.submit(db, h, user.id, reason))
    elif cur == "review" and req.to_status == "draft":
        _flow(db, lambda: approval_flow.back_to_draft(db, h, user.id, reason))
    elif cur == "review" and req.to_status == "confirmed":
        _flow(db, lambda: approval_flow.approve(db, h, user.id, reason))
    elif cur == "confirmed":
        raise HTTPException(status_code=409, detail=dap.NO_REOPEN)
    else:
        raise HTTPException(status_code=409, detail=f"'{cur}' 에서 '{req.to_status}' 로 바꿀 수 없습니다")
    return _approval(db, d, user.id)


@router.post("/deficiencies/{deficiency_id}/review", response_model=DeficiencyApproval)
def review_deficiency(deficiency_id: UUID, req: ReviewRequest, user: User = Depends(require_icfr_staff),
                      db: Session = Depends(get_db)) -> DeficiencyApproval:
    """책임관리자 검토 — 일반관리자가 요청한 건만. 요청자 본인 불가."""
    d = _get_def(db, deficiency_id)
    h = dap.hooks(db, d)
    _flow(db, lambda: approval_flow.review(db, h, user.id, req.action, (req.reason or "").strip() or None))
    return _approval(db, d, user.id)


@router.post("/deficiencies/{deficiency_id}/external-approval", response_model=DeficiencyApproval)
def external_approval_deficiency(deficiency_id: UUID, approver_body: str = Form(...), approved_on: str = Form(...),
                                 reference: str | None = Form(default=None), purpose: str = Form(default="approve"),
                                 files: list[UploadFile] = File(...), user: User = Depends(require_icfr_staff),
                                 db: Session = Depends(get_db)) -> DeficiencyApproval:
    """마스터관리자 작성분의 대표이사·이사회 **외부 승인 기록** — 증빙 파일 필수. 재오픈이 없으므로 확정 목적만."""
    if purpose != "approve":
        raise HTTPException(status_code=409, detail=dap.NO_REOPEN)
    d = _get_def(db, deficiency_id)
    h = dap.hooks(db, d)
    ev = [approval_flow.EvidenceFile(filename=f.filename or "", content_type=f.content_type,
                                     data=f.file.read(approval_flow.MAX_EVIDENCE_BYTES + 1)) for f in files]
    _flow(db, lambda: approval_flow.record_external(db, h, user.id, purpose="approve", approver_body=approver_body,
                                                    approved_on=approved_on, reference=reference, files=ev))
    return _approval(db, d, user.id)


@router.get("/deficiencies/{deficiency_id}/governance-events", response_model=list[GovernanceEventRead])
def list_deficiency_events(deficiency_id: UUID, user: CurrentUser, db: Session = Depends(get_db)
                           ) -> list[GovernanceEventRead]:
    """검토·승인 이력(최신순) — 지울 수 없는 기록."""
    return av.events(db, ENTITY_DEFICIENCY, _get_def(db, deficiency_id).id)


# ── Remediation Plans ──────────────────────────────────────

@router.get("/plans")
def list_plans(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(RemediationPlan).filter(RemediationPlan.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [RemediationPlanRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/plans", status_code=status.HTTP_201_CREATED, response_model=RemediationPlanRead)
def create_plan(body: RemediationPlanCreate, user: User = Depends(require_write), db: Session = Depends(get_db)) -> RemediationPlan:
    obj = RemediationPlan(**body.model_dump())
    db.add(obj)
    db.flush()
    history = RemediationStatusHistory(
        remediation_plan_id=obj.id,
        from_status=None,
        to_status="planned",
        changed_by_id=user.id,
        changed_at=datetime.now(UTC),
    )
    db.add(history)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/plans/{plan_id}", response_model=RemediationPlanRead)
def get_plan(plan_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> RemediationPlan:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    return obj


@router.patch("/plans/{plan_id}", response_model=RemediationPlanRead)
def update_plan(plan_id: UUID, body: RemediationPlanUpdate, user: User = Depends(require_write), db: Session = Depends(get_db)) -> RemediationPlan:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    _assert_plan_not_approved(obj)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> None:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    _assert_plan_not_approved(obj)
    obj.is_deleted = True
    db.commit()


@router.post("/plans/{plan_id}/transition", response_model=RemediationPlanRead)
def transition_plan(plan_id: UUID, body: RemediationTransitionRequest, user: User = Depends(require_write), db: Session = Depends(get_db)) -> RemediationPlan:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    if body.to_status not in ALLOWED_TRANSITIONS.get(obj.status, set()):
        raise HTTPException(
            status_code=422,
            detail=f"전이 불가: {obj.status} → {body.to_status}. 허용: {ALLOWED_TRANSITIONS.get(obj.status, set())}",
        )
    if body.to_status == "approved":
        _assert_not_self_approval(db, obj, user.id)
    from_status = obj.status
    obj.status = body.to_status
    if body.to_status == "approved":
        obj.approved_by_id = user.id
        obj.approved_at = datetime.now(UTC)
    history = RemediationStatusHistory(
        remediation_plan_id=obj.id,
        from_status=from_status,
        to_status=body.to_status,
        changed_by_id=user.id,
        changed_at=datetime.now(UTC),
        reason=body.reason,
    )
    db.add(history)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/plans/{plan_id}/history")
def get_plan_history(plan_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    history = (
        db.query(RemediationStatusHistory)
        .filter(RemediationStatusHistory.remediation_plan_id == plan_id)
        .order_by(RemediationStatusHistory.changed_at)
        .all()
    )
    return {"items": [RemediationStatusHistoryRead.model_validate(h) for h in history], "total": len(history)}


# ── DesignAssessment ────────────────────────────────────────

@router.get("/design-assessments")
def list_design_assessments(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(DesignAssessment).filter(DesignAssessment.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [DesignAssessmentRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/design-assessments", status_code=status.HTTP_201_CREATED, response_model=DesignAssessmentRead)
def create_design_assessment(body: DesignAssessmentCreate, user: User = Depends(require_write), db: Session = Depends(get_db)) -> DesignAssessment:
    existing = db.query(DesignAssessment).filter(
        DesignAssessment.control_id == body.control_id,
        DesignAssessment.fiscal_year == body.fiscal_year,
        DesignAssessment.is_deleted == False,  # noqa: E712
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="해당 통제·연도의 설계평가가 이미 존재합니다")
    target = resolve_assertion_target(db, body.control_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Control not found")
    baseline_control_id, instance_control_id = target
    obj = DesignAssessment(
        **body.model_dump(),
        baseline_control_id=baseline_control_id,
        instance_control_id=instance_control_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/design-assessments/by-control/{control_id}")
def get_design_assessment_by_control(
    control_id: UUID, fiscal_year: int | None = None,
    user: CurrentUser = None, db: Session = Depends(get_db)
) -> dict:
    q = db.query(DesignAssessment).filter(
        DesignAssessment.control_id == control_id,
        DesignAssessment.is_deleted == False,  # noqa: E712
    )
    if fiscal_year is not None:
        q = q.filter(DesignAssessment.fiscal_year == fiscal_year)
    items = q.order_by(DesignAssessment.fiscal_year.desc()).all()
    return {"items": [DesignAssessmentRead.model_validate(i) for i in items], "total": len(items)}


@router.get("/design-assessments/{assessment_id}", response_model=DesignAssessmentRead)
def get_design_assessment(assessment_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> DesignAssessment:
    obj = db.query(DesignAssessment).filter(DesignAssessment.id == assessment_id, DesignAssessment.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="DesignAssessment not found")
    return obj


@router.patch("/design-assessments/{assessment_id}", response_model=DesignAssessmentRead)
def update_design_assessment(assessment_id: UUID, body: DesignAssessmentUpdate, user: User = Depends(require_write), db: Session = Depends(get_db)) -> DesignAssessment:
    obj = db.query(DesignAssessment).filter(DesignAssessment.id == assessment_id, DesignAssessment.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="DesignAssessment not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/design-assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_design_assessment(assessment_id: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> None:
    obj = db.query(DesignAssessment).filter(DesignAssessment.id == assessment_id, DesignAssessment.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="DesignAssessment not found")
    obj.is_deleted = True
    db.commit()
