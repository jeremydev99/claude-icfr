from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_db
from app.models.rcm import Process, RiskCategory, Control, ControlAssertion
from app.schemas.rcm import (
    ProcessCreate, ProcessUpdate, ProcessRead,
    RiskCategoryCreate, RiskCategoryUpdate, RiskCategoryRead,
    ControlCreate, ControlUpdate, ControlRead,
    ControlAssertionCreate, ControlAssertionRead,
)

router = APIRouter(prefix="/api/rcm", tags=["rcm"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "rcm",
        "name_kr": "RCM 관리",
        "phase_0_status": "최소 CRUD 완료",
        "phase_1_features": ["통제 CRUD", "검색·필터 (프로세스/어써션)", "Excel 일괄 업로드", "단순 이력"],
        "phase_1_excluded": ["버전 관리 (스냅샷·Diff)", "변경 승인 워크플로"],
        "available_in_phase_1": True,
    }


# ── Processes ──────────────────────────────────────────────

@router.get("/processes")
def list_processes(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(Process).filter(Process.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [ProcessRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/processes", status_code=status.HTTP_201_CREATED, response_model=ProcessRead)
def create_process(body: ProcessCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Process:
    obj = Process(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/processes/{process_id}", response_model=ProcessRead)
def get_process(process_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> Process:
    obj = db.query(Process).filter(Process.id == process_id, Process.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Process not found")
    return obj


@router.patch("/processes/{process_id}", response_model=ProcessRead)
def update_process(process_id: UUID, body: ProcessUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Process:
    obj = db.query(Process).filter(Process.id == process_id, Process.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Process not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process(process_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(Process).filter(Process.id == process_id, Process.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Process not found")
    obj.is_deleted = True
    db.commit()


# ── Risk Categories ────────────────────────────────────────

@router.get("/risk-categories")
def list_risk_categories(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(RiskCategory).filter(RiskCategory.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [RiskCategoryRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/risk-categories", status_code=status.HTTP_201_CREATED, response_model=RiskCategoryRead)
def create_risk_category(body: RiskCategoryCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> RiskCategory:
    obj = RiskCategory(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/risk-categories/{rc_id}", response_model=RiskCategoryRead)
def get_risk_category(rc_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> RiskCategory:
    obj = db.query(RiskCategory).filter(RiskCategory.id == rc_id, RiskCategory.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RiskCategory not found")
    return obj


@router.patch("/risk-categories/{rc_id}", response_model=RiskCategoryRead)
def update_risk_category(rc_id: UUID, body: RiskCategoryUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> RiskCategory:
    obj = db.query(RiskCategory).filter(RiskCategory.id == rc_id, RiskCategory.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RiskCategory not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/risk-categories/{rc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk_category(rc_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(RiskCategory).filter(RiskCategory.id == rc_id, RiskCategory.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="RiskCategory not found")
    obj.is_deleted = True
    db.commit()


# ── Controls ───────────────────────────────────────────────

@router.get("/controls")
def list_controls(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(Control).filter(Control.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [ControlRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/controls", status_code=status.HTTP_201_CREATED, response_model=ControlRead)
def create_control(body: ControlCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Control:
    obj = Control(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/controls/{control_id}", response_model=ControlRead)
def get_control(control_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> Control:
    obj = db.query(Control).filter(Control.id == control_id, Control.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Control not found")
    return obj


@router.patch("/controls/{control_id}", response_model=ControlRead)
def update_control(control_id: UUID, body: ControlUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> Control:
    obj = db.query(Control).filter(Control.id == control_id, Control.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Control not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_control(control_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(Control).filter(Control.id == control_id, Control.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="Control not found")
    obj.is_deleted = True
    db.commit()


# ── Control Assertions ─────────────────────────────────────

@router.get("/control-assertions")
def list_control_assertions(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(ControlAssertion).filter(ControlAssertion.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [ControlAssertionRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/control-assertions", status_code=status.HTTP_201_CREATED, response_model=ControlAssertionRead)
def create_control_assertion(body: ControlAssertionCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> ControlAssertion:
    obj = ControlAssertion(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/control-assertions/{ca_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_control_assertion(ca_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(ControlAssertion).filter(ControlAssertion.id == ca_id, ControlAssertion.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="ControlAssertion not found")
    obj.is_deleted = True
    db.commit()
