import io
from datetime import timedelta
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


def presigned_download_url(object_key: str, expires_seconds: int = 900) -> str:
    url = _client.presigned_get_object(
        settings.minio_bucket,
        object_key,
        expires=timedelta(seconds=expires_seconds),
    )
    # 내부 endpoint(minio:9000)를 공개 endpoint로 치환
    internal = f"http://{settings.minio_endpoint}"
    if url.startswith(internal):
        url = settings.minio_public_endpoint + url[len(internal):]
    return url


def remove_object_safe(object_key: str) -> None:
    try:
        _client.remove_object(settings.minio_bucket, object_key)
    except S3Error:
        pass
