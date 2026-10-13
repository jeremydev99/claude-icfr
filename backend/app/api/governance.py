"""거버넌스 공통 — 내 결재 대기·외부 승인 증빙 내려받기 (ADR-0038).

결재 대기 판정은 `services/approval.can` 을 그대로 쓴다 — 화면 버튼과 대기 목록이 같은 규칙을 본다.
"""
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import tenant_roles
from app.minio_client import get_object_stream
from app.models.ai_proposal import AI_PROPOSED, KIND_LABELS, AiProposal
from app.models.assessment import CYCLE_CLOSED, AssessmentCycle
from app.models.control_change import (
    B_REVIEW,
    CH_DEPT_APPROVED,
    CH_DEPT_REVIEW,
    CH_REJECTED,
    ControlChange,
    ControlChangeBatch,
)
from app.models.financial_statement import FS_BASIS_LABELS, FS_STATEMENT_LABELS, FsStatement
from app.models.governance import (
    AS_CONFIRMED,
    AS_REVIEW,
    ENTITY_ASSESSMENT_CYCLE,
    ENTITY_DEFICIENCY,
    ENTITY_FS_STATEMENT,
    ENTITY_RCM_YEAR,
    ApprovalState,
    GovernanceFile,
)
from app.models.proposal import P_PENDING_REVIEW, P_REVIEWED, Proposal
from app.models.rcm_governance import RcmFiscalYear
from app.models.remediation import Deficiency
from app.models.role_assignment import ROLE_ICFR_MANAGER
from app.models.schedule import PLAN_REVIEW, SchedulePlan
from app.models.scoping import STATUS_CONFIRMED, STATUS_REVIEW, Scoping
from app.services import approval, cycle_approval
from app.services import proposals as proposal_svc
from app.services import schedule as schedule_svc

router = APIRouter(prefix="/api/governance", tags=["governance"])


class InboxItem(BaseModel):
    entity_type: str
    entity_id: UUID
    title: str
    action: str        # review | approve | external_approve | reopen_decide | reopen_external
    label: str
    path: str          # 화면 경로


@router.get("/inbox", response_model=list[InboxItem])
def inbox(user: CurrentUser, db: Session = Depends(get_db)) -> list[InboxItem]:
    """지금 내가 처리할 결재 — 검토·승인·외부 승인 등록·재오픈 결정."""
    if approval.user_tier(db, user.id) == 0:
        return _work_items(db, user)   # 조직장·작성자 — 관리자 단계가 없어도 통제 변경 결재·반려 건은 있다
    out: list[InboxItem] = []
    rows = db.query(Scoping).filter(Scoping.is_deleted == False,  # noqa: E712
                                    Scoping.status.in_([STATUS_REVIEW, STATUS_CONFIRMED])).all()
    for s in rows:
        c = approval.can(db, s, user.id)
        title = f"{s.fiscal_year} 회계연도 스코핑"
        for flag, action, label in [
            (c.review, "review", "책임관리자 검토"),
            (c.approve, "approve", "승인(확정)"),
            (c.external_approve, "external_approve", "대표이사·이사회 승인 증빙 등록"),
            (c.reopen_decide, "reopen_decide", "재오픈 승인 여부 결정"),
            (c.reopen_external, "reopen_external", "재오픈 외부 승인 증빙 등록"),
        ]:
            if flag:
                out.append(InboxItem(entity_type="scoping", entity_id=s.id, title=title, action=action,
                                     label=label, path="/scoping"))
    # 공통 결재 상태(2-1)를 쓰는 문서 — 재무제표(2-2)
    for st in db.query(ApprovalState).filter(ApprovalState.entity_type.in_([ENTITY_FS_STATEMENT, ENTITY_DEFICIENCY]),
                                             ApprovalState.is_deleted == False,  # noqa: E712
                                             ApprovalState.status.in_([AS_REVIEW, AS_CONFIRMED])).all():
        if st.entity_type == ENTITY_FS_STATEMENT:
            fs = db.get(FsStatement, st.entity_id)
            if fs is None or fs.is_deleted:
                continue
            title = (f"{fs.fiscal_year} 회계연도 {FS_STATEMENT_LABELS.get(fs.statement_type, fs.statement_type)}"
                     f"({FS_BASIS_LABELS.get(fs.basis, fs.basis)})")
            path = f"/financial-statements?statement={fs.id}"
        else:
            d = db.get(Deficiency, st.entity_id)
            if d is None or d.is_deleted:
                continue
            title, path = f"미비점 {d.code} 평가 결론", f"/remediation?deficiency={d.id}"
        c = approval.can(db, st, user.id)
        for flag, action, label in [
            (c.review, "review", "책임관리자 검토"),
            (c.approve, "approve", "승인(확정)"),
            (c.external_approve, "external_approve", "대표이사·이사회 승인 증빙 등록"),
            (c.reopen_decide, "reopen_decide", "재오픈 승인 여부 결정"),
            (c.reopen_external, "reopen_external", "재오픈 외부 승인 증빙 등록"),
        ]:
            if flag:
                out.append(InboxItem(entity_type=st.entity_type, entity_id=st.entity_id, title=title, action=action,
                                     label=label, path=path))
    # 회계연도 RCM(ADR-0038 2-5)
    for st in db.query(ApprovalState).filter(ApprovalState.entity_type == ENTITY_RCM_YEAR,
                                             ApprovalState.is_deleted == False,  # noqa: E712
                                             ApprovalState.status.in_([AS_REVIEW, AS_CONFIRMED])).all():
        y = db.get(RcmFiscalYear, st.entity_id)
        if y is None or y.is_deleted:
            continue
        c = approval.can(db, st, user.id)
        for flag, action, label in [
            (c.review, "review", "책임관리자 검토"), (c.approve, "approve", "승인(확정)"),
            (c.external_approve, "external_approve", "대표이사·이사회 승인 증빙 등록"),
            (c.reopen_decide, "reopen_decide", "재오픈 승인 여부 결정"),
            (c.reopen_external, "reopen_external", "재오픈 외부 승인 증빙 등록"),
        ]:
            if flag:
                out.append(InboxItem(entity_type=ENTITY_RCM_YEAR, entity_id=y.id, title=f"{y.fiscal_year} 회계연도 RCM",
                                     action=action, label=label, path="/rcm?tab=year"))
    # 평가 회차 최종승인(ADR-0038 2-4) — 마감된 회차
    for cy in db.query(AssessmentCycle).filter(AssessmentCycle.status == CYCLE_CLOSED,
                                               AssessmentCycle.is_deleted == False).all():  # noqa: E712
        c = cycle_approval.can(db, cy, user.id)
        for flag, action, label in [(c.approve, "approve", "회차 최종승인"),
                                    (c.external_approve, "external_approve", "대표이사·이사회 승인 증빙 등록")]:
            if flag:
                out.append(InboxItem(entity_type=ENTITY_ASSESSMENT_CYCLE, entity_id=cy.id, title=f"평가 회차 {cy.name}",
                                     action=action, label=label, path=f"/schedule?cycle={cy.id}"))
    for p in db.query(Proposal).filter(Proposal.is_deleted == False,  # noqa: E712
                                       Proposal.status.in_([P_PENDING_REVIEW, P_REVIEWED])).all():
        c = proposal_svc.can(db, p, user.id)
        if c.decide or c.review_done:
            out.append(InboxItem(entity_type="proposal", entity_id=p.id, title=p.title, action="proposal_review",
                                 label="1차 승인(항목별 검토)", path=f"/proposals/{p.id}"))
        elif c.approve:
            out.append(InboxItem(entity_type="proposal", entity_id=p.id, title=p.title, action="proposal_approve",
                                 label="2차 승인", path=f"/proposals/{p.id}"))
    out.extend(_work_items(db, user))
    return out



def _work_items(db: Session, user) -> list[InboxItem]:
    """관리자 단계와 무관하게 사람에게 걸리는 결재·할 일 — 통제 변경(13.9-95)·연간 일정안(13.9-93)."""
    out: list[InboxItem] = []
    # 통제 변경 결재(13.9-95) — 건마다 줄을 만들면 목록이 넘치므로 단계별로 묶어 1줄씩
    ch = db.query(ControlChange).filter(ControlChange.is_deleted == False)  # noqa: E712
    dept = ch.filter(ControlChange.status == CH_DEPT_REVIEW, ControlChange.dept_approver_id == user.id).all()
    if dept:
        out.append(InboxItem(entity_type="control_change", entity_id=dept[0].id, title=f"통제 변경 {len(dept)}건",
                             action="dept_approve", label="조직장 결재", path="/rcm?tab=changes"))
    tier = approval.user_tier(db, user.id)
    if tier >= 1:
        queued = ch.filter(ControlChange.status == CH_DEPT_APPROVED).all()
        if queued:
            out.append(InboxItem(entity_type="control_change", entity_id=queued[0].id,
                                 title=f"통제 변경 {len(queued)}건", action="batch_submit",
                                 label="내부회계 일괄 상신 대기", path="/rcm?tab=changes"))
    if ROLE_ICFR_MANAGER in tenant_roles(db, user.id):
        for b in db.query(ControlChangeBatch).filter(ControlChangeBatch.is_deleted == False,  # noqa: E712
                                                     ControlChangeBatch.status == B_REVIEW,
                                                     ControlChangeBatch.submitted_by_id != user.id).all():
            out.append(InboxItem(entity_type="control_change_batch", entity_id=b.id,
                                 title=f"통제 변경 묶음 {b.item_count}건", action="batch_decide",
                                 label="관리자 결재", path="/rcm?tab=changes"))
    rejected = ch.filter(ControlChange.status == CH_REJECTED, ControlChange.author_id == user.id).all()
    if rejected:
        out.append(InboxItem(entity_type="control_change", entity_id=rejected[0].id,
                             title=f"반려된 통제 변경 {len(rejected)}건", action="fix_rejected",
                             label="고쳐서 다시 상신", path="/rcm?tab=changes"))
    # AI 제안 채택 대기(ADR-0042) — 내부회계 관리자 단계가 채택·폐기한다
    if tier >= 1:
        for ap in db.query(AiProposal).filter(AiProposal.status == AI_PROPOSED,
                                              AiProposal.is_deleted == False).all():  # noqa: E712
            out.append(InboxItem(entity_type="ai_proposal", entity_id=ap.id,
                                 title=f"AI 제안 · {ap.fiscal_year} {KIND_LABELS.get(ap.kind, ap.kind)}",
                                 action="ai_adopt", label="검토 후 채택 또는 폐기", path="/schedule"))
    # 연간 일정안 결재(13.9-93) — 지금 단계 승인자이고 자기 승인이 아닐 때
    for p in db.query(SchedulePlan).filter(SchedulePlan.is_deleted == False,  # noqa: E712
                                           SchedulePlan.status == PLAN_REVIEW).all():
        if schedule_svc.can(db, p, user.id).approve:
            out.append(InboxItem(entity_type="schedule_plan", entity_id=p.id, title=f"{p.fiscal_year} 회계연도 일정안",
                                 action="approve", label="일정안 승인", path="/schedule"))
    return out

@router.get("/files/{file_id}")
def download_file(file_id: UUID, user: CurrentUser, db: Session = Depends(get_db)) -> StreamingResponse:
    """외부 승인 증빙 내려받기 — 테넌트 자동 필터로 다른 회사 파일은 404."""
    f = db.query(GovernanceFile).filter(GovernanceFile.id == file_id,
                                        GovernanceFile.is_deleted == False).first()  # noqa: E712
    if f is None:
        raise HTTPException(status_code=404, detail="파일이 없습니다")
    resp = get_object_stream(f.minio_key)

    def it():
        try:
            yield from resp.stream(32 * 1024)
        finally:
            resp.close()
            resp.release_conn()
    return StreamingResponse(it(), media_type=f.mime_type,
                             headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(f.filename)}"})
