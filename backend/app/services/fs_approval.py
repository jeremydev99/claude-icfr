"""재무제표 결재 (ADR-0038 2-2) — 공통 결재 흐름(`approval_flow`)에 재무제표 동작을 붙인다.

- 검토 요청·승인 시 **검증 관문**을 다시 돈다 — 실패하면 `svc.FsValidationError`(API 422, 항목별 차이).
- 승인 = `svc.finalize`(상태 `final` + 상태 이력). 재오픈 승인 = `svc.reopen`. `fs_statements.status` 는 그대로
  draft/final 이다 — 확정본을 읽는 곳(스코핑 생성 등)은 바뀌지 않는다. 검토 단계는 `approval_states` 에만 있다.
- 업로드의 "확정" 옵션은 **검토 요청**으로 바뀌었다 — 결재 없이 확정되는 경로를 없앤다.
- 원칙적으로 수정 불가(§3.1) — 재오픈은 명백한 수정 사유가 있을 때만. 경로 자체는 §2.3 그대로.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.financial_statement import FS_STATUS_DRAFT, FS_STATUS_FINAL, FsStatement
from app.models.governance import ENTITY_FS_STATEMENT
from app.services import approval, approval_flow
from app.services import financial_statement as svc
from app.services.approval_flow import DocHooks, FlowError

UPLOAD_SUBMIT_REASON = "업로드 후 검토 요청 — 최신 연도 검증 통과"


def hooks(db: Session, st: FsStatement) -> DocHooks:
    def check_submit() -> None:
        if st.status != FS_STATUS_DRAFT:
            raise FlowError(409, "작성 중인 재무제표만 검토 요청할 수 있습니다")
        result = svc.validate(db, st)
        if not result["ok"]:
            raise svc.FsValidationError(result)

    return DocHooks(
        entity_type=ENTITY_FS_STATEMENT, entity_id=st.id,
        is_confirmed=lambda: st.status == FS_STATUS_FINAL,
        check_submit=check_submit,
        confirm=lambda uid, reason: svc.finalize(db, st, uid, reason),
        reopen=lambda uid, reason: svc.reopen(db, st, uid, reason),
    )


def submit_after_upload(db: Session, st: FsStatement, actor_id: UUID) -> bool:
    """업로드·결합 직후 검토 요청 — 내부회계 관리자(1~3단계)만. 못 하면 작성 중으로 둔다(오류 아님)."""
    if approval.user_tier(db, actor_id) == 0:
        return False
    try:
        approval_flow.submit(db, hooks(db, st), actor_id, UPLOAD_SUBMIT_REASON)
    except (FlowError, svc.FsValidationError):
        return False
    return True
