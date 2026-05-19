from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.config import get_settings

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/", status_code=status.HTTP_200_OK)
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/db", status_code=status.HTTP_200_OK)
def health_db(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "postgres"}
    except Exception as e:
        return {"status": "error", "service": "postgres", "detail": str(e)}


@router.get("/storage", status_code=status.HTTP_200_OK)
def health_storage() -> dict:
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError
    settings = get_settings()
    try:
        endpoint = f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}"
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.minio_root_user,
            aws_secret_access_key=settings.minio_root_password,
            region_name="us-east-1",
        )
        s3.list_buckets()
        return {"status": "ok", "service": "minio"}
    except (ClientError, EndpointConnectionError) as e:
        return {"status": "error", "service": "minio", "detail": str(e)}
