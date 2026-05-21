from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_db
from app.models.evidence import EvidenceFile, EvidenceLink
from app.schemas.evidence import (
    EvidenceFileCreate, EvidenceFileUpdate, EvidenceFileRead,
    EvidenceLinkCreate, EvidenceLinkRead,
)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


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
def create_file(body: EvidenceFileCreate, user: CurrentUser = None, db: Session = Depends(get_db)) -> EvidenceFile:
    obj = EvidenceFile(**body.model_dump(), uploaded_by_id=user.id)
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
