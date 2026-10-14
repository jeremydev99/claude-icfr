"""회계연도 RCM 확정 결재 (ADR-0038 2-5) — 공통 결재 흐름(`approval_flow`)에 RCM 동작을 붙인다.

- 회계연도 RCM 문서(`RcmFiscalYear`)가 결재 대상. 승인하면 **그 시점의 라이브 RCM 전체를 스냅샷**으로 남긴다.
- **잠금**(2026-10-07 마스터 Q1): 가장 최근 회계연도 RCM 이 검토 중·확정이면 라이브 RCM 쓰기 전부 409.
  바꾸려면 재오픈(요청 → 다른 마스터 승인, 버전 +1) 후 수정·재결재 → 새 스냅샷. 다음 연도 RCM 을 시작하면 다시 열린다.
- 검토 요청 전 점검: 상신된 통제 변경 결재(13.9-95)가 남아 있으면 409 — 끝내거나 회수한 뒤.
- 결재 없이 바로 바뀌는 쓰기(통제 생성·삭제, 상위 계층, 어서션, 엑셀)를 변경 결재로 넘기는 일은 별도 항목(Q3).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.governance_log import _json
from app.models.control_change import CH_DEPT_APPROVED, CH_DEPT_REVIEW, CH_IN_BATCH, ControlChange
from app.models.governance import (
    AS_DRAFT,
    ENTITY_RCM_YEAR,
    PATH_EXTERNAL,
    PATH_LEAD_THEN_MASTER,
    PATH_MASTER,
)
from app.models.rcm_governance import RcmFiscalYear, RcmSnapshot
from app.services import approval_flow, control_resolver
from app.services.approval_flow import DocHooks, FlowError

SUBMITTED_CHANGES = (CH_DEPT_REVIEW, CH_DEPT_APPROVED, CH_IN_BATCH)


def latest_year(db: Session) -> RcmFiscalYear | None:
    return db.query(RcmFiscalYear).filter(RcmFiscalYear.is_deleted == False).order_by(  # noqa: E712
        RcmFiscalYear.fiscal_year.desc()).first()


def pending_changes(db: Session) -> int:
    return db.query(ControlChange).filter(ControlChange.status.in_(SUBMITTED_CHANGES),
                                          ControlChange.is_deleted == False).count()  # noqa: E712


def build_snapshot(db: Session, fiscal_year: int, version: int) -> dict:
    processes, sub_processes, risks = control_resolver.resolve_hierarchy(db)
    controls = control_resolver.resolve_controls(db)
    return _json({
        "fiscal_year": fiscal_year, "version": version, "taken_at": datetime.now(UTC),
        "processes": processes, "sub_processes": sub_processes, "risks": risks, "controls": controls,
        "assertion_links": control_resolver.resolve_control_assertion_links(db),
    })


def hooks(db: Session, y: RcmFiscalYear) -> DocHooks:
    def check_submit() -> None:
        n = pending_changes(db)
        if n:
            raise FlowError(409, f"상신된 통제 변경 결재 {n}건이 남아 있습니다 — 결재를 끝내거나 회수한 뒤 검토 요청하세요")
        latest = latest_year(db)
        if latest is not None and latest.id != y.id:
            raise FlowError(409, f"가장 최근 회계연도({latest.fiscal_year}) RCM 만 결재할 수 있습니다")

    def confirm(uid, _reason: str) -> None:
        st = approval_flow.get_state(db, ENTITY_RCM_YEAR, y.id)
        version = st.version if st is not None else 1
        editors = list((st.editor_ids if st is not None else None) or [])
        # 이번 판을 바로 고친 사람은 그 판을 승인할 수 없다(13.9-127) — 작성자·승인자 분리
        if str(uid) in editors:
            raise FlowError(409, "이번 판 RCM 을 직접 수정한 사람은 승인할 수 없습니다 — 다른 마스터관리자 또는 대표이사·이사회 승인 증빙으로 확정하세요")
        snap = build_snapshot(db, y.fiscal_year, version)
        snap["editor_ids"] = editors
        db.add(RcmSnapshot(rcm_year_id=y.id, fiscal_year=y.fiscal_year, version=version, snapshot=snap,
                           control_count=len(snap["controls"]), confirmed_by_id=uid, confirmed_at=datetime.now(UTC)))

    def reopen(_uid, _reason: str) -> None:
        st = approval_flow.get_state(db, ENTITY_RCM_YEAR, y.id)
        if st is not None:
            st.editor_ids = None    # 새 판 — 수정자를 처음부터 모은다

    def adjust_path(path: str) -> str:
        """승인할 마스터가 모두 이번 판 수정자면 대표이사·이사회 승인 증빙으로(마스터 작성분과 같은 경로)."""
        if path not in (PATH_MASTER, PATH_LEAD_THEN_MASTER):
            return path
        st = approval_flow.get_state(db, ENTITY_RCM_YEAR, y.id)
        editors = set((st.editor_ids if st is not None else None) or [])
        if editors and not (_master_ids(db) - editors):
            return PATH_EXTERNAL
        return path

    return DocHooks(entity_type=ENTITY_RCM_YEAR, entity_id=y.id, is_confirmed=lambda: False,
                    check_submit=check_submit, confirm=confirm, reopen=reopen, adjust_path=adjust_path)


def _master_ids(db: Session) -> set[str]:
    from app.models.role_assignment import ROLE_ICFR_MANAGER
    from app.models.user_mgmt import UserRole
    return {str(r.user_id) for r in db.query(UserRole).filter(UserRole.role_name == ROLE_ICFR_MANAGER,
                                                              UserRole.is_deleted == False).all()}  # noqa: E712


def mark_editors(db: Session, user_ids) -> None:
    """작성 중인 가장 최근 회계연도 RCM 에 '이번 판 수정자'를 더한다(13.9-127). 회계연도 RCM 이 없으면 아무것도 안 한다.
    호출하는 쪽이 커밋한다 — 쓰기가 실패해 롤백되면 기록도 함께 사라진다."""
    y = latest_year(db)
    if y is None:
        return
    h = hooks(db, y)
    if approval_flow.view_state(db, h).status != AS_DRAFT:
        return
    st = approval_flow._ensure_state(db, h)
    cur = list(st.editor_ids or [])
    for u in user_ids:
        if u and str(u) not in cur:
            cur.append(str(u))
    st.editor_ids = cur     # JSON 은 새 객체를 넣어야 변경이 감지된다


def editor_ids(db: Session, y: RcmFiscalYear) -> list[str]:
    st = approval_flow.get_state(db, ENTITY_RCM_YEAR, y.id)
    return list((st.editor_ids if st is not None else None) or [])


def lock_reason(db: Session) -> str | None:
    """라이브 RCM 이 잠겼으면 그 이유, 아니면 None."""
    y = latest_year(db)
    if y is None:
        return None
    st = approval_flow.view_state(db, hooks(db, y))
    if st.status == AS_DRAFT:
        return None
    what = "검토 중" if st.status == "review" else f"확정(v{st.version})"
    return (f"{y.fiscal_year} 회계연도 RCM 이 {what}이라 RCM 을 바꿀 수 없습니다 — "
            "재오픈 요청 후 승인을 받거나, 검토 중이면 회수·반려 후 수정하세요")


def reopened_draft(db: Session) -> bool:
    """가장 최근 회계연도 RCM 이 **확정본이 있는 채로 작성 중**(재오픈 후)인가.

    이 상태의 변경은 다음 확정 결재(버전 비교 → 검토 요청 → 마스터 승인)를 반드시 거친다 — 결재 밖에서 RCM 이
    바뀌는 경로가 아니다. 엑셀 저장을 내부회계 관리자에게 여는 근거(2026-10-13, 13.9-115).
    """
    y = latest_year(db)
    if y is None:
        return False
    if approval_flow.view_state(db, hooks(db, y)).status != AS_DRAFT:
        return False
    return db.query(RcmSnapshot.id).filter(RcmSnapshot.rcm_year_id == y.id,
                                           RcmSnapshot.is_deleted == False).first() is not None  # noqa: E712


def can_upload_excel(db: Session, user_id) -> bool:
    """RCM 엑셀 **저장** 자격 — 내부회계관리자(바로 반영), 또는 재오픈 작성 중이면 내부회계 관리자 1~3단계.

    작성(일반·책임)과 승인(마스터)을 나누기 위해서다 — 마스터가 올리고 마스터가 승인하면 자기 변경을 자기가
    승인하게 된다(2026-10-13 Regina). 외부 자문(`external_advisor`)은 포함하지 않는다.
    """
    from app.core.permissions import tenant_roles
    from app.models.role_assignment import TIER_ROLES
    from app.services.control_changes import direct_edit_allowed

    if direct_edit_allowed(db, user_id):
        return True
    return bool(tenant_roles(db, user_id) & set(TIER_ROLES)) and reopened_draft(db)


def ensure_rcm_editable(db: Session) -> None:
    why = lock_reason(db)
    if why:
        raise FlowError(409, why)
