# ICFR Backend

FastAPI 기반 ICFR 시스템 백엔드.

## 빠른 시작 (Docker)

```powershell
# 레포 루트에서 실행
.\dev.ps1 up        # postgres + minio + backend 시작 (첫 실행은 빌드 포함)
.\dev.ps1 ps        # 3개 컨테이너 healthy 확인
```

API 문서: http://localhost:8000/docs

임시 admin 계정:
- Email: `admin@acme.example` (또는 .env의 ADMIN_EMAIL)
- Password: `admin123` (또는 .env의 ADMIN_PASSWORD)

## 로컬 개발 (가상환경)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# DB 마이그레이션 적용 (postgres 컨테이너 실행 중이어야 함)
$env:DATABASE_URL = "postgresql+psycopg://icfr_user:changeme_in_production@localhost:5432/icfr_db"
alembic upgrade head

# uvicorn 직접 실행
$env:DATABASE_URL = "postgresql+psycopg://icfr_user:changeme_in_production@localhost:5432/icfr_db"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Alembic 마이그레이션

```powershell
# 새 마이그레이션 생성 (모델 변경 후)
$env:DATABASE_URL = "postgresql+psycopg://icfr_user:changeme_in_production@localhost:5432/icfr_db"
alembic revision --autogenerate -m "add column xxx"

# 최신 버전으로 적용
alembic upgrade head

# 한 버전 되돌리기
alembic downgrade -1

# 현재 버전 확인
alembic current
```

## 테스트

```powershell
# 로컬 venv에서
pytest

# Docker 컨테이너 내에서
docker compose exec backend pytest
```

## 헬스체크 엔드포인트

| URL | 설명 |
|---|---|
| `GET /api/health/` | 앱 상태 |
| `GET /api/health/db` | PostgreSQL 연결 |
| `GET /api/health/storage` | MinIO 연결 |

## 11개 모듈 구조

| # | 모듈 ID | 한국어 | API prefix | 활성 Phase |
|---|---|---|---|---|
| 1 | schedule | 일정관리 | `/api/schedule` | Phase 2 |
| 2 | rcm | RCM 관리 | `/api/rcm` | Phase 1 (A-1) |
| 3 | scoping | Scoping | `/api/scoping` | Phase 2 |
| 4 | euc | EUC | `/api/euc` | Phase 3 |
| 5 | iuc | IUC | `/api/iuc` | Phase 3 |
| 6 | remediation | 개선계획 | `/api/remediation` | Phase 1 (A-1) |
| 7 | evidence | 증빙 관리 | `/api/evidence` | Phase 1 (A-1) |
| 8 | user_mgmt | 사용자/권한 | `/api/users` | Phase 1 (A-1) |
| 9 | notification | 알림 | `/api/notification` | Phase 2 |
| 10 | report | Report | `/api/report` | Phase 3 |
| 11 | test_module | Test (평가) | `/api/test` | Phase 1 (A-1) |

각 모듈은 Phase 0에서 `GET /api/{module}/info` placeholder만 노출.
Phase 1부터 단계적으로 CRUD·비즈니스 로직 추가.

시스템 전체 메타 정보:
- `GET /api/system/modules` — Frontend 메뉴 생성용 (11개 모듈 목록 + lucide-react 아이콘명)
- `GET /api/system/info` — 시스템 버전·상태

## 공통 미들웨어

- **RequestIDMiddleware**: 모든 요청에 `X-Request-ID` 부여 (외부감사 추적용)
- **AuditLogMiddleware**: 모든 API 호출을 콘솔 감사 로그 (Phase 1+에 audit_logs 테이블 저장)
- **CORS**: `cors_allowed_origins` 환경변수로 제어
- **ICFRException**: 도메인 예외를 표준 `{"detail": "..."}` 형식으로 응답

## 프로젝트 구조

```
backend/
├── app/
│   ├── main.py          # FastAPI 앱 엔트리포인트
│   ├── config.py        # 환경 변수 설정 (pydantic-settings)
│   ├── core/
│   │   ├── database.py  # SQLAlchemy 엔진·세션
│   │   ├── security.py  # JWT + 패스워드 해싱
│   │   ├── deps.py      # 의존성 주입 (get_current_user 등)
│   │   └── exceptions.py
│   ├── models/          # SQLAlchemy ORM 모델
│   ├── schemas/         # Pydantic 스키마
│   ├── api/             # FastAPI 라우터
│   └── seeds/           # 초기 데이터 시드
├── alembic/             # DB 마이그레이션
├── tests/
├── Dockerfile
└── requirements.txt
```
