"""대시보드 모듈 현황 — 메뉴별 데이터 건수 (2026-09-30).

대시보드의 모듈 카드 배지("실데이터 / 데이터 없음 …")가 `navigation.ts` 의 **고정값**이라, 데이터가 들어와도
"데이터 없음"으로 남았다(마스터 지적 — 스코핑에 1,897개 값이 있는데 데이터 없음). 메뉴 경로별로 대표 테이블의
건수를 돌려주고, 프론트가 건수 > 0 이면 "실데이터"로 표시한다.

- 건수는 **현재 테넌트** 기준이다. `AuditedBase` 모델은 자동 필터가 걸리고, 테넌트 필터가 없는 모델
  (`UserTenantAccess`)만 직접 거른다.
- 삭제(소프트) 행은 세지 않는다. 조회 전원(대시보드와 같다).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.tenant_context import get_active_tenant
from app.models.assessment import AssessmentCycle
from app.models.euc import EucFile
from app.models.evidence import EvidenceFile
from app.models.financial_statement import FsStatement
from app.models.iuc import InformationItem
from app.models.org import Department
from app.models.rcm_baseline import BaselineControl, ControlInstance
from app.models.remediation import Deficiency
from app.models.role_assignment import RoleAssignment, TenantPolicy
from app.models.scoping import Scoping
from app.models.tenant import UserTenantAccess
from app.models.test_module import TestRun

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# 메뉴 경로 → 대표 테이블. 경로는 frontend/src/config/navigation.ts 의 path 와 같다
MODULE_TABLES = {
    "/financial-statements": FsStatement,
    "/scoping": Scoping,
    "/euc": EucFile,
    "/iuc": InformationItem,
    "/test": TestRun,
    "/remediation": Deficiency,
    "/evidence": EvidenceFile,
    "/schedule": AssessmentCycle,
    "/admin/departments": Department,
    "/admin/role-assignments": RoleAssignment,
    "/admin/policies": TenantPolicy,
}


def _count(db: Session, model) -> int:
    q = select(func.count()).select_from(model)
    if hasattr(model, "is_deleted"):
        q = q.where(model.is_deleted == False)  # noqa: E712
    return int(db.scalar(q) or 0)


@router.get("/modules")
def module_counts(user: CurrentUser, db: Session = Depends(get_db)) -> dict[str, int]:
    """메뉴 경로별 데이터 건수 — 0 이면 "데이터 없음", 1 이상이면 "실데이터"."""
    out = {path: _count(db, model) for path, model in MODULE_TABLES.items()}
    out["/rcm"] = _count(db, BaselineControl) + _count(db, ControlInstance)
    out["/admin/fiscal-year"] = out["/admin/policies"]
    tenant = get_active_tenant()
    out["/users"] = int(db.scalar(select(func.count()).select_from(UserTenantAccess).where(
        UserTenantAccess.tenant_id == tenant)) or 0) if tenant else 0
    return out
