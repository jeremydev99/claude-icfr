# ICFR_backend_2_20260519.md — Phase 0 작업3: 11개 모듈 API 골조 + 공통 미들웨어

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-19 |
| 작업 유형 | 백엔드 11개 모듈 라우터·모델·스키마 골조 + 공통 미들웨어 |
| 담당 | TrustBuilder |
| Phase | Phase 0 — 작업 단위 3 |
| 결정 출처 | claude.ai 사전 승인 (옵션 X — 사용자 CRUD 제외, Phase 1로 분리) |
| 예상 작업 시간 | 1.5~2시간 |
| 영향 파일 | `backend/app/api/` 12개 신규, `backend/app/models/` 11개 신규(빈 파일), `backend/app/schemas/` 11개 신규(빈 파일), `app/core/` 미들웨어 2개, `app/main.py` 갱신 |
| 커밋 메시지 제안 | `feat(backend): 11개 모듈 API 골조 + 공통 미들웨어 (Phase 0 작업3)` |

---

## 작업 지시

다음 파일들을 먼저 확인:
- `ClaudeICFR.md` 섹션 1.2 (모듈 11개), 섹션 4 (모듈별 명세), 섹션 15.3 (A-1안 모듈별 포함/제외), 섹션 19 (API 명세 표준)
- `CLAUDE.md` 섹션 9 (명세 동기화 체크)
- `backend/app/main.py` 현재 상태
- `backend/app/api/` 현재 구조

**핵심 결정** (이미 합의됨):
- Phase 0 작업3는 11개 모듈의 **API 라우터 골조만**, 실제 비즈니스 로직 없음
- 각 모듈에 placeholder 엔드포인트 1개 (`GET /api/{module}/info`)
- 모델·스키마는 빈 파일로 자리만 잡아둠 (Phase 1에서 채움)
- 사용자 CRUD는 Phase 1의 첫 모듈 작업으로 분리 (이번 작업 범위 외)
- 공통 미들웨어 3개 추가 (감사 로그, 글로벌 예외, 요청 ID)

---

## 1. 11개 모듈 정의

| # | 모듈 ID | 한국어 이름 | API prefix | Phase 1 활성? |
|---|---|---|---|---|
| 1 | `schedule` | 일정관리 | `/api/schedule` | ❌ Phase 2 |
| 2 | `rcm` | RCM 관리 | `/api/rcm` | ✅ Phase 1 (A-1) |
| 3 | `scoping` | Scoping | `/api/scoping` | ❌ Phase 2 |
| 4 | `euc` | EUC | `/api/euc` | ❌ Phase 3 |
| 5 | `iuc` | IUC | `/api/iuc` | ❌ Phase 3 |
| 6 | `remediation` | 개선계획 | `/api/remediation` | ✅ Phase 1 (A-1) |
| 7 | `evidence` | 증빙 관리 | `/api/evidence` | ✅ Phase 1 (A-1) |
| 8 | `user_mgmt` | 사용자/권한 | `/api/users` | ✅ Phase 1 (A-1) |
| 9 | `notification` | 알림 | `/api/notification` | ❌ Phase 2 |
| 10 | `report` | Report | `/api/report` | ❌ Phase 3 |
| 11 | `test_module` | Test (평가) | `/api/test` | ✅ Phase 1 (A-1) |

> 💡 **모듈명 주의**:
> - `test`는 Python 예약어와 충돌해서 모듈 파일명은 `test_module.py`
> - `user`는 작업2 User 모델과 혼란 방지 + Python 내장명 회피 위해 `user_mgmt.py`
> - URL prefix는 자연스럽게 `/api/test`, `/api/users` 사용

---

## 2. 각 모듈 라우터 파일 표준 형태

각 모듈마다 `backend/app/api/{module}.py` 생성. 표준 패턴:

### 예시 1: RCM 라우터 (`backend/app/api/rcm.py`)

```python
"""
RCM 관리 모듈 API.

Phase 0: placeholder 엔드포인트만 (인증 검증용).
Phase 1: 통제 CRUD, 검색·필터, Excel 일괄, 단순 이력 (ADR-0007 A-1안).
Phase 1.5: 버전 관리, 변경 승인 워크플로.

자세한 명세: ClaudeICFR.md 섹션 4.2 참조.
"""
from fastapi import APIRouter

from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/rcm", tags=["rcm"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """RCM 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "rcm",
        "name_kr": "RCM 관리",
        "phase_0_status": "골조만",
        "phase_1_features": [
            "통제 CRUD",
            "검색·필터 (프로세스/어써션)",
            "Excel 일괄 업로드",
            "단순 이력",
        ],
        "phase_1_excluded": [
            "버전 관리 (스냅샷·Diff)",
            "변경 승인 워크플로",
        ],
        "available_in_phase_1": True,
    }
```

### 예시 2: Schedule 라우터 (Phase 2 모듈)

```python
"""
일정관리 모듈 API.

Phase 0: placeholder 엔드포인트만.
Phase 2: 연간 평가 일정 수립, 마일스톤, 담당자 배정.

자세한 명세: ClaudeICFR.md 섹션 4.1 참조.
"""
from fastapi import APIRouter

from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/info")
def get_module_info(user: CurrentUser) -> dict:
    """일정관리 모듈 정보 — Phase 0 placeholder."""
    return {
        "module": "schedule",
        "name_kr": "일정관리",
        "phase_0_status": "골조만",
        "phase_2_features": [
            "연간 평가 일정 수립 (WBS)",
            "마일스톤 추적",
            "담당자 배정",
        ],
        "available_in_phase_1": False,
    }
```

### 표준 패턴 (모든 11개 모듈에 적용)

각 라우터마다:
1. Module docstring (한국어 + Phase 정보)
2. `router = APIRouter(prefix=..., tags=[...])`
3. `GET /info` 엔드포인트 — 인증 필요 + 모듈 정보 반환
4. Phase 1 활성 모듈은 `available_in_phase_1: True`, 나머지는 `False`

### 11개 모듈 한국어 정보 (각 라우터에 들어갈 내용)

다음 정보를 각 모듈의 `/info` 엔드포인트에 정확히 반영:

```
1. schedule (일정관리, Phase 2)
   features: 연간 평가 일정 수립 (WBS), 마일스톤, 담당자 배정

2. rcm (RCM 관리, Phase 1 A-1)
   Phase 1: 통제 CRUD, 검색·필터, Excel 일괄, 단순 이력
   Phase 1.5: 버전 관리, 변경 승인 워크플로

3. scoping (Scoping, Phase 2)
   features: 정량·정성 평가, 유의계정 식별, 평가대상 통제 산출

4. euc (EUC, Phase 3)
   features: EUC 파일 등록, SHA-256 해시 점검, 변경 감지

5. iuc (IUC, Phase 3)
   features: IUC 리포트 등록, 평가 자동 연결

6. remediation (개선계획, Phase 1 A-1)
   Phase 1: 미비점 CRUD, 단순 심각도 3단계, 개선계획 서술형, 종결 처리
   Phase 1.5: 심각도 매트릭스, 마일스톤, 이월 트래킹

7. evidence (증빙 관리, Phase 1 A-1)
   Phase 1: 업로드/다운로드, 모듈 연결, 단순 검색
   Phase 3: PBC 빌더, 보존기간 알림

8. user_mgmt (사용자/권한, Phase 1 A-1)
   Phase 1: 로그인 ID/PW, 사용자 CRUD, 단순 역할 (Admin/User)
   Phase 1.5: SoD, 위임, HR 연동

9. notification (알림, Phase 2)
   features: 이메일 (SMTP), 잔디 Webhook, 이벤트 기반 알림

10. report (Report, Phase 3)
    features: 이사회 보고서 자동 초안, PBC 패키지, 결재, 잠금

11. test_module (Test 평가, Phase 1 A-1)
    Phase 1: 평가 계획 수동 등록, 운영평가 결과 입력, Pass/Fail, 단순 검토
    Phase 1.5: 자동 샘플 추출, 자동 미비점 등록, 재테스트, 설계평가
```

---

## 3. 빈 모델·스키마 파일 (Phase 1에서 채울 자리)

각 모듈마다 빈 모델·스키마 파일을 미리 만들어 둠. Phase 1 시작 시 무엇을 어디에 추가할지 명확.

### 예시: `backend/app/models/rcm.py`

```python
"""
RCM 관리 모듈 모델.

Phase 1에서 다음 엔티티 추가 예정 (ClaudeICFR.md 섹션 5.2 그룹 B·D):
- Process
- SubProcess
- Risk
- Control
- Assertion (마스터)

자연키 명명 규칙: ClaudeICFR.md 섹션 16.4 참조.
- Process: O2C, P2P, R2R, HR, ITG
- SubProcess: {Process}-{2자 약어}
- Control: {SubProcess}-C{3자리}
- Risk: {SubProcess}-R{3자리}
"""
# from sqlalchemy.orm import Mapped, mapped_column
# from app.core.database import Base
# from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, VersionMixin

# Phase 1에서 활성화
```

### 예시: `backend/app/schemas/rcm.py`

```python
"""
RCM 관리 모듈 Pydantic 스키마.

Phase 1에서 추가 예정:
- ControlBase, ControlCreate, ControlUpdate, ControlResponse
- ProcessResponse, SubProcessResponse
- ControlListFilter, ControlBulkUploadRequest
"""
# from pydantic import BaseModel, Field, ConfigDict
# import uuid
```

### 11개 모듈 모두 동일 패턴

각 모듈의 빈 모델·스키마 파일에는:
- Module docstring (한국어, Phase별 추가 예정 내용)
- 향후 추가될 엔티티 목록 (주석)
- ClaudeICFR.md 섹션 4 또는 5.2 참조 명시

> 💡 이 빈 파일들은 Phase 1 시작 시 "어디부터 시작할지" 가이드가 됨.

---

## 4. 모듈 메타 정보 엔드포인트 (`/api/system/modules`)

새 파일 `backend/app/api/system.py` 생성. Frontend가 메뉴 생성 시 참조할 메타 정보.

```python
"""
시스템 전체 메타 정보 API.

Frontend(Regina의 영역)가 메뉴·라우트를 동적으로 생성할 때 참조.
"""
from fastapi import APIRouter

from app.core.deps import CurrentUser

router = APIRouter(prefix="/api/system", tags=["system"])


MODULES = [
    {
        "id": "schedule",
        "name_kr": "일정관리",
        "icon": "calendar",
        "phase_target": "Phase 2",
        "available_in_phase_1": False,
        "order": 1,
    },
    {
        "id": "rcm",
        "name_kr": "RCM 관리",
        "icon": "shield-check",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 2,
    },
    {
        "id": "scoping",
        "name_kr": "Scoping",
        "icon": "target",
        "phase_target": "Phase 2",
        "available_in_phase_1": False,
        "order": 3,
    },
    {
        "id": "euc",
        "name_kr": "EUC",
        "icon": "file-spreadsheet",
        "phase_target": "Phase 3",
        "available_in_phase_1": False,
        "order": 4,
    },
    {
        "id": "iuc",
        "name_kr": "IUC",
        "icon": "file-text",
        "phase_target": "Phase 3",
        "available_in_phase_1": False,
        "order": 5,
    },
    {
        "id": "remediation",
        "name_kr": "개선계획",
        "icon": "wrench",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 6,
    },
    {
        "id": "evidence",
        "name_kr": "증빙 관리",
        "icon": "paperclip",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 7,
    },
    {
        "id": "user_mgmt",
        "name_kr": "사용자/권한",
        "icon": "users",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 8,
    },
    {
        "id": "notification",
        "name_kr": "알림",
        "icon": "bell",
        "phase_target": "Phase 2",
        "available_in_phase_1": False,
        "order": 9,
    },
    {
        "id": "report",
        "name_kr": "Report",
        "icon": "file-bar-chart",
        "phase_target": "Phase 3",
        "available_in_phase_1": False,
        "order": 10,
    },
    {
        "id": "test_module",
        "name_kr": "Test (평가)",
        "icon": "clipboard-check",
        "phase_target": "Phase 1",
        "available_in_phase_1": True,
        "order": 11,
    },
]


@router.get("/modules")
def list_modules(user: CurrentUser) -> list[dict]:
    """ICFR 시스템의 11개 모듈 목록.

    Frontend가 사이드바 메뉴를 동적으로 생성할 때 참조.
    Phase별 활성 여부에 따라 UI에서 표시/숨김 결정 가능.
    """
    return MODULES


@router.get("/info")
def system_info(user: CurrentUser) -> dict:
    """시스템 전체 정보."""
    return {
        "name": "ICFR System",
        "version": "0.1.0",
        "current_phase": "Phase 0",
        "module_count": len(MODULES),
        "active_in_phase_1": sum(1 for m in MODULES if m["available_in_phase_1"]),
    }
```

> 💡 **icon 필드**: shadcn/ui와 함께 쓰이는 `lucide-react` 아이콘 이름. Regina가 작업5에서 사용.

---

## 5. 공통 미들웨어 추가

### 5.1 요청 ID 미들웨어 (`backend/app/core/middleware.py`)

새 파일 생성:

```python
"""
공통 미들웨어 — 감사 로그, 요청 ID, 글로벌 예외 처리.

ICFR 시스템은 외부감사 추적성이 필수 (ADR 다수).
"""
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("icfr.audit")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """모든 요청에 X-Request-ID 헤더 부여 + 응답에도 포함.

    외부감사 시 특정 요청을 로그에서 찾을 수 있도록.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 클라이언트가 보낸 ID가 있으면 사용, 없으면 생성
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """모든 API 호출을 감사 로그로 기록.

    Phase 0: 콘솔 로그.
    Phase 1+: audit_logs 테이블에 저장 예정 (ClaudeICFR.md 섹션 5.2 그룹 I).
    """

    EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/health"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start_time = time.time()

        # 헬스체크 등은 로그 제외 (소음 방지)
        if any(request.url.path.startswith(p) for p in self.EXCLUDED_PATHS):
            return await call_next(request)

        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        request_id = getattr(request.state, "request_id", "unknown")
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            "audit",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
        return response
```

### 5.2 글로벌 예외 처리기 (`backend/app/main.py`에 추가)

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import ICFRException


@app.exception_handler(ICFRException)
async def icfr_exception_handler(request: Request, exc: ICFRException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"X-Request-ID": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
        headers={"X-Request-ID": getattr(request.state, "request_id", "unknown")},
    )
```

---

## 6. `backend/app/main.py` 갱신

작업2의 main.py를 다음과 같이 확장:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import get_settings
from app.api import (
    health,
    auth,
    system,
    schedule,
    rcm,
    scoping,
    euc,
    iuc,
    remediation,
    evidence,
    user_mgmt,
    notification,
    report,
    test_module,
)
from app.core.exceptions import ICFRException
from app.core.middleware import RequestIDMiddleware, AuditLogMiddleware
from app.seeds.bootstrap import ensure_initial_admin

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_initial_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Middlewares (등록 순서 중요 — 가장 바깥쪽이 먼저 실행)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
@app.exception_handler(ICFRException)
async def icfr_exception_handler(request: Request, exc: ICFRException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"X-Request-ID": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
        headers={"X-Request-ID": getattr(request.state, "request_id", "unknown")},
    )


# Routers — 작업2 (인증·헬스)
app.include_router(health.router)
app.include_router(auth.router)

# Routers — 시스템 메타
app.include_router(system.router)

# Routers — 11개 모듈 (작업3)
app.include_router(schedule.router)
app.include_router(rcm.router)
app.include_router(scoping.router)
app.include_router(euc.router)
app.include_router(iuc.router)
app.include_router(remediation.router)
app.include_router(evidence.router)
app.include_router(user_mgmt.router)
app.include_router(notification.router)
app.include_router(report.router)
app.include_router(test_module.router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
```

---

## 7. 테스트 추가 (`backend/tests/test_modules.py`)

```python
"""11개 모듈 라우터 등록 + /info 엔드포인트 동작 검증."""
import pytest
from fastapi.testclient import TestClient


MODULE_PREFIXES = [
    "/api/schedule",
    "/api/rcm",
    "/api/scoping",
    "/api/euc",
    "/api/iuc",
    "/api/remediation",
    "/api/evidence",
    "/api/users",
    "/api/notification",
    "/api/report",
    "/api/test",
]


def _get_admin_token(client: TestClient) -> str:
    """admin 로그인 후 토큰 반환."""
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@acme.example", "password": "admin123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.parametrize("prefix", MODULE_PREFIXES)
def test_module_info_requires_auth(client: TestClient, prefix: str) -> None:
    """인증 없이는 401."""
    response = client.get(f"{prefix}/info")
    assert response.status_code == 401


@pytest.mark.parametrize("prefix", MODULE_PREFIXES)
def test_module_info_with_auth(client: TestClient, prefix: str) -> None:
    """admin 인증 후 정상 응답."""
    token = _get_admin_token(client)
    response = client.get(
        f"{prefix}/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "module" in data
    assert "name_kr" in data
    assert "available_in_phase_1" in data


def test_system_modules_list(client: TestClient) -> None:
    """/api/system/modules가 11개 모듈 반환."""
    token = _get_admin_token(client)
    response = client.get(
        "/api/system/modules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    modules = response.json()
    assert len(modules) == 11
    # Phase 1 A-1안: 5개 모듈 (rcm, remediation, evidence, user_mgmt, test_module)
    phase_1_active = [m for m in modules if m["available_in_phase_1"]]
    assert len(phase_1_active) == 5


def test_request_id_header(client: TestClient) -> None:
    """모든 응답에 X-Request-ID 헤더 포함."""
    response = client.get("/")
    assert "X-Request-ID" in response.headers
```

---

## 8. `backend/README.md` 갱신

기존 README에 다음 섹션 추가:

```markdown
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
- `GET /api/system/modules` — Frontend 메뉴 생성용
- `GET /api/system/info` — 시스템 버전·상태

## 공통 미들웨어
- **RequestIDMiddleware**: 모든 요청에 `X-Request-ID` 부여 (외부감사 추적용)
- **AuditLogMiddleware**: 모든 API 호출을 콘솔 감사 로그 (Phase 1+에 audit_logs 테이블 저장)
- **CORS**: `cors_allowed_origins` 환경변수로 제어
- **글로벌 예외 처리**: `ICFRException`, `RequestValidationError`를 표준 형식으로 응답
```

---

## 9. 진행 방식

### Step 1: 사전 작업
1. `git fetch origin` + 원격 변경 확인 (CLAUDE.md 섹션 9)
2. `backend/app/api/`, `backend/app/models/`, `backend/app/schemas/` 현재 상태 확인
3. `backend/app/main.py` 백업 (자동 — git이 알아서)

### Step 2: 파일 생성 (총 36개 신규/갱신)
1. `backend/app/api/system.py` (1개)
2. `backend/app/api/{schedule,rcm,scoping,euc,iuc,remediation,evidence,user_mgmt,notification,report,test_module}.py` (11개)
3. `backend/app/models/{schedule,rcm,scoping,euc,iuc,remediation,evidence,user_mgmt,notification,report,test_module}.py` (11개, 빈 파일)
4. `backend/app/schemas/{schedule,rcm,scoping,euc,iuc,remediation,evidence,user_mgmt,notification,report,test_module}.py` (11개, 빈 파일)
5. `backend/app/core/middleware.py` (1개 신규)
6. `backend/app/main.py` (갱신)
7. `backend/tests/test_modules.py` (1개 신규)
8. `backend/README.md` (갱신)

### Step 3: 검증
```powershell
# 컨테이너 재빌드
docker compose up -d --build backend

# 컨테이너 상태
.\dev.ps1 ps

# Swagger UI 확인
# http://localhost:8000/docs
# → 13개 카테고리 (default, health, auth, system + 11개 모듈) 노출 확인

# 시스템 메타 확인
curl http://localhost:8000/api/system/modules \
  -H "Authorization: Bearer $TOKEN"
# → 11개 모듈 배열 반환

# 테스트 실행
docker compose exec backend pytest -v
# → 모든 테스트 통과 (작업2의 3개 + 작업3의 ~24개)
```

### Step 4: 커밋 메시지 제안 + 사용자 OK 대기
변경 요약 표 + 커밋 메시지 제안. 사용자 OK 후 `git add . → git commit → git push`.

커밋 메시지: `feat(backend): 11개 모듈 API 골조 + 공통 미들웨어 (Phase 0 작업3)`

### Step 5: 일일 진행 로그 자동 추가 (자동 푸시)
ClaudeICFR.md 섹션 18에 다음 한 줄 자동 추가:
```
- **TrustBuilder**: Phase 0 작업3 완료 — 11개 모듈 API 골조 + 공통 미들웨어(요청ID·감사로그·글로벌예외). Swagger UI에 13개 카테고리 노출. 다음: 시드 데이터 (작업6) 또는 Regina의 프론트엔드 골조 시작 대기.
```
commit prefix: `chore(log): 2026-05-19 일일 진행 로그 추가 [auto]`

---

## 완료 후 안내 사항

1. ✅ Phase 0 작업3 완료
2. Swagger UI에서 11개 모듈 + system + 기존 (health, auth) 모두 노출 확인 가능
3. **이 시점부터 Regina가 작업4 시작 가능** — Frontend는 `/api/system/modules`를 호출하여 메뉴 자동 생성
4. 사용자는 다음 단계 선택:
   - **작업6 (시드 데이터)** 진행 — TrustBuilder 단독 영역 마무리
   - **Regina의 작업4 시작 대기** — 사용자는 잠시 휴식 가능
5. Regina에게 `git pull` 안내 및 Swagger UI 공유
