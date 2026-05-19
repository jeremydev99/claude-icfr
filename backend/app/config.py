from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://icfr_user:changeme@postgres:5432/icfr_db"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "changeme"
    minio_bucket: str = "icfr-evidence"
    minio_use_ssl: bool = False
    minio_public_endpoint: str = "http://localhost:9000"

    # JWT
    jwt_secret_key: str = "please_change_this"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 30
    jwt_refresh_token_expires_days: int = 7

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    app_name: str = "ICFR System"
    app_version: str = "0.1.0"

    # Phase 0 임시 Admin 계정
    admin_email: str = "admin@acme.example"
    admin_password: str = "admin123"
    admin_display_name: str = "System Administrator"

    # CORS
    cors_allowed_origins: List[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
