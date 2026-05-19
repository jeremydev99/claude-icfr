# ICFR_backend_1_20260519.md — Phase 0 작업2: FastAPI 백엔드 골조

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-19 |
| 작업 유형 | 백엔드 골조 (FastAPI + DB + Alembic + JWT) |
| 담당 | TrustBuilder |
| Phase | Phase 0 — 작업 단위 2 |
| 결정 출처 | claude.ai 사전 승인 (Step B 옵션 A) |
| 예상 작업 시간 | 1~1.5시간 |
| 영향 파일 | `backend/` 폴더 전체 신규 생성 (약 25~30개 파일) + `docker-compose.yml` 활성화 + `.github/workflows/ci.yml` 활성화 |
| 커밋 메시지 제안 | `feat(backend): FastAPI 프로젝트 + DB + Alembic + JWT 골조 (Phase 0 작업2)` |

---

## 작업 지시

`ClaudeICFR.md` (특히 섹션 3 기술 스택, 섹션 5 데이터 모델, 섹션 10 ADR-0008·0011·0015·0017·0018, 섹션 19 API 명세 표준), `CLAUDE.md` (특히 섹션 9 명세 동기화 체크)를 먼저 확인하고, 아래 백엔드 골조를 순서대로 생성해줘.

**핵심 결정사항** (재확인):
- 동기 SQLAlchemy 2.x (sync, asyncio 미사용)
- Phase 0 임시 admin 계정 자동 생성 (env에서 비밀번호 관리)
- 모든 PK는 Surrogate UUID + 자연키 별도 컬럼 (ADR-0015)
- role 값은 소문자 (`admin`, `user`) — 코드·식별자 컨벤션 (ADR-0018)
- JWT Access Token 30분, Refresh Token 7일 (ADR-0011)
- API 표준은 섹션 19 준수 (URL 패턴, snake_case, JWT Bearer, ISO 8601, 에러 `{"detail": "..."}`)

---

## 1. backend/ 폴더 구조 생성

```
backend/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── alembic.ini
├── README.md
├── .dockerignore
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── deps.py
│   │   └── exceptions.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   └── common.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── auth.py
│   └── seeds/
│       ├── __init__.py
│       └── bootstrap.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_health.py
```

---

## 2. requirements.txt

```
# Core
fastapi==0.115.*
uvicorn[standard]==0.32.*
pydantic==2.9.*
pydantic-settings==2.6.*

# Database
sqlalchemy==2.0.*
alembic==1.13.*
psycopg[binary]==3.2.*

# Auth & Security
python-jose[cryptography]==3.3.*
passlib[bcrypt]==1.7.*
python-multipart==0.0.*
bcrypt==4.2.*

# Storage
boto3==1.35.*

# HTTP Client
httpx==0.27.*

# Testing
pytest==8.3.*
pytest-cov==5.0.*

# Linting
ruff==0.7.*
```

---

## 3. pyproject.toml

```toml
[project]
name = "icfr-backend"
version = "0.1.0"
description = "ICFR System Backend"
requires-python = ">=3.12"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
addopts = "-v --cov=app --cov-report=term-missing"
```

---

## 4. app/config.py — 환경 변수 설정

`pydantic-settings`로 `.env` 자동 로드. 다음 필드 포함:

- DB 접속: `database_url`
- MinIO: `minio_endpoint`, `minio_root_user`, `minio_root_password`, `minio_bucket`, `minio_use_ssl`, `minio_public_endpoint`
- JWT: `jwt_secret_key`, `jwt_algorithm`, `jwt_access_token_expires_minutes`, `jwt_refresh_token_expires_days`
- App: `environment`, `log_level`, `app_name`, `app_version`
- Admin 시드: `admin_email` (기본 `admin@acme.example`), `admin_password` (기본 `admin123`, .env에서 변경 가능), `admin_display_name` (기본 `System Administrator`)
- CORS: `cors_allowed_origins` (기본 `["http://localhost:5173"]`)

`Settings` 클래스를 싱글톤으로 사용 (`get_settings()` 함수 + `@lru_cache`).

`.env.example`과 `.env`에 admin 관련 항목 추가:
```
# === Phase 0 임시 Admin 계정 ===
ADMIN_EMAIL=admin@acme.example
ADMIN_PASSWORD=admin123
ADMIN_DISPLAY_NAME=System Administrator
```

---

## 5. app/core/database.py — SQLAlchemy 엔진·세션

- SQLAlchemy 2.x 동기 엔진 생성 (`create_engine`)
- `DATABASE_URL` 형식: `postgresql+psycopg://...` (psycopg3 사용)
- `SessionLocal` 팩토리
- FastAPI 의존성으로 사용할 `get_db()` 제너레이터 함수

---

## 6. app/models/base.py — 공통 베이스 클래스

```python
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String, Boolean, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class Base(DeclarativeBase):
    """모든 모델의 베이스 클래스."""
    pass


class TimestampMixin:
    """생성·수정 시각 + 작성자."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SoftDeleteMixin:
    """논리 삭제."""
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class VersionMixin:
    """낙관적 잠금."""
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class UUIDPrimaryKeyMixin:
    """Surrogate UUID PK (ADR-0015)."""
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False
    )


class AuditedBase(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    """공통 감사 컬럼이 모두 포함된 베이스 — 모든 비즈니스 테이블이 이걸 상속."""
    __abstract__ = True
```

---

## 7. app/models/user.py — User 모델

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean
from app.models.base import AuditedBase


class User(AuditedBase):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

Phase 1 작업에서 employee_no(자연키), department_id, hire_date 등이 추가될 예정. Phase 0에서는 최소형.

---

## 8. app/core/security.py — JWT + 패스워드 해싱

- `pwd_context = CryptContext(schemes=["bcrypt"])` 설정
- `hash_password(plain) -> str`
- `verify_password(plain, hashed) -> bool`
- `create_access_token(subject, expires_delta=None) -> str`
- `create_refresh_token(subject) -> str`
- `decode_token(token) -> dict | None` (만료·서명 검증 포함)
- 토큰 페이로드: `{"sub": user_id, "exp": ..., "type": "access" | "refresh"}`

---

## 9. app/core/deps.py — 의존성 주입

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """JWT 토큰에서 현재 사용자 가져오기."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="자격 증명을 검증할 수 없습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == UUID(user_id_str), User.is_deleted == False).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 필요."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다",
        )
    return current_user
```

---

## 10. app/core/exceptions.py — 공통 예외 처리

- FastAPI의 글로벌 예외 핸들러 등록
- `RequestValidationError` → 422
- `IntegrityError` (DB 중복) → 409 `{"detail": "..."}`
- 기타 미처리 예외 → 500 (로그 출력)

응답 형식은 섹션 19 표준 `{"detail": "..."}` 준수.

---

## 11. app/schemas/auth.py — 인증 스키마

```python
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

---

## 12. app/schemas/user.py — User 스키마

- `UserRead` — 응답용 (비밀번호 제외)
- `UserCreate` — Phase 1 사용
- `UserUpdate` — Phase 1 사용

snake_case 필드, ISO 8601 시간.

---

## 13. app/schemas/common.py — 공통 응답

- `PaginationMeta` (page, size, total)
- `ErrorResponse` ({"detail": "..."})
- 추후 페이지네이션 래퍼

---

## 14. app/api/health.py — 헬스체크

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.config import get_settings


router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/", status_code=status.HTTP_200_OK)
def health() -> dict:
    """앱 헬스체크."""
    settings = get_settings()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/db", status_code=status.HTTP_200_OK)
def health_db(db: Session = Depends(get_db)) -> dict:
    """DB 연결 헬스체크."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "postgres"}
    except Exception as e:
        return {"status": "error", "service": "postgres", "detail": str(e)}


@router.get("/storage", status_code=status.HTTP_200_OK)
def health_storage() -> dict:
    """MinIO 연결 헬스체크."""
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
```

---

## 15. app/api/auth.py — 인증 라우터

엔드포인트:
- `POST /api/auth/login` (form data `username`+`password` → JWT) — OAuth2PasswordRequestForm 사용 (Swagger UI Authorize 버튼 호환)
  - `username` 필드를 이메일로 받음
  - 검증: 이메일 존재 + 패스워드 일치 + is_active + not is_deleted
  - 성공 시 `TokenResponse` (access + refresh)
  - 실패 시 401 `{"detail": "이메일 또는 비밀번호가 올바르지 않습니다"}`
- `POST /api/auth/refresh` (RefreshRequest → access token)
- `POST /api/auth/logout` (현재는 단순 200 OK 응답, 블랙리스트는 Phase 1.5+)
- `GET /api/auth/me` (현재 사용자 정보 반환, `get_current_user` 의존성)

---

## 16. app/seeds/bootstrap.py — Phase 0 임시 admin 자동 생성

앱 시작 시 호출되어 다음을 수행:
- admin 사용자가 없으면 .env의 ADMIN_EMAIL/ADMIN_PASSWORD/ADMIN_DISPLAY_NAME으로 생성
- role = "admin"
- is_active = True
- 이미 존재하면 아무 것도 안 함 (멱등성)

`bootstrap_admin(db: Session)` 함수.

> ⚠️ Phase 0 임시. Phase 1 작업6의 정식 시드(Acme Corp)에서 대체됨.

---

## 17. app/main.py — FastAPI 앱 엔트리포인트

```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.database import SessionLocal
from app.api import health, auth
from app.seeds.bootstrap import bootstrap_admin


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작·종료 시점에 실행."""
    # 시작 시: admin 시드
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version} ({settings.environment})")
    db = SessionLocal()
    try:
        bootstrap_admin(db)
        logger.info("Bootstrap admin completed")
    except Exception as e:
        logger.error(f"Bootstrap admin failed: {e}")
    finally:
        db.close()
    yield
    # 종료 시: 정리
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ICFR (Internal Control over Financial Reporting) 통합 관리 시스템 API",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router)
    app.include_router(auth.router)

    # 글로벌 예외 처리
    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request, exc: IntegrityError):
        return JSONResponse(
            status_code=409,
            content={"detail": "데이터 무결성 제약 위반 (중복 또는 참조 오류)"},
        )

    return app


app = create_app()
```

---

## 18. alembic 셋업

- `alembic init alembic` 실행
- `alembic/env.py` 수정:
  - `app.config`에서 DATABASE_URL 로드
  - `app.models.base.Base.metadata`를 target으로
  - 모든 모델 import 보장 (`from app.models import user` 등)
- `alembic.ini`에서 `sqlalchemy.url`은 env에서 동적 로드
- 첫 마이그레이션 자동 생성: `alembic revision --autogenerate -m "create users table"`
  - `alembic/versions/`에 파일 생성
  - 로컬에서 한 번 `alembic upgrade head` 실행해서 정상 적용 확인

---

## 19. backend/Dockerfile

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


FROM python:3.12-slim

WORKDIR /app

# 빌더에서 설치된 패키지 복사
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 앱 코드 복사
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# 컨테이너 내 사용 포트
EXPOSE 8000

# 시작 시 마이그레이션 후 uvicorn 실행
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

---

## 20. backend/.dockerignore

```
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
htmlcov/
.coverage
.venv/
venv/
tests/
*.md
```

---

## 21. docker-compose.yml — backend 서비스 활성화

작업1에서 주석으로 둔 backend 섹션을 활성화:

```yaml
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: icfr-backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    networks:
      - icfr-network
```

---

## 22. .github/workflows/ci.yml — backend 단계 활성화

작업1에서 주석으로 둔 단계를 활성화:

```yaml
      - name: Install backend dependencies
        working-directory: ./backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Lint with ruff
        working-directory: ./backend
        run: ruff check .
      
      - name: Run pytest
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql+psycopg://test:test@localhost:5432/test_db
          JWT_SECRET_KEY: test_secret_key
          MINIO_ENDPOINT: localhost:9000
          MINIO_ROOT_USER: test
          MINIO_ROOT_PASSWORD: test
          MINIO_BUCKET: test-bucket
          ADMIN_EMAIL: admin@test.example
          ADMIN_PASSWORD: testpass
        run: pytest
```

> CI에서 PostgreSQL 컨테이너 service도 추가 (`services:` 블록에 postgres:16-alpine).

---

## 23. tests/conftest.py — pytest fixture

- 테스트용 SQLite 인메모리 DB 또는 PostgreSQL test DB
- `TestClient` fixture
- 모델 테이블 자동 생성·삭제

---

## 24. tests/test_health.py — 헬스체크 테스트

- `GET /api/health/` → 200 + status=ok
- `GET /api/health/db` → 200 + status=ok (DB 연결됨)
- `GET /api/health/storage` → 200 (MinIO 연결 또는 error 응답)

---

## 25. backend/README.md — 백엔드 사용 안내

- 로컬 개발 (가상환경 + requirements 설치 + uvicorn 직접 실행)
- Docker로 실행 (`docker compose up -d --build`)
- Alembic 마이그레이션 사용법 (새 마이그레이션 생성, 적용, 다운그레이드)
- 테스트 실행 (`pytest`)
- API 문서 URL (http://localhost:8000/docs)
- 임시 admin 계정 정보

---

## 26. .env.example 및 .env 갱신

작업1에서 만든 `.env.example`에 다음 추가:

```env
# === Phase 0 임시 Admin 계정 ===
ADMIN_EMAIL=admin@acme.example
ADMIN_PASSWORD=admin123
ADMIN_DISPLAY_NAME=System Administrator

# === CORS ===
CORS_ALLOWED_ORIGINS=["http://localhost:5173"]
```

`.env`에도 동일 항목 반영 (로컬 개발용 값).

---

## 진행 방식

### Step 1: 사전 확인
- `ClaudeICFR.md` 섹션 19 (API 명세 표준) 재확인
- `CLAUDE.md` 섹션 9 (Contract Sync) 발동: `git fetch origin` → 원격 변경 점검
- `.env`, `.env.example` 현재 내용 확인

### Step 2: 파일 생성 (25~30개)
위 1~26 항목 순서대로 생성.

### Step 3: 로컬 검증
1. `docker compose down` (기존 컨테이너 종료)
2. `docker compose up -d --build` (backend 포함 재빌드)
3. `docker compose ps` → 3개 컨테이너 모두 healthy 확인
4. `curl http://localhost:8000/api/health/` → 200 응답 확인
5. `curl http://localhost:8000/api/health/db` → 200 응답 확인
6. `curl http://localhost:8000/api/health/storage` → 200 응답 확인
7. 브라우저로 `http://localhost:8000/docs` → Swagger UI 노출 확인
8. 로그인 테스트 (Swagger UI Authorize):
   - username: `admin@acme.example`
   - password: `admin123`
   - 토큰 발급 성공 확인
9. `GET /api/auth/me` 호출해서 admin 정보 확인

검증 실패 시 사용자에게 보고하고 수정. 모두 통과하면 다음 단계.

### Step 4: pytest 실행
- `docker compose exec backend pytest` (또는 로컬에서 venv 만들어 실행)
- 테스트 통과 확인

### Step 5: 변경 요약 + 커밋 메시지 제안
변경 요약 표 + 커밋 메시지 제안 후 사용자 OK 받으면 `git add . → git commit → git push` 진행.

커밋 메시지 제안: `feat(backend): FastAPI 프로젝트 + DB + Alembic + JWT 골조 (Phase 0 작업2)`

### Step 6: 일일 진행 로그 추가
ClaudeICFR.md 섹션 18에 한 줄 자동 추가:
```
- **TrustBuilder**: Phase 0 작업2 완료 — FastAPI 백엔드 골조 + PostgreSQL 연결 + Alembic + JWT 인증 + 임시 admin 시드. 다음: 작업3 (11개 모듈 API 골조).
```
자동 푸시 대상이지만, 같은 커밋에 포함되어 사용자 OK 후 함께 푸시.

### Step 7: ClaudeICFR.md 섹션 12·13 갱신
- 섹션 12.1: 단계 9의 진행 표시 (작업2 완료)
- 섹션 13.1: 다음 작업을 작업3으로 갱신

---

## 완료 후 알릴 것 (사용자에게)

1. ✅ Phase 0 작업2 완료 — FastAPI 백엔드 골조
2. 사용자 직접 테스트:
   - http://localhost:8000/docs (Swagger UI)
   - http://localhost:8000/api/health/ (앱 헬스)
   - http://localhost:8000/api/health/db (DB 헬스)
   - http://localhost:8000/api/health/storage (MinIO 헬스)
   - Swagger Authorize로 로그인 → `/api/auth/me` 호출
3. 다음 작업: `ICFR_backend_2_YYYYMMDD.md` (11개 모듈 폴더·API 골조)
4. Regina에게 `git pull` 안내 (선택)
