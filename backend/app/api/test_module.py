from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.test_module import ControlRiskAssessment, TestRun, TestStep, TestStatusHistory
from app.schemas.test_module import (
    ControlRiskAssessmentCreate, ControlRiskAssessmentRead, ControlRiskAssessmentUpdate,
    TestRunCreate, TestRunRead, TestRunUpdate,
    TestStatusHistoryRead,
    TestStepCreate, TestStepRead, TestStepUpdate,
    TransitionRequest,
)

router = APIRouter(prefix="/api/test", tags=["test_module"])

# 허용 전이 — 하드코딩 dict. WorkflowEngine·StateMachine 금지 (ADR-0020 원칙).
ALLOWED_TRANSITIONS: dict = {
    "planned": {"in_progress"},
    "in_progress": {"completed"},
    "completed": {"approved"},
    "approved": set(),
}


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "test_module",
        "name_kr": "Test (평가)",
        "phase_0_status": "Phase 1 풀 확장 완료",
        "phase_1_features": [
            "RAWC 평가 (그룹 6)", "Test 워크플로 (그룹 7)",
            "4단계 워크플로 (planned→approved)", "상태 변경 이력",
        ],
        "phase_1_excluded": ["자동 샘플 추출", "재테스트", "설계평가"],
        "available_in_phase_1": True,
    }


# ── RAWC 평가 ─────────────────────────────────────────────
# 주의: /rawc/by-control/{...} 는 /rawc/{id} 보다 먼저 정의해야 함

@router.get("/rawc/by-control/{control_id}")
def get_rawc_by_control(
    control_id: UUID,
    fiscal_year: int | None = None,
    user: CurrentUser = None,
    db: Session = Depends(get_db),
) -> dict:
    q = db.query(ControlRiskAssessment).filter(
        ControlRiskAssessment.control_id == control_id,
        ControlRiskAssessment.is_deleted == False,  # noqa: E712
    )
    if fiscal_year:
        q = q.filter(ControlRiskAssessment.fiscal_year == fiscal_year)
    total = q.count()
    items = q.all()
    return {"items": [ControlRiskAssessmentRead.model_validate(i) for i in items], "total": total}


@router.get("/rawc")
def list_rawc(
    control_id: UUID | None = None,
    fiscal_year: int | None = None,
    skip: int = 0,
    limit: int = 100,
    user: CurrentUser = None,
    db: Session = Depends(get_db),
) -> dict:
    q = db.query(ControlRiskAssessment).filter(ControlRiskAssessment.is_deleted == False)  # noqa: E712
    if control_id:
        q = q.filter(ControlRiskAssessment.control_id == control_id)
    if fiscal_year:
        q = q.filter(ControlRiskAssessment.fiscal_year == fiscal_year)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [ControlRiskAssessmentRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/rawc", status_code=status.HTTP_201_CREATED, response_model=ControlRiskAssessmentRead)
def create_rawc(body: ControlRiskAssessmentCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> ControlRiskAssessment:
    obj = ControlRiskAssessment(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/rawc/{rawc_id}", response_model=ControlRiskAssessmentRead)
def get_rawc(rawc_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> ControlRiskAssessment:
    obj = db.query(ControlRiskAssessment).filter(
        ControlRiskAssessment.id == rawc_id, ControlRiskAssessment.is_deleted == False  # noqa: E712
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="ControlRiskAssessment not found")
    return obj


@router.patch("/rawc/{rawc_id}", response_model=ControlRiskAssessmentRead)
def update_rawc(rawc_id: UUID, body: ControlRiskAssessmentUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> ControlRiskAssessment:
    obj = db.query(ControlRiskAssessment).filter(
        ControlRiskAssessment.id == rawc_id, ControlRiskAssessment.is_deleted == False  # noqa: E712
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="ControlRiskAssessment not found")
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/rawc/{rawc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rawc(rawc_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(ControlRiskAssessment).filter(
        ControlRiskAssessment.id == rawc_id, ControlRiskAssessment.is_deleted == False  # noqa: E712
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="ControlRiskAssessment not found")
    obj.is_deleted = True
    db.commit()


# ── TestRun — 정적 경로 먼저 ─────────────────────────────

@router.get("/runs")
def list_runs(
    fiscal_year: int | None = None,
    status_filter: str | None = None,
    skip: int = 0,
    limit: int = 100,
    user: CurrentUser = None,
    db: Session = Depends(get_db),
) -> dict:
    q = db.query(TestRun).filter(TestRun.is_deleted == False)  # noqa: E712
    if fiscal_year:
        q = q.filter(TestRun.fiscal_year == fiscal_year)
    if status_filter:
        q = q.filter(TestRun.status == status_filter)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [TestRunRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/runs", status_code=status.HTTP_201_CREATED, response_model=TestRunRead)
def create_run(body: TestRunCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> TestRun:
    obj = TestRun(**body.model_dump(), status="planned")
    db.add(obj)
    db.flush()
    # 생성 시 자동 이력 1건 (from_status=None → "planned")
    history = TestStatusHistory(
        test_run_id=obj.id,
        from_status=None,
        to_status="planned",
        changed_by_id=user.id,
        reason="Initial creation",
    )
    db.add(history)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/runs/{run_id}/history")
def get_run_history(run_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    """상태 변경 이력 조회 — 조회 전용, 삭제·수정 불가 (ICFR 무결성)."""
    run = db.query(TestRun).filter(TestRun.id == run_id, TestRun.is_deleted == False).first()  # noqa: E712
    if not run:
        raise HTTPException(status_code=404, detail="TestRun not found")
    items = (
        db.query(TestStatusHistory)
        .filter(TestStatusHistory.test_run_id == run_id)
        .order_by(TestStatusHistory.changed_at.asc())
        .all()
    )
    return {"items": [TestStatusHistoryRead.model_validate(i) for i in items]}


@router.post("/runs/{run_id}/transition")
def transition_test_run(
    run_id: UUID,
    body: TransitionRequest,
    user: CurrentUser = None,
    db: Session = Depends(get_db),
) -> dict:
    """워크플로 전이 — 단일 함수, 하드코딩 dict. WorkflowEngine 금지 (ADR-0020)."""
    run = db.query(TestRun).filter(TestRun.id == run_id, TestRun.is_deleted == False).first()  # noqa: E712
    if not run:
        raise HTTPException(status_code=404, detail="TestRun not found")

    current = run.status
    target = body.to_status

    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=422,
            detail=f"'{current}' → '{target}' 전이는 허용되지 않습니다",
        )

    history = TestStatusHistory(
        test_run_id=run.id,
        from_status=current,
        to_status=target,
        changed_by_id=user.id,
        reason=body.reason,
    )
    db.add(history)

    run.status = target
    if target == "approved":
        run.approved_by_id = user.id
        run.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(run)
    db.refresh(history)
    return {
        "test_run": TestRunRead.model_validate(run),
        "history_entry": TestStatusHistoryRead.model_validate(history),
    }


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
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
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


# ── Test Steps ────────────────────────────────────────────

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
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(obj, f, v)
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
