# ICFR-PROMPT-tenant-header-axis

멀티테넌시 Phase 2 프론트엔드 축 작업.
`/api/auth/me`에 `tenants[]` + `active_tenant_id`가 추가되어(백엔드 main 반영) 이전에 보류했던 헤더 주입 작업을 재개한다.

**목표 3가지**
1. `/me`의 tenant 정보를 auth 레이어에 반영 (타입 + 저장)
2. axios 인터셉터에서 `X-Tenant-Id` 헤더 주입
3. Query Key factory에 tenant 프리픽스 도입 (캐시 격리 구조 선확보)

현재 tenant는 1개(사이냅소프트/DEFAULT)뿐이라 **동작상 변화는 없어야 한다(zero behavioral change)**. 구조만 깐다.
**tenant 전환 UI는 이번 범위 아님.** 만들지 말 것.
**RCM baseline/overlay는 백엔드 2-A-3 전까지 FE 무영향.** RCM API 관련 코드는 건드리지 말 것.

---

## 0. 사전 준비 (필수)

프로젝트 경로: `E:\claudeprojects\ICFR`
PowerShell 5.1 — bash 문법 금지(`&&`, `$()`, `|| `, heredoc, grep 사용 불가). 한 줄에 한 명령.

```powershell
Set-Location E:\claudeprojects\ICFR
```
```powershell
git checkout main
```
```powershell
git pull
```
```powershell
docker compose up -d --build backend
```

> 백엔드는 이미지에 코드가 baked 되므로 **반드시 `--build`**. restart만으로는 `/me` 변경이 반영되지 않는다.

---

## 1. STEP 1 — `/me` 실제 응답 검증 (추정 금지)

로그인 후 `/api/auth/me`를 **실제로 호출해서 응답 JSON을 확인**한다. 문서/기억이 아니라 실물 기준으로 타입을 정의한다.

- 계정: `admin@acme.example` / `admin123`
- 확인 항목:
  - `tenants` 배열 필드명/형태: `{ id, name, code, role }`
  - `active_tenant_id` 존재 및 타입 (uuid string인지 int인지 **실물로 확인**)
  - 기존 필드(id, email, role 등)가 그대로인지 (기존 파싱 깨짐 여부)

응답 원문을 콘솔에 출력해서 남기고, 그 결과를 근거로 STEP 2를 진행한다.
만약 `tenants` / `active_tenant_id`가 응답에 없으면 **여기서 멈추고 보고**한다 (pull/빌드 문제 가능성).

---

## 2. STEP 2 — 타입 + auth 상태 반영

- `/me` 응답 타입(예: `User` / `MeResponse`)에 다음 추가:
  ```ts
  export interface TenantSummary {
    id: string;          // STEP 1에서 확인한 실제 타입으로
    name: string;
    code: string;
    role: string;
  }
  // MeResponse
  tenants: TenantSummary[];
  active_tenant_id: string | null;
  ```
- auth context/store에서 `activeTenantId`를 파생값으로 노출한다.
  - 소스는 **오직 `/me`의 `active_tenant_id`**. JWT 파싱이나 localStorage 별도 저장은 하지 않는다(단일 소스 원칙).
  - `tenants` 배열도 함께 보관만 해둔다(향후 전환 UI용). **UI는 만들지 않는다.**
- 기존 auth 소비 컴포넌트가 깨지지 않도록 optional/기본값 처리.

---

## 3. STEP 3 — axios 인터셉터 `X-Tenant-Id` 주입

기존 Authorization 토큰 주입 인터셉터 옆에 붙인다.

요구사항:
- 요청 시 `activeTenantId`가 있으면 `X-Tenant-Id` 헤더를 붙인다.
- **제외 대상**: 인증 이전 요청 — `/auth/login`, `/auth/refresh`, `/auth/me`. (헤더가 붙어도 무해하지만, tenant 확정 전 요청이므로 명시적으로 제외)
- `activeTenantId`가 아직 없으면(로그인 직후 `/me` 이전) 헤더 없이 그대로 요청 — **에러로 막지 말 것.**
- 인터셉터가 React hook에 의존하지 않도록, auth 레이어에서 모듈 스코프에 tenantId를 sync 해두는 방식(예: `setActiveTenantId()` setter)을 사용한다. 기존 토큰 주입 방식과 동일한 패턴을 따를 것.

---

## 4. STEP 4 — Query Key factory tenant 프리픽스

대상: `src/lib/queryKeys.ts` (RCM, Test, Evidence, Remediation, Users 5개 모듈)

**핵심 제약: 컴포넌트 호출부는 수정하지 않는다.**

- 각 모듈 key root를 `['tenant', tenantId, 'rcm', ...]` 형태로 tenant를 prefix 한다.
- tenantId는 **각 모듈의 커스텀 훅 레이어에서 `useAuth()`로 읽어 주입**한다. 컴포넌트가 tenantId를 인자로 넘기게 만들지 말 것.
- tenantId가 `null`일 때도 key가 안정적으로 생성되어야 한다(예: `'no-tenant'` sentinel). 키가 `undefined`를 포함해 unstable 해지지 않게 할 것.
- **invalidation 경로가 전부 새 key 구조를 타는지 반드시 점검**한다. 하드코딩된 `queryClient.invalidateQueries(['rcm'])` 같은 잔재가 있으면 factory 경유로 교체.
- 결과적으로 현재(tenant 1개) 동작은 완전히 동일해야 한다.

---

## 5. 검증

```powershell
npm run build
```

브라우저 확인용 기동:
```powershell
docker compose up -d
```
```powershell
npm run dev
```

수동 확인 체크리스트:
- [ ] 로그인 정상
- [ ] DevTools Network에서 RCM/Test/Evidence/Remediation/Users 요청에 `X-Tenant-Id` 헤더가 붙는가
- [ ] `/auth/login`, `/auth/me` 에는 헤더가 안 붙는가
- [ ] 5개 모듈 목록 화면 정상 렌더
- [ ] 각 모듈에서 CRUD 1건씩 → 목록 자동 갱신되는가 (invalidation 깨짐 확인)
- [ ] 로그아웃 → 재로그인 시 캐시 이상 없는가

---

## 6. Git

- 브랜치: `feature/tenant-header-axis`
- `npm run build` 통과 후 커밋, **feature 브랜치 push까지 자동 진행**
- main 머지는 브라우저 확인 후 사용자 승인 시 진행
- 머지 후 `ClaudeICFR.md` 12/13/14 섹션 업데이트

---

## 주의

- DB 스키마 변경 명령(`alembic upgrade/downgrade`) 없음. 이번 작업은 FE 전용.
- 백엔드 코드 수정 금지.
- RCM baseline/overlay 관련 구조는 건드리지 않는다.
- tenant 전환 UI 생성 금지.
