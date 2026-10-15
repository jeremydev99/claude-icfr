from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import require_write
from app.models.test_module import ControlRiskAssessment
from app.models.user import User
from app.schemas.test_module import (
    ControlRiskAssessmentCreate,
    ControlRiskAssessmentRead,
    ControlRiskAssessmentUpdate,
)
from app.services.control_resolver import resolve_assertion_target

router = APIRouter(prefix="/api/test", tags=["test_module"])

# TestRun(/runs·/steps)은 폐지했다(2026-10-15, ADR-0032 §2.10) — 테스트는 평가 회차 활동(test)과
# 샘플(activity_samples)로 기록한다(api/assessment). 운영 test_runs 0건이라 이관 없음.
# 테이블(test_runs·test_steps·test_status_history)은 남겨 둔다 — 삭제는 별도 마이그레이션.
# 이 라우터에는 통제 위험평가(RAWC)만 남는다 — RCM 상세 화면이 쓴다.


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "test_module",
        "name_kr": "Test (평가)",
        "phase_0_status": "RAWC 만 — 테스트는 /api/assessment(내 평가)로 이전",
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
def create_rawc(body: ControlRiskAssessmentCreate, user: User = Depends(require_write), db: Session = Depends(get_db)) -> ControlRiskAssessment:
    target = resolve_assertion_target(db, body.control_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Control not found")
    baseline_control_id, instance_control_id = target
    obj = ControlRiskAssessment(
        **body.model_dump(),
        baseline_control_id=baseline_control_id,
        instance_control_id=instance_control_id,
    )
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
def update_rawc(rawc_id: UUID, body: ControlRiskAssessmentUpdate, user: User = Depends(require_write), db: Session = Depends(get_db)) -> ControlRiskAssessment:
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
def delete_rawc(rawc_id: UUID, user: User = Depends(require_write), db: Session = Depends(get_db)) -> None:
    obj = db.query(ControlRiskAssessment).filter(
        ControlRiskAssessment.id == rawc_id, ControlRiskAssessment.is_deleted == False  # noqa: E712
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="ControlRiskAssessment not found")
    obj.is_deleted = True
    db.commit()
