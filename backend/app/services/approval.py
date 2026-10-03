"""검토·승인 규칙 (ADR-0038) — 판정은 여기 하나뿐이다. API 는 이 함수들로 막고, 화면은 `can()` 결과만 본다.

- 관리자 단계: 1 일반(`icfr_staff`) · 2 책임(`icfr_lead`) · 3 마스터(`icfr_manager`). `sys_admin` 은 단계를 올리지 않는다.
- 승인 경로(검토 요청 시점에 정해 저장): 일반 작성 + 책임관리자 있음 → 책임 검토 → 마스터 승인 /
  책임 작성(또는 책임관리자 0명) → 마스터 승인 / 마스터 작성 → 대표이사·이사회 외부 승인(증빙).
- 자기 승인 금지: 검토자 ≠ 요청자, 승인자 ≠ 요청자, 승인자 ≠ 검토자. 재오픈 승인자 ≠ 재오픈 요청자.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import tenant_roles
from app.models.governance import (
    PATH_EXTERNAL,
    PATH_LEAD_THEN_MASTER,
    PATH_MASTER,
    REOPEN_PENDING,
    ReopenRequest,
)
from app.models.role_assignment import ROLE_EXTERNAL_ADVISOR, ROLE_ICFR_LEAD, TIER_ROLES
from app.models.scoping import STATUS_CONFIRMED, STATUS_DRAFT, STATUS_REVIEW, Scoping
from app.models.user_mgmt import UserRole

TIER_LABELS = {0: "권한 없음", 1: "일반관리자", 2: "책임관리자", 3: "마스터관리자"}


def tier_of(roles: set[str]) -> int:
    """관리자 단계(0~3). 1~3 은 중복 배정이 막혀 있지만, 옛 데이터가 겹쳐도 가장 높은 단계를 쓴다."""
    t = max((TIER_ROLES[r] for r in roles if r in TIER_ROLES), default=0)
    if t == 0 and ROLE_EXTERNAL_ADVISOR in roles:
        return 1   # PA회계법인 — 일반관리자처럼 작성·검토 요청만(ADR-0039 §2.1)
    return t


def user_tier(db: Session, user_id) -> int:
    return tier_of(tenant_roles(db, user_id))


def has_lead(db: Session) -> bool:
    """활성 테넌트에 책임관리자가 1명이라도 있는가(user_roles 는 테넌트 자동 필터)."""
    return db.query(UserRole).filter(UserRole.role_name == ROLE_ICFR_LEAD,
                                     UserRole.is_deleted == False).first() is not None  # noqa: E712


def path_for(requester_tier: int, lead_exists: bool) -> str:
    """검토 요청자의 단계 → 승인 경로 (순수 함수)."""
    if requester_tier >= 3:
        return PATH_EXTERNAL
    if requester_tier == 1 and lead_exists:
        return PATH_LEAD_THEN_MASTER
    return PATH_MASTER


def pending_reopen(db: Session, entity_id) -> ReopenRequest | None:
    return db.query(ReopenRequest).filter(ReopenRequest.entity_id == entity_id,
                                          ReopenRequest.status == REOPEN_PENDING,
                                          ReopenRequest.is_deleted == False).first()  # noqa: E712


@dataclass
class Can:
    """이 사용자가 지금 할 수 있는 일 + 못 하는 이유(화면 안내용)."""
    edit: bool = False
    submit: bool = False
    withdraw: bool = False
    review: bool = False
    review_return: bool = False
    approve: bool = False
    external_approve: bool = False
    reopen_request: bool = False
    reopen_decide: bool = False
    reopen_external: bool = False
    why: dict[str, str] = field(default_factory=dict)


def can(db: Session, s: Scoping, user_id: UUID) -> Can:
    t = user_tier(db, user_id)
    c = Can()
    if t == 0:
        c.why["all"] = "내부회계 관리자(일반·책임·마스터) 역할이 필요합니다"
        return c
    me = user_id
    req, rev = s.review_requested_by_id, s.reviewed_by_id
    if s.status == STATUS_DRAFT:
        c.edit = c.submit = True
    elif s.status == STATUS_REVIEW:
        path = s.review_path
        c.withdraw = me == req
        if path == PATH_LEAD_THEN_MASTER and rev is None:
            c.review = t == 2 and me != req
            c.review_return = c.review
            if not c.review:
                c.why["review"] = ("검토 요청자는 본인 검토를 할 수 없습니다" if me == req
                                   else "책임관리자가 검토합니다")
            c.why["approve"] = "책임관리자 검토가 끝나야 승인할 수 있습니다"
        elif path in (PATH_LEAD_THEN_MASTER, PATH_MASTER):
            c.approve = t == 3 and me != req and me != rev
            c.review_return = c.approve
            if not c.approve:
                c.why["approve"] = ("작성(검토 요청)자·검토자는 승인할 수 없습니다 — 자기 승인 금지" if me in (req, rev)
                                    else "마스터관리자가 승인합니다")
        elif path == PATH_EXTERNAL:
            c.external_approve = True   # 기록 행위 — 일반 이상 누구나(ADR-0038 §2.2.1)
            c.why["approve"] = "마스터관리자 작성분은 대표이사·이사회 승인 증빙을 등록해 확정합니다"
    elif s.status == STATUS_CONFIRMED:
        p = pending_reopen(db, s.id)
        if p is None:
            c.reopen_request = True
        else:
            if p.requested_tier >= 3:
                c.reopen_external = True
                c.why["reopen"] = "마스터관리자의 재오픈 요청은 대표이사·이사회 승인 증빙으로 처리합니다"
            else:
                c.reopen_decide = t == 3 and me != p.requested_by_id
                if not c.reopen_decide:
                    c.why["reopen"] = ("재오픈 요청자는 본인 요청을 승인할 수 없습니다" if me == p.requested_by_id
                                       else "마스터관리자가 재오픈을 승인합니다")
    return c
