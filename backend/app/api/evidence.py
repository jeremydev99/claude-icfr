import hashlib
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import CurrentUser, get_db
from app.minio_client import get_object_stream, upload_object
from app.models.evidence import EvidenceFile, EvidenceLink
from app.models.user import User
from app.schemas.evidence import (
    EvidenceFileHistory,
    EvidenceFileRead,
    EvidenceFileUpdate,
    EvidenceLinkCreate,
    EvidenceLinkRead,
)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/haansofthwp",
    "application/x-hwp",
}


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    return {
        "module": "evidence",
        "name_kr": "증빙 관리",
        "phase_0_status": "최소 CRUD 완료",
        "phase_1_features": ["파일 업로드/다운로드 (MinIO)", "모듈 연결 (RCM·Test·개선계획)", "단순 검색 (파일명·태그)"],
        "phase_1_excluded": ["PBC 빌더", "보존기간 알림"],
        "available_in_phase_1": True,
    }


# ── Evidence Files ─────────────────────────────────────────

@router.get("/files")
def list_files(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(EvidenceFile).filter(EvidenceFile.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [EvidenceFileRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/files", status_code=status.HTTP_201_CREATED, response_model=EvidenceFileRead)
async def create_file(
    file: UploadFile = File(...),
    user: CurrentUser = None,
    db: Session = Depends(get_db),
) -> EvidenceFile:
    settings = get_settings()

    data = await file.read()

    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"파일 크기 초과 (최대 {settings.max_upload_bytes // 1024 // 1024}MB)")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"허용되지 않는 파일 형식: {content_type}")

    sha256 = hashlib.sha256(data).hexdigest()
    minio_key = f"{uuid4()}/{file.filename}"

    upload_object(minio_key, data, content_type)

    obj = EvidenceFile(
        filename=file.filename,
        mime_type=content_type,
        size_bytes=len(data),
        minio_key=minio_key,
        sha256=sha256,
        uploaded_by_id=user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/files/{file_id}", response_model=EvidenceFileRead)
def get_file(file_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> EvidenceFile:
    obj = db.query(EvidenceFile).filter(EvidenceFile.id == file_id, EvidenceFile.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="EvidenceFile not found")
    return obj


@router.get("/files/{file_id}/download")
def download_file(file_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)):
    obj = db.query(EvidenceFile).filter(EvidenceFile.id == file_id, EvidenceFile.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="EvidenceFile not found")
    if not obj.minio_key:
        raise HTTPException(status_code=409, detail="파일 본체 없음 (레거시 메타)")

    response = get_object_stream(obj.minio_key)

    def iterfile():
        try:
            yield from response.stream(32 * 1024)
        finally:
            response.close()
            response.release_conn()

    encoded = quote(obj.filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}
    return StreamingResponse(iterfile(), media_type=obj.mime_type, headers=headers)


@router.patch("/files/{file_id}", response_model=EvidenceFileRead)
def update_file(file_id: UUID, body: EvidenceFileUpdate, user: CurrentUser = None, db: Session = Depends(get_db)) -> EvidenceFile:
    obj = db.query(EvidenceFile).filter(EvidenceFile.id == file_id, EvidenceFile.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="EvidenceFile not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: UUID, reason: str | None = None, user: CurrentUser = None,
                db: Session = Depends(get_db)) -> None:
    """삭제 표시만 한다. **MinIO 파일을 지우지 않는다** (ADR-0032 §2.4).

    증빙은 감사 증거물이다. 레코드만 남기고 파일을 지우면 "그때 지운 게 뭐였나"에
    답할 수 없고, 보존기간이 5년 이상이므로 파일도 그 기간을 따른다(§2.9).

    **2026-09-04 수정 전에는 `remove_object_safe` 로 파일을 실제 삭제했다.**
    운영 실측에서 `is_deleted=true` 인 2건의 MinIO 객체가 이미 사라져 있었다 —
    테스트 파일이라 손실은 없었으나 동작이 그대로면 실증빙에서 같은 일이 난다.
    """
    obj = db.query(EvidenceFile).filter(EvidenceFile.id == file_id, EvidenceFile.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="EvidenceFile not found")
    obj.is_deleted = True
    obj.deleted_by_id = user.id
    obj.deleted_at_ts = datetime.now(UTC)
    obj.delete_reason = reason
    db.commit()


@router.get("/files/{file_id}/history", response_model=EvidenceFileHistory)
def get_file_history(file_id: UUID, user: CurrentUser = None,
                     db: Session = Depends(get_db)) -> EvidenceFileHistory:
    """삭제된 증빙 포함 이력 조회 — 업로더·업로드시각·삭제자·삭제시각·사유.

    `is_deleted` 를 필터하지 않는다. **삭제된 것을 보는 것이 이 엔드포인트의 목적**이다.
    """
    obj = db.query(EvidenceFile).filter(EvidenceFile.id == file_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="EvidenceFile not found")
    names = {
        u.id: u.display_name
        for u in db.query(User).filter(
            User.id.in_({i for i in (obj.uploaded_by_id, obj.deleted_by_id) if i})
        ).all()
    }
    return EvidenceFileHistory(
        id=obj.id, filename=obj.filename, is_deleted=obj.is_deleted,
        uploaded_by_id=obj.uploaded_by_id, uploaded_by_name=names.get(obj.uploaded_by_id),
        uploaded_at=obj.created_at,
        deleted_by_id=obj.deleted_by_id,
        deleted_by_name=names.get(obj.deleted_by_id) if obj.deleted_by_id else None,
        deleted_at=obj.deleted_at_ts, delete_reason=obj.delete_reason,
        minio_key=obj.minio_key,
    )


# ── Evidence Links ─────────────────────────────────────────

@router.get("/links")
def list_links(file_id: UUID | None = None, skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(EvidenceLink).filter(EvidenceLink.is_deleted == False)  # noqa: E712
    if file_id:
        q = q.filter(EvidenceLink.file_id == file_id)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [EvidenceLinkRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/links", status_code=status.HTTP_201_CREATED, response_model=EvidenceLinkRead)
def create_link(body: EvidenceLinkCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> EvidenceLink:
    obj = EvidenceLink(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(EvidenceLink).filter(EvidenceLink.id == link_id, EvidenceLink.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="EvidenceLink not found")
    obj.is_deleted = True
    db.commit()
