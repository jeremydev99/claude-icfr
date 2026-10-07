"""평가 회차 최종승인 규칙 (ADR-0038 2-4) — 회차 마감 → 최종승인, **마감자 ≠ 승인자**, 재오픈 없음.

- 마감은 지금처럼 평가자(전담부서)가 한다(ADR-0032 §2.5). 최종승인은 마스터관리자(`icfr_manager`)가 회차 전체에 대해.
- **자기 승인 금지**: 마감한 사람은 최종승인할 수 없다(2026-10-07 이전에는 가능했다).
- 마감자 외에 마스터관리자가 없으면(마감자가 유일한 마스터 등) 대표이사·이사회 **외부 승인 증빙**으로 승인한다(§2.2.1).
- 승인은 막지 않고 경고만: 미완 통제·같은 회계연도 미확정 미비점 건수(ADR-0032 "막지 않고 기록"과 같은 원칙).
- 재오픈 없음 — 이후 개선은 새 차수(회차)로(ADR-0038 §3.1). 2-4 이전에 승인된 회차는 **이전 방식 승인**으로 인정.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import tenant_roles
from app.models.assessment import CYCLE_CLOSED, AssessmentCycle
from app.models.governance import (
    ENTITY_ASSESSMENT_CYCLE,
    EV_APPROVE,
    EV_EXTERNAL_APPROVE,
    GovernanceEvent,
)
from app.models.remediation import Deficiency
from app.models.role_assignment import ROLE_ICFR_MANAGER
from app.models.user_mgmt import UserRole
from app.services import approval
from app.services.assessment_period import current_fiscal_year, fiscal_year_start_month


@dataclass
class CycleCan:
    approve: bool = False
    external_approve: bool = False
    why: dict[str, str] = field(default_factory=dict)


def other_masters(db: Session, closer_id) -> int:
    """마감자를 뺀 마스터관리자 수(활성 테넌트)."""
    q = db.query(UserRole.user_id).filter(UserRole.role_name == ROLE_ICFR_MANAGER,
                                          UserRole.is_deleted == False)  # noqa: E712
    if closer_id is not None:
        q = q.filter(UserRole.user_id != closer_id)
    return q.distinct().count()


def can(db: Session, c: AssessmentCycle, user_id: UUID) -> CycleCan:
    out = CycleCan()
    if c.status != CYCLE_CLOSED:
        out.why["approve"] = "마감된 회차만 최종승인합니다" if c.status == "open" else "이미 최종승인된 회차입니다"
        return out
    if other_masters(db, c.closed_by_id) == 0:
        # 내부에 독립 승인자가 없다 — 외부 승인 기록(기록 행위라 일반관리자 이상 누구나)
        out.external_approve = approval.user_tier(db, user_id) >= 1
        out.why["approve"] = "마감자 외에 마스터관리자가 없어 대표이사·이사회 승인 증빙을 등록해 승인합니다"
        return out
    is_master = ROLE_ICFR_MANAGER in tenant_roles(db, user_id)
    if not is_master:
        out.why["approve"] = "마스터관리자(내부회계관리자)가 최종승인합니다"
    elif user_id == c.closed_by_id:
        out.why["approve"] = "회차를 마감한 사람은 최종승인할 수 없습니다 — 자기 승인 금지"
    else:
        out.approve = True
    return out


def legacy_approved(db: Session, c: AssessmentCycle) -> bool:
    """승인돼 있는데 2-4 결재 기록이 없음 = 이전 방식 승인(그대로 인정)."""
    if c.status != "approved":
        return False
    return db.query(GovernanceEvent).filter(
        GovernanceEvent.entity_type == ENTITY_ASSESSMENT_CYCLE, GovernanceEvent.entity_id == c.id,
        GovernanceEvent.action.in_([EV_APPROVE, EV_EXTERNAL_APPROVE])).first() is None


def fiscal_year_of(db: Session, c: AssessmentCycle) -> int:
    return current_fiscal_year(c.period_end, fiscal_year_start_month(db))


def unconfirmed_deficiencies(db: Session, fiscal_year: int) -> int:
    return db.query(Deficiency).filter(Deficiency.fiscal_year == fiscal_year, Deficiency.confirmed_at.is_(None),
                                       Deficiency.is_deleted == False).count()  # noqa: E712
