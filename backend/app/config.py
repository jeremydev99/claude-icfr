from functools import lru_cache

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
    # 7 → 1 (보안 1단계, 2026-10-01 사외 접속 허용) — 분실·공용 PC 에 남은 세션이 하루를 넘기지 않게
    jwt_refresh_token_expires_days: int = 1
    # 계정 잠금 — 연속 실패 N 회면 M 분 잠금(관리자 해제·비밀번호 재설정으로도 풀린다)
    login_lock_threshold: int = 5
    login_lock_minutes: int = 15
    # MFA 의무(ADR-0039) — 외부 사용자는 처음부터, 내부 마스터·책임관리자는 이 날짜부터(30일 유예)
    mfa_internal_required_from: str = "2026-11-02"
    # 외부 사용자 갱신 토큰(시간) — 내부(일)보다 짧게
    external_refresh_hours: int = 8

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    app_name: str = "ICFR System"
    app_version: str = "0.1.0"

    # Phase 0 임시 Admin 계정
    admin_email: str = "admin@acme.example"
    admin_password: str = "admin123"
    # display_name 은 실명 용도 — 직책명("System Administrator") 금지.
    # 운영 시 .env 의 ADMIN_DISPLAY_NAME 으로 실제 관리자 실명을 설정한다.
    admin_display_name: str = "홍길동"

    # Upload
    max_upload_bytes: int = 52428800  # 50MB

    # CORS
    cors_allowed_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
