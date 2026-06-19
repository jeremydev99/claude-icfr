import io
from minio import Minio
from minio.error import S3Error

from app.config import get_settings

settings = get_settings()

_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_root_user,
    secret_key=settings.minio_root_password,
    secure=settings.minio_use_ssl,
)


def ensure_bucket() -> None:
    if not _client.bucket_exists(settings.minio_bucket):
        _client.make_bucket(settings.minio_bucket)


def upload_object(object_key: str, data_bytes: bytes, content_type: str) -> None:
    _client.put_object(
        settings.minio_bucket,
        object_key,
        io.BytesIO(data_bytes),
        length=len(data_bytes),
        content_type=content_type,
    )


def get_object_stream(object_key: str):
    """MinIO 객체 응답 반환. 호출측에서 stream 후 close/release_conn 책임."""
    return _client.get_object(settings.minio_bucket, object_key)


def remove_object_safe(object_key: str) -> None:
    try:
        _client.remove_object(settings.minio_bucket, object_key)
    except S3Error:
        pass
