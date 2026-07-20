# ICFR-PROMPT-rcm-adapter-layer

## 목적

RCM 모듈에 **어댑터 경계(adapter boundary)** 를 도입한다.
현재 `controlsApi.ts` / `rawcApi.ts` 의 서버 응답이 훅을 거쳐 컴포넌트까지 **무가공으로** 흐른다.
ADR-0027 2-B(상위 계층 baseline화) 완료 후 응답 스키마에 출처 판별 필드가 추가될 예정이므로,
그 변경이 **어댑터 파일 1곳** 에서 흡수되도록 매핑 지점을 선제적으로 한 군데로 모은다.

**이번 작업에서 새 필드를 만들지 않는다.** 현재 API 계약을 100% 그대로 유지한다.
(2-B 스펙 미수신 상태 — 미확인 계약 기반 구현 금지 원칙 준수)

## 절대 하지 말 것

- `source`, `baseline_id`, `is_overridden` 등 **미확정 필드 추가 금지**
- 컴포넌트 파일 수정 금지 (`features/rcm/components/**`, `pages/**`)
- 훅 이름·시그니처·반환 타입 변경 금지
- `queryKeys.ts`, `axios.ts` 수정 금지 (테넌트 축 작업 완료분 건드리지 않는다)
- API 엔드포인트 URL·파라미터 변경 금지

## 사전 확인

```powershell
Set-Location E:\claudeprojects\ICFR
git status
git fetch origin
git log origin/main --oneline -5
```

원격에 새 커밋이 있으면 먼저 보고하고 멈춘다.

## 브랜치

```powershell
git checkout -b feature/rcm-adapter-layer
```

---

## Step 1 — DTO 타입 분리

`frontend/src/features/rcm/api/dto.ts` **신규 생성**.

1. `frontend/src/features/rcm/types.ts` 를 읽는다.
2. 서버 응답 형태에 해당하는 타입들을 DTO로 복제한다:
   - `ControlDto`, `ControlListResponseDto`
   - `ProcessItemDto`, `SubProcessItemDto`, `RiskItemDto`
   - 현재 `types.ts` 의 해당 타입과 **필드가 완전히 동일** 해야 한다.
3. `types.ts` 는 **수정하지 않는다.** 기존 `Control`, `ControlListResponse` 등은 그대로 두고
   앞으로 "도메인 타입"의 역할을 맡는다. (오늘 시점엔 DTO와 형태가 같다.)

주석으로 각 파일 상단에 역할을 명시한다:
- `dto.ts` → `// 서버 응답 원형(wire format). 백엔드 계약 변경 시 여기만 바뀐다.`
- `types.ts` → `// 프론트 도메인 타입. 컴포넌트가 소비한다.`

## Step 2 — 어댑터 생성

`frontend/src/features/rcm/api/controlsAdapter.ts` **신규 생성**.

```
toControl(dto: ControlDto): Control
toControlList(dto: ControlListResponseDto): ControlListResponse
toProcessItems(dto): { items: ProcessItem[] }
toSubProcessItems(dto): { items: SubProcessItem[] }
toRiskItems(dto): { items: RiskItem[] }
```

- 현재는 **1:1 필드 매핑(항등 변환)** 이다. `as` 캐스팅으로 얼버무리지 말고,
  필드를 명시적으로 나열해 매핑한다. (2-B 때 여기서 필드가 추가/변형된다)
- 파일 상단에 주석:
  ```
  // ADR-0027 2-B 착륙 지점.
  // baseline/tenant 출처 판별 필드는 2-B 스펙 확정 후 이 파일에서 흡수한다.
  ```

## Step 3 — API 레이어 반환 타입 교체

`frontend/src/features/rcm/api/controlsApi.ts` 수정.

- import를 `../types` → `./dto` 로 교체 (요청 payload 타입 `ControlCreatePayload`,
  `ControlUpdatePayload`, `ControlSearchParams` 는 `../types` 유지)
- 각 fetch 함수의 제네릭·반환 타입을 DTO 타입으로 변경
- `createControl`, `updateControlById` 의 반환은 `ControlDto`
- **함수 이름·인자·엔드포인트·params 처리 로직은 그대로**

## Step 4 — 훅에 select 연결

`frontend/src/features/rcm/api/useControls.ts` 수정.

- `useControls` 의 `useQuery` 에 `select: toControlList` 추가
- 제네릭을 `useQuery<ControlListResponseDto, Error, ControlListResponse>` 형태로 명시
- **queryKey, staleTime, placeholderData 는 변경 금지**
- mutation 훅 3개(`useCreateControl` / `useUpdateControl` / `useDeleteControl`)는
  **이번 작업에서 손대지 않는다.** (2-A-4 CRUD 스펙 대기 중)

## Step 5 — rawc 동일 패턴 적용

`rawcApi.ts` / `useRawc.ts` 에 Step 1~4 와 동일한 패턴을 적용한다.
- `frontend/src/features/rcm/api/rawcAdapter.ts` 신규
- DTO는 `dto.ts` 에 추가 (파일 분리하지 않는다)
- 쿼리 훅만 `select` 연결, mutation은 손대지 않는다

`mockData.ts` 가 위 타입을 참조하면 DTO 타입으로 맞춰준다.

---

## 검증

### 타입·빌드

```powershell
Set-Location E:\claudeprojects\ICFR\frontend
npm run build
```

에러 0이어야 한다. `any` 로 우회하지 않는다.

### 브라우저 확인 (백엔드 기동 포함)

```powershell
Set-Location E:\claudeprojects\ICFR
docker compose up -d
```

```powershell
docker compose ps
```

```powershell
Set-Location E:\claudeprojects\ICFR\frontend
npm run dev
```

확인 항목 — `admin@acme.example / admin123` 로그인 후:
1. RCM 통제 목록 정상 렌더링
2. 검색 필터(process / sub_process / risk_level) 동작
3. 페이지네이션 동작
4. RAWC 화면 정상 렌더링
5. 브라우저 콘솔 에러 0
6. DevTools Network 에서 `X-Tenant-Id` 헤더 유지 확인

**하나라도 실패하면 머지하지 말고 보고한다.**

---

## 커밋 & 머지

```powershell
Set-Location E:\claudeprojects\ICFR
git add -A
git commit -m "refactor(rcm): introduce adapter boundary between API and hooks

- add dto.ts: server wire-format types separated from domain types
- add controlsAdapter.ts / rawcAdapter.ts as single mapping point
- wire adapters via TanStack Query select
- no contract change; landing point for ADR-0027 2-B"
```

```powershell
git checkout main
```

```powershell
git merge --no-ff feature/rcm-adapter-layer
```

```powershell
git push origin main
```

푸시까지 자동 진행 승인. (계약 무변경 리팩터 — 위험도 낮음)

## 마무리

`ClaudeICFR.md` 섹션 12 / 14 에 아래를 반영한다:
- RCM 어댑터 경계 도입 완료, 2-B 착륙 지점 확보
- mutation 계열은 2-A-4 스펙 대기로 미변경
- 나머지 4개 모듈(evidence / remediation / test / users)은 2-B 스펙 확정 후 일괄 적용 예정

## PowerShell 제약

- `&&`, `||`, `$()`, `grep`, heredoc, `/dev/null` 금지
- `cd` 대신 `Set-Location`
- 복합 명령은 반드시 분리 실행
- 단일 명령 965바이트 이하
