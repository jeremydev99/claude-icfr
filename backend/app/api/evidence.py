import hashlib
from urllib.parse import quote
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import CurrentUser, get_db
from app.minio_client import get_object_stream, remove_object_safe, upload_object
from app.models.evidence import EvidenceFile, EvidenceLink
from app.schemas.evidence import (
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
            for chunk in response.stream(32 * 1024):
                yield chunk
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
def delete_file(file_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> None:
    obj = db.query(EvidenceFile).filter(EvidenceFile.id == file_id, EvidenceFile.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(status_code=404, detail="EvidenceFile not found")
    if obj.minio_key:
        remove_object_safe(obj.minio_key)
    obj.is_deleted = True
    db.commit()


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
