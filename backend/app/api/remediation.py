from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_db
from app.models.remediation import Deficiency, RemediationPlan, DesignAssessment, RemediationStatusHistory
from app.schemas.remediation import (
    DeficiencyCreate, DeficiencyUpdate, DeficiencyRead,
    RemediationPlanCreate, RemediationPlanUpdate, RemediationPlanRead, RemediationTransitionRequest,
    RemediationStatusHistoryRead,
    DesignAssessmentCreate, DesignAssessmentUpdate, DesignAssessmentRead,
)

router = APIRouter(prefix="/api/remediation", tags=["remediation"])

ALLOWED_TRANSITIONS: dict = {
    "planned": {"in_progress"},
    "in_progress": {"completed"},
    "completed": {"approved"},
    "approved": set(),
}


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
    return {"items": [DeficiencyRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/deficiencies", status_code=status.HTTP_201_CREATED, response_model=DeficiencyRead)
def create_deficiency(body: DeficiencyCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Deficiency:
    obj = Deficiency(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/deficiencies/{deficiency_id}", response_model=DeficiencyRead)
def get_deficiency(deficiency_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> Deficiency:
    obj = db.query(Deficiency).filter(Deficiency.id == deficiency_id, Deficiency.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Deficiency not found")
    return obj


@router.patch("/deficiencies/{deficiency_id}", response_model=DeficiencyRead)
def update_deficiency(deficiency_id: UUID, body: DeficiencyUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Deficiency:
    obj = db.query(Deficiency).filter(Deficiency.id == deficiency_id, Deficiency.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Deficiency not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/deficiencies/{deficiency_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deficiency(deficiency_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
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
    obj.is_deleted = True
    db.commit()


# ── Remediation Plans ──────────────────────────────────────

@router.get("/plans")
def list_plans(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(RemediationPlan).filter(RemediationPlan.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [RemediationPlanRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/plans", status_code=status.HTTP_201_CREATED, response_model=RemediationPlanRead)
def create_plan(body: RemediationPlanCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> RemediationPlan:
    obj = RemediationPlan(**body.model_dump())
    db.add(obj)
    db.flush()
    history = RemediationStatusHistory(
        remediation_plan_id=obj.id,
        from_status=None,
        to_status="planned",
        changed_by_id=user.id,
        changed_at=datetime.now(timezone.utc),
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
def update_plan(plan_id: UUID, body: RemediationPlanUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> RemediationPlan:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    obj.is_deleted = True
    db.commit()


@router.post("/plans/{plan_id}/transition", response_model=RemediationPlanRead)
def transition_plan(plan_id: UUID, body: RemediationTransitionRequest, user: CurrentUser = None, db: Session = Depends(get_db)) -> RemediationPlan:
    obj = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id, RemediationPlan.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    if body.to_status not in ALLOWED_TRANSITIONS.get(obj.status, set()):
        raise HTTPException(
            status_code=422,
            detail=f"전이 불가: {obj.status} → {body.to_status}. 허용: {ALLOWED_TRANSITIONS.get(obj.status, set())}",
        )
    from_status = obj.status
    obj.status = body.to_status
    if body.to_status == "approved":
        obj.approved_by_id = user.id
        obj.approved_at = datetime.now(timezone.utc)
    history = RemediationStatusHistory(
        remediation_plan_id=obj.id,
        from_status=from_status,
        to_status=body.to_status,
        changed_by_id=user.id,
        changed_at=datetime.now(timezone.utc),
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
def create_design_assessment(body: DesignAssessmentCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> DesignAssessment:
    existing = db.query(DesignAssessment).filter(
        DesignAssessment.control_id == body.control_id,
        DesignAssessment.fiscal_year == body.fiscal_year,
        DesignAssessment.is_deleted == False,  # noqa: E712
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="해당 통제·연도의 설계평가가 이미 존재합니다")
    obj = DesignAssessment(**body.model_dump())
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
def update_design_assessment(assessment_id: UUID, body: DesignAssessmentUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> DesignAssessment:
    obj = db.query(DesignAssessment).filter(DesignAssessment.id == assessment_id, DesignAssessment.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="DesignAssessment not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/design-assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_design_assessment(assessment_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(DesignAssessment).filter(DesignAssessment.id == assessment_id, DesignAssessment.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="DesignAssessment not found")
    obj.is_deleted = True
    db.commit()
