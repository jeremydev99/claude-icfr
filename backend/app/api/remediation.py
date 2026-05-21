from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_db
from app.models.remediation import Deficiency, RemediationPlan
from app.schemas.remediation import (
    DeficiencyCreate, DeficiencyUpdate, DeficiencyRead,
    RemediationPlanCreate, RemediationPlanUpdate, RemediationPlanRead,
)

router = APIRouter(prefix="/api/remediation", tags=["remediation"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "remediation",
        "name_kr": "개선계획",
        "phase_0_status": "최소 CRUD 완료",
        "phase_1_features": ["미비점 CRUD", "단순 심각도 3단계", "개선계획 서술형", "종결 처리"],
        "phase_1_excluded": ["심각도 매트릭스", "마일스톤 추적", "이월 트래킹"],
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
