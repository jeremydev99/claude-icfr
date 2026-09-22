from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceFileBase(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    size_bytes: int
    minio_key: str | None = None
    sha256: str | None = None

class EvidenceFileCreate(EvidenceFileBase):
    pass

class EvidenceFileUpdate(BaseModel):
    """증빙 수정 — **파일명만.** `minio_key` 는 어떤 권한으로도 바꿀 수 없다(13.9-48).

    저장 경로를 바꾸면 증빙 레코드가 다른 파일을 가리키게 된다 — 업로드 이력·해시는 그대로인데
    내용만 바뀐다. 경로는 업로드 때 `build_evidence_key` 만 만든다. 알 수 없는 필드는 422.
    """
    model_config = ConfigDict(extra="forbid")
    filename: str | None = Field(None, min_length=1, max_length=255)

class EvidenceFileRead(EvidenceFileBase):
    id: UUID
    # 통제 × 회차 부착 (ADR-0032 §2.7). 레거시 4건은 NULL — 신규는 핸들러가 필수로 막는다
    cycle_id: UUID | None = None
    control_id: UUID | None = None
    uploaded_by_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EvidenceFileHistory(BaseModel):
    """삭제 이력 포함 조회 (ADR-0032 §2.4).

    "누가 언제 올렸다가 지웠는지"가 감사에서 실제로 묻는 질문이다.
    `minio_key` 를 함께 낸다 — 삭제 후에도 파일이 남아 있음을 확인할 수 있어야 한다.
    """
    id: UUID
    filename: str
    is_deleted: bool
    uploaded_by_id: UUID
    uploaded_by_name: str | None = None
    uploaded_at: datetime
    deleted_by_id: UUID | None = None
    deleted_by_name: str | None = None
    deleted_at: datetime | None = None
    delete_reason: str | None = None
    minio_key: str | None = None


class EvidenceLinkBase(BaseModel):
    file_id: UUID
    linked_entity_type: str = Field(min_length=1, max_length=50)
    linked_entity_id: str = Field(min_length=1, max_length=36)

class EvidenceLinkCreate(EvidenceLinkBase):
    pass

class EvidenceLinkRead(EvidenceLinkBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
