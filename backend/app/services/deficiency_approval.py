"""미비점 평가 결재 (ADR-0038 2-3) — 공통 결재 흐름(`approval_flow`)에 미비점 동작을 붙인다.

- 결재 단위 = 미비점 1건의 **평가 결론**(심각도 + 최종 결론). 검토 요청에는 둘 다 필요하다.
- 승인하면 서버가 `confirmed_at`·`confirmed_by_id` 를 기록한다 — 이 칸은 API 로 직접 쓸 수 없다(2026-10-07,
  예전 PATCH 는 누구나 확정자를 임의로 적을 수 있었다).
- **확정 후 재오픈 없음**(ADR-0038 §3.1) — 이후 개선은 개선계획·다음 차수 평가로. 정정은 새 미비점으로 다시 평가한다.
- 잠그는 것은 평가 결론뿐이다. `status`(진행 중·종결)는 개선 진행 상태라 확정 후에도 바뀐다.
- 확정돼 있는데 결재 상태 행이 없으면 **이전 방식 확정**(PATCH 로 confirmed_at 이 적힌 건, Q3 고정).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.governance import AS_DRAFT, ENTITY_DEFICIENCY
from app.models.remediation import Deficiency
from app.services import approval_flow
from app.services.approval_flow import DocHooks, FlowError

# 결론 칸 — 검토 중·확정이면 바꿀 수 없다. status 는 여기 없다(개선 진행 상태)
LOCKED_FIELDS = {"severity", "description", "final_conclusion", "fiscal_year", "control_id", "test_run_id", "code"}
NO_REOPEN = "확정된 미비점 평가는 재오픈하지 않습니다 — 이후 개선은 개선계획·다음 차수 평가로, 정정은 새 미비점으로 평가하세요"


def hooks(db: Session, d: Deficiency) -> DocHooks:
    def check_submit() -> None:
        if d.confirmed_at is not None:
            raise FlowError(409, "이미 확정된 미비점입니다")
        if not d.severity or not (d.final_conclusion or "").strip():
            raise FlowError(422, "심각도와 최종 결론을 먼저 입력하세요")

    def confirm(uid, _reason: str) -> None:
        d.confirmed_at, d.confirmed_by_id = datetime.now(UTC), uid

    def reopen(_uid, _reason: str) -> None:
        raise FlowError(409, NO_REOPEN)

    return DocHooks(entity_type=ENTITY_DEFICIENCY, entity_id=d.id, is_confirmed=lambda: d.confirmed_at is not None,
                    check_submit=check_submit, confirm=confirm, reopen=reopen)


def approval_status(db: Session, d: Deficiency) -> str:
    return approval_flow.view_state(db, hooks(db, d)).status


def ensure_editable(db: Session, d: Deficiency, fields: set[str]) -> None:
    """결론 칸을 바꾸거나 지우려 할 때 — 작성 중이 아니면 409."""
    if fields & LOCKED_FIELDS and approval_status(db, d) != AS_DRAFT:
        raise FlowError(409, "검토 중이거나 확정된 미비점은 평가 내용을 바꿀 수 없습니다"
                        + (" — 회수·반려 후 수정하세요" if d.confirmed_at is None else ""))
