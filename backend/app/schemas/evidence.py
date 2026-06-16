from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class EvidenceFileBase(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    size_bytes: int
    minio_key: str | None = None
    sha256: str | None = None

class EvidenceFileCreate(EvidenceFileBase):
    pass

class EvidenceFileUpdate(BaseModel):
    filename: str | None = Field(None, min_length=1, max_length=255)
    minio_key: str | None = None

class EvidenceFileRead(EvidenceFileBase):
    id: UUID
    uploaded_by_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


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
