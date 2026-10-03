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
from app.minio_client import get_object_stream
from app.models.governance import GovernanceFile
from app.models.scoping import STATUS_CONFIRMED, STATUS_REVIEW, Scoping
from app.services import approval

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
        return []
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
