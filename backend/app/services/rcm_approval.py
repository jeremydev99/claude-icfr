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
from app.models.governance import AS_DRAFT, ENTITY_RCM_YEAR
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
        snap = build_snapshot(db, y.fiscal_year, version)
        db.add(RcmSnapshot(rcm_year_id=y.id, fiscal_year=y.fiscal_year, version=version, snapshot=snap,
                           control_count=len(snap["controls"]), confirmed_by_id=uid, confirmed_at=datetime.now(UTC)))

    return DocHooks(entity_type=ENTITY_RCM_YEAR, entity_id=y.id, is_confirmed=lambda: False,
                    check_submit=check_submit, confirm=confirm, reopen=lambda _uid, _reason: None)


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


def ensure_rcm_editable(db: Session) -> None:
    why = lock_reason(db)
    if why:
        raise FlowError(409, why)
