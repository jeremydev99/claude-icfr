from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_db
from app.models.test_module import TestRun, TestStep
from app.schemas.test_module import (
    TestRunCreate, TestRunUpdate, TestRunRead,
    TestStepCreate, TestStepUpdate, TestStepRead,
)

router = APIRouter(prefix="/api/test", tags=["test_module"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "test_module",
        "name_kr": "Test (평가)",
        "phase_0_status": "최소 CRUD 완료",
        "phase_1_features": ["평가 계획 수동 등록", "운영평가 결과 입력", "Pass/Fail 결론", "단순 검토 워크플로 (1단계)"],
        "phase_1_excluded": ["자동 샘플 추출", "자동 미비점 등록 연동", "재테스트", "설계평가"],
        "available_in_phase_1": True,
    }


# ── Test Runs ──────────────────────────────────────────────

@router.get("/runs")
def list_runs(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(TestRun).filter(TestRun.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [TestRunRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/runs", status_code=status.HTTP_201_CREATED, response_model=TestRunRead)
def create_run(body: TestRunCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> TestRun:
    obj = TestRun(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/runs/{run_id}", response_model=TestRunRead)
def get_run(run_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> TestRun:
    obj = db.query(TestRun).filter(TestRun.id == run_id, TestRun.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="TestRun not found")
    return obj


@router.patch("/runs/{run_id}", response_model=TestRunRead)
def update_run(run_id: UUID, body: TestRunUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> TestRun:
    obj = db.query(TestRun).filter(TestRun.id == run_id, TestRun.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="TestRun not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(run_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(TestRun).filter(TestRun.id == run_id, TestRun.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="TestRun not found")
    obj.is_deleted = True
    db.commit()


# ── Test Steps ─────────────────────────────────────────────

@router.get("/steps")
def list_steps(run_id: UUID | None = None, skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(TestStep).filter(TestStep.is_deleted == False)  # noqa: E712
    if run_id:
        q = q.filter(TestStep.test_run_id == run_id)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [TestStepRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/steps", status_code=status.HTTP_201_CREATED, response_model=TestStepRead)
def create_step(body: TestStepCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> TestStep:
    obj = TestStep(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/steps/{step_id}", response_model=TestStepRead)
def get_step(step_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> TestStep:
    obj = db.query(TestStep).filter(TestStep.id == step_id, TestStep.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="TestStep not found")
    return obj


@router.patch("/steps/{step_id}", response_model=TestStepRead)
def update_step(step_id: UUID, body: TestStepUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> TestStep:
    obj = db.query(TestStep).filter(TestStep.id == step_id, TestStep.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="TestStep not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(step_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(TestStep).filter(TestStep.id == step_id, TestStep.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="TestStep not found")
    obj.is_deleted = True
    db.commit()
