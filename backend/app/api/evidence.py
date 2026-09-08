import hashlib
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import CurrentUser, get_db
from app.core.permissions import require_write, tenant_roles
from app.minio_client import build_evidence_key, get_object_stream, upload_object
from app.models.assessment import CYCLE_OPEN, AssessmentCycle
from app.models.evidence import EvidenceFile, EvidenceLink
from app.models.role_assignment import (
    POLICY_EVIDENCE_EDIT_ENABLED,
    POLICY_EVIDENCE_MAX_BYTES,
    ROLE_CONTROL_OWNER,
    ROLE_ICFR_MANAGER,
    TenantPolicy,
)
from app.models.user import User
from app.schemas.evidence import (
    EvidenceFileHistory,
    EvidenceFileRead,
    EvidenceFileUpdate,
    EvidenceLinkCreate,
    EvidenceLinkRead,
)
from app.services.role_resolver import (
    resolve_control_process_id,
    resolve_roles_for_control,
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


def _policy(db: Session, key: str) -> str | None:
    row = db.query(TenantPolicy).filter(
        TenantPolicy.policy_key == key,
        TenantPolicy.is_deleted == False,  # noqa: E712
    ).first()
    return row.policy_value if row else None


def _evidence_max_bytes(db: Session) -> int:
    """업로드 상한. **하드코딩하지 않고 정책에서 읽는다** (ADR-0032 §2.6).

    미설정이면 기존 기본값(`settings.max_upload_bytes`, 50MB)을 쓴다 — 현행 유지.
    잘못된 값에 예외를 던지지 않는다: 설정 하나가 깨졌다고 업로드 전체가 막히면 안 된다.

    §2.7 은 "크기 상한을 두지 않는다"지만, 업로드가 `file.read()` 로 전체를 메모리에
    적재하는 현재 구조에서 상한을 없애면 대용량 파일이 백엔드 메모리를 소진한다.
    **스트리밍 전환이 선행되어야 한다**(13.9-31).
    """
    raw = _policy(db, POLICY_EVIDENCE_MAX_BYTES)
    if raw is None:
        return get_settings().max_upload_bytes
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return get_settings().max_upload_bytes
    return value if value > 0 else get_settings().max_upload_bytes


def _evidence_edit_enabled(db: Session) -> bool:
    """진행 중 회차에서 통제책임자의 편집 허용 여부 (§2.5). 미설정이면 허용이 기본."""
    raw = _policy(db, POLICY_EVIDENCE_EDIT_ENABLED)
    return raw is None or raw.lower() not in ("false", "0", "no")


def _assert_can_edit_evidence(db: Session, user: User, cycle_id: UUID,
                              control_id: UUID) -> None:
    """증빙 편집 권한 — 회차 상태 + 통제 단위 역할 (ADR-0032 §2.5).

    | 회차 상태 | 통제책임자 | `icfr_manager` |
    |---|---|---|
    | 진행 중 | 가능(정책 토글) | 가능 |
    | 마감·최종승인 | **불가** | 가능 |

    마감 후 관리자 편집이 허용되는 것은 정정이 필요한 경우가 실재하기 때문이다.
    그 사실은 업로드·삭제 이력에 남는다(업로더/삭제자 계정).

    `external_auditor` 는 `require_write` 가 이미 막는다 — 여기서 다시 보지 않는다.
    권한 판정을 두 곳에 두면 어긋난다.
    """
    cycle = db.query(AssessmentCycle).filter(
        AssessmentCycle.id == cycle_id,
        AssessmentCycle.is_deleted == False,  # noqa: E712
    ).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="AssessmentCycle not found")

    is_manager = ROLE_ICFR_MANAGER in tenant_roles(db, user.id)

    if cycle.status != CYCLE_OPEN:
        if not is_manager:
            raise HTTPException(
                status_code=403,
                detail=(f"마감된 회차의 증빙은 내부회계관리자만 편집할 수 있습니다 "
                        f"(상태: {cycle.status})"),
            )
        return

    if is_manager:
        return

    if not _evidence_edit_enabled(db):
        raise HTTPException(
            status_code=403,
            detail="증빙 편집이 비활성화되어 있습니다 (정책: evidence_edit_enabled)",
        )

    # 통제 단위 판정 — "이 사람이 통제책임자인가"가 아니라 "이 통제에서 통제책임자인가"
    process_id = resolve_control_process_id(db, control_id)
    resolved = resolve_roles_for_control(db, control_id, process_id)
    owner = next((r["user_id"] for r in resolved if r["role_name"] == ROLE_CONTROL_OWNER), None)
    if owner != user.id:
        raise HTTPException(
            status_code=403,
            detail="이 통제의 통제책임자만 증빙을 편집할 수 있습니다",
        )


# ── Evidence Files ─────────────────────────────────────────

@router.get("/files")
def list_files(skip: int = 0, limit: int = 100, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
    q = db.query(EvidenceFile).filter(EvidenceFile.is_deleted == False)  # noqa: E712
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"items": [EvidenceFileRead.model_validate(i) for i in items], "total": total, "skip": skip, "limit": limit}


@router.post("/files", status_code=status.HTTP_201_CREATED, response_model=EvidenceFileRead)
async def create_file(
    cycle_id: UUID = Form(...),
    control_id: UUID = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_write),
    db: Session = Depends(get_db),
) -> EvidenceFile:
    """증빙 업로드 — **통제 × 회차**에 붙는다 (ADR-0032 §2.7).

    **`cycle_id`·`control_id` 는 핸들러에서 필수로 막는다. DB 제약이 아니다.**
    컬럼이 nullable 인 것은 기존 4건(시드·테스트 잔재) 때문이며, NOT NULL 로 만들면
    그 4건을 지우거나 값을 지어내야 한다 — 실데이터 조작을 하지 않기로 확정했다
    (13.9-29). 그래서 "레거시는 NULL 을 허용하되 **신규는 만들지 않는다**"를
    핸들러가 담당한다.

    권한은 §2.5 — 회차 상태와 통제 단위 역할 양쪽을 본다.
    """
    _assert_can_edit_evidence(db, user, cycle_id, control_id)

    data = await file.read()

    max_bytes = _evidence_max_bytes(db)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"파일 크기 초과 (최대 {max_bytes // 1024 // 1024}MB)",
        )

    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"허용되지 않는 파일 형식: {content_type}")

    obj = EvidenceFile(
        filename=file.filename,
        mime_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by_id=user.id,
        cycle_id=cycle_id,
        control_id=control_id,
    )
    db.add(obj)
    db.flush()   # id 확보 — 경로가 내부 식별자를 쓴다(§2.3)

    # 경로는 build_evidence_key 만 만든다. tenant_id 는 그 함수가 컨텍스트에서 가져온다
    obj.minio_key = build_evidence_key(cycle_id, control_id, obj.id)
    upload_object(obj.minio_key, data, content_type)

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
def delete_file(file_id: UUID, reason: str | None = None,
                user: User = Depends(require_write),
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
    # 레거시 증빙(cycle_id NULL)은 회차 판정을 걸 수 없다 — require_write 만 적용된다
    if obj.cycle_id and obj.control_id:
        _assert_can_edit_evidence(db, user, obj.cycle_id, obj.control_id)
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
