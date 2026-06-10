# ICFR_frontend_7_20260601.md — Phase 1: useControls mock → 진짜 API 전환 (TanStack Query)

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-06-01 |
| 작업 유형 | RCM 통제 목록 + 검색/필터 + 페이지네이션을 mock에서 진짜 백엔드 API로 전환 (TanStack Query) |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 RCM 작업5 |
| 결정 출처 | claude.ai 사전 승인 (2026-06-01) |
| 예상 작업 시간 | 1.5~2.5시간 |
| 영향 파일 | `frontend/src/features/rcm/api/` 재구성 + `RcmPage.tsx`·`ControlTable.tsx` 수정 |
| 커밋 메시지 제안 | `feat(frontend): RCM 목록/검색/필터/페이지네이션을 백엔드 API로 전환 (TanStack Query)` |
| 브랜치 | `feature/fe-rcm-list-api` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 작업 범위 | 목록 조회 + 검색/필터 + 페이지네이션 — 모두 백엔드로 |
| API 호출 방식 | TanStack Query (`@tanstack/react-query`) |
| 추가/편집/Excel 업로드 | 이번 작업에서는 **건드리지 않음** — 다음 작업으로 분리 |
| mock 데이터 | `mockData.ts` 자체는 보존(롤백 대비), 단 `useControls`에서는 import 제거 |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.2, 19), `CLAUDE.md` (섹션 9), `backend/app/api/rcm.py`의 `/controls/search` 엔드포인트를 먼저 확인하고 아래를 구현해줘.

**작업 시작 전 필수 체크**:
1. `git fetch origin && git checkout main && git pull`
2. `feature/fe-rcm-list-api` 브랜치 생성
3. 백엔드 컨테이너 healthy 확인 (`docker-compose ps`)
4. **백엔드 응답 스키마 정확히 매칭**: `backend/app/schemas/rcm.py`의 `ControlOut`(또는 응답 모델) 필드 ↔ 프론트엔드 `Control` 타입(`features/rcm/types.ts`) 비교
   - 필드 누락·이름 불일치 있으면 프론트엔드 `Control` 타입을 백엔드에 맞춰 보정
   - 특히 `process_code`, `sub_process_code`, `risk_level`, `assertions` 같은 표시용 필드가 백엔드 응답에 포함되는지 확인. **없으면 프롬프트 작성자(claude.ai)에게 보고하고 멈춤** — 백엔드 명세 변경 필요할 수 있음

---

## 1. 핵심 설계 원칙

- **mock 코드 깔끔히 제거**: `useControls` 훅 내부에서 `mockControls`, `controlsState`, `subscribers`, `addControl`, `updateControl` 모두 제거
- **TanStack Query로 일관**: `useQuery`로 목록 조회, 키는 `['controls', params]` 패턴
- **검색 파라미터 → URL 쿼리스트링 → 백엔드**: 기존 `ControlSearchParams`를 그대로 백엔드에 전달
- **로딩/에러 명확히 표시**: 테이블에 스피너 + 에러 상태
- **추가/편집은 mock 유지**: 다음 작업에서 전환 예정 — 사용자에게 명확히 안내(이미 노란 박스 있음)
- **QueryClient 설정**: `lib/queryClient.ts` 이미 있음(섹션 3.10) — 재사용

---

## 2. 생성/수정 파일

```
frontend/src/features/rcm/
├── api/
│   ├── useControls.ts              ← 대폭 수정: mock 제거 + TanStack Query
│   ├── mockData.ts                 ← 보존 (롤백/테스트용으로 남김. 주석 추가)
│   ├── uploadExcel.ts              ← 변경 없음
│   └── controlsApi.ts              ← 신규: 백엔드 fetch 함수 분리
├── pages/RcmPage.tsx               ← 수정: 로딩/에러 표시 + 추가/편집 mock 사용 명시 주석
└── components/ControlTable.tsx     ← 수정: isLoading·error props 받아 표시
```

---

## 3. controlsApi.ts (신규 — 백엔드 호출 함수만 분리)

```typescript
import axiosInstance from '@/lib/axios'
import type { Control, ControlSearchParams, ControlListResponse } from '../types'

export async function fetchControls(
  params: ControlSearchParams
): Promise<ControlListResponse> {
  // undefined 값은 쿼리에서 제외 (false나 0은 포함되도록 명시)
  const cleanParams: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value
    }
  }
  const res = await axiosInstance.get<ControlListResponse>(
    '/api/rcm/controls/search',
    { params: cleanParams }
  )
  return res.data
}

// 다음 작업에서 사용 예정 (지금은 정의만)
// export async function fetchControlById(id: string): Promise<Control> { ... }
// export async function createControl(payload: ...): Promise<Control> { ... }
// export async function updateControl(id: string, payload: ...): Promise<Control> { ... }
```

> **주의**: 엔드포인트 경로(`/api/rcm/controls/search`)는 백엔드 코드 확인 후 정확히 일치시킬 것. axios의 baseURL이 `http://localhost:8000`이면 path는 `/api/rcm/...` 로 시작.

---

## 4. useControls.ts (재작성)

기존 mock 로직 전부 제거하고 TanStack Query 기반으로 단순하게:

```typescript
import { useQuery } from '@tanstack/react-query'
import { fetchControls } from './controlsApi'
import type { ControlSearchParams, ControlListResponse } from '../types'

export function useControls(params: ControlSearchParams) {
  return useQuery<ControlListResponse>({
    queryKey: ['controls', params],
    queryFn: () => fetchControls(params),
    placeholderData: (previous) => previous, // 페이지 전환 시 깜빡임 방지
    staleTime: 1000 * 30, // 30초 동안 캐시
  })
}
```

**반환값 변경 안내** (호출하는 쪽 수정 필요):
- 기존: `{ data: ControlListResponse, isLoading: false }` (커스텀 형태)
- 신규: TanStack Query의 표준 반환값 — `{ data, isLoading, isError, error, isFetching, ... }`
- `data`는 fetch 전엔 `undefined` → 호출하는 쪽에서 안전하게 처리해야 함

### addControl / updateControl 제거 처리

기존 mock 함수 `addControl`, `updateControl`은 **임시로 console.warn + mock 동작 유지** (다음 작업까지 추가/편집 UI가 작동해야 함):

```typescript
// TODO: 다음 작업(ICFR_frontend_8)에서 실제 API로 교체
// 현재는 mock 동작 유지 — 새로고침 시 사라짐
import { mockControls } from './mockData'
let localOnlyControls: Control[] = []

export function addControl(payload: Omit<Control, 'id' | 'created_at'>): Control {
  console.warn('[mock] addControl — 새로고침 시 사라집니다. 다음 작업에서 실제 API로 전환됩니다.')
  const newControl: Control = {
    ...payload,
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
  }
  localOnlyControls.push(newControl)
  // 단, 이 데이터는 useControls 결과에 영향을 주지 않음 (서버 데이터와 별개)
  return newControl
}

export function updateControl(id: string, payload: Partial<Control>): Control | null {
  console.warn('[mock] updateControl — 새로고침 시 사라집니다.')
  // 기존 동작 유지 (UI에 즉시 반영되진 않음)
  return null
}
```

> 사실상 이번 작업 후 추가/편집은 화면에 즉각 반영되지 않게 됨. **이 부분을 RcmPage 또는 Dialog에 안내 토스트로 표시할 것** (예: "통제 추가/편집은 다음 업데이트에서 실제 저장됩니다").

또는 **더 단순한 접근**: 추가/편집 버튼을 일시적으로 비활성화하고 "곧 실제 API로 연결됩니다" 표시. 둘 중 사용자 경험 더 자연스러운 쪽 선택.

---

## 5. ControlTable.tsx 수정

기존:
```tsx
function ControlTable({ data, ... }) { ... }
```

변경:
```tsx
function ControlTable({ data, isLoading, isError, error, ... }) {
  if (isLoading) {
    return <div className="flex items-center justify-center p-12"><Loader2 className="animate-spin" /> 불러오는 중...</div>
  }
  if (isError) {
    return <div className="rounded border border-red-200 bg-red-50 p-6 text-red-700">
      불러오기 실패: {error?.message ?? '알 수 없는 오류'}
      <br />백엔드가 실행 중인지, 로그인 상태인지 확인해주세요.
    </div>
  }
  // data가 undefined일 때도 안전하게
  const items = data?.items ?? []
  const total = data?.total ?? 0
  // ... 기존 렌더링
}
```

- `Loader2` 아이콘: `lucide-react`에서 import
- 빈 결과(`items.length === 0`)는 기존처럼 "검색 결과 없음" 표시

---

## 6. RcmPage.tsx 수정

```tsx
const { data, isLoading, isError, error, refetch } = useControls(searchParams)

return (
  <div>
    <h1>RCM 관리</h1>
    <ControlSearchBar value={searchParams} onChange={setSearchParams} />
    <ControlFilterChips ... />
    <ControlTable
      data={data}
      isLoading={isLoading}
      isError={isError}
      error={error}
      onSelect={handleSelect}
      onAddClick={handleAddClick}
      onEdit={handleEditClick}
      onUploadClick={handleUploadClick}
    />
    <ControlDetailSheet ... />
    <ControlFormDialog ... />
    <ExcelUploadDialog
      open={uploadOpen}
      onOpenChange={setUploadOpen}
      onSuccess={() => {
        setUploadOpen(false)
        toast.success('Excel 업로드가 완료되었습니다')
        refetch() // ← 핵심: 업로드 후 목록 즉시 새로고침
      }}
    />
  </div>
)
```

**Excel 업로드 성공 후 `refetch()` 호출하면 화면에 새로 저장된 데이터가 자동 반영됨!**

또한 **노란색 안내 박스 제거 또는 갱신**:
- 목록은 이제 실제 DB 데이터를 보여주므로 "추후 목록도 실제 API로 전환 예정" 문구는 부정확
- 변경: "추가/편집은 다음 업데이트에서 실제 저장됩니다. Excel 업로드와 목록 조회는 실제 DB와 연결되어 있습니다."

---

## 7. 페이지네이션·정렬 동작 확인

`ControlTable`의 정렬 헤더 클릭, "이전/다음" 버튼, 페이지당 개수 Select 변경 → 모두 `searchParams` 갱신 → TanStack Query가 자동으로 새 데이터 가져옴.

확인 포인트:
- [ ] 정렬 변경 시 백엔드 호출 일어남 (Network 탭)
- [ ] 페이지 이동 시 새 데이터 로드, 깜빡임 없음 (`placeholderData` 덕분)
- [ ] 페이지당 개수 변경 시 첫 페이지로 리셋되는지

---

## 8. 완료 후 필수 작업

### 8.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: RCM FE 비고에 "목록/검색/필터/페이지네이션 API 연결" 추가
- **섹션 14**: "Regina: useControls mock → 백엔드 API 전환 (목록/검색/필터/페이지네이션)" 한 줄
- **섹션 18.2**: 일일 진행 로그 (2026-06-01)

### 8.2 git 작업

```bash
git checkout -b feature/fe-rcm-list-api
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_7_20260601.md
git commit -m "feat(frontend): RCM 목록/검색/필터/페이지네이션 백엔드 API 전환"
git push -u origin feature/fe-rcm-list-api
```

> 커밋 메시지는 한 줄 단순 형식 (Windows PowerShell 호환).

### 8.3 동작 확인 체크리스트
- [ ] `npm run build` 통과
- [ ] 백엔드 healthy, 프론트엔드 dev 동작
- [ ] 로그인 → RCM 메뉴 → **목록에 실제 백엔드 데이터(93건 + 시드) 표시**
- [ ] 페이지당 100건 선택 시 한 번에 100건 로드
- [ ] 검색창에 "EL" 입력 → 백엔드 필터링 결과 표시 (Network 탭에서 `q=EL` 요청 확인)
- [ ] 프로세스 필터 변경 → 결과 즉시 갱신
- [ ] 정렬 헤더 클릭 → 정렬 동작
- [ ] 페이지네이션 이전/다음 동작, 깜빡임 없음
- [ ] 백엔드 끄고 RCM 페이지 진입 → 명확한 에러 메시지 표시
- [ ] 로그아웃 상태에서 진입 → 401 후 자동 로그인 페이지 이동 (axios 인터셉터)
- [ ] Excel 업로드 → 완료 → 목록 즉시 갱신 (refetch 동작)
- [ ] 추가/편집 시도 → 안내 토스트("다음 업데이트에서 실제 저장") 또는 비활성화 표시
- [ ] 상세보기 패널 — mock 사라졌으니 깨지지 않는지 확인 (data.items 기반으로 잘 동작)

---

## 9. 트러블슈팅 가이드

작업 중 흔히 발생할 수 있는 문제:

1. **백엔드 응답 필드 누락** (예: `process_code`가 응답에 없음):
   - 백엔드 코드(`backend/app/api/rcm.py`의 `/controls/search` 응답)에서 어떤 필드를 반환하는지 정확히 확인
   - 누락된 필드가 있으면 → 멈추고 보고. 백엔드 명세 변경(JOIN 추가)이 필요할 수 있음

2. **CORS 또는 401 오류**:
   - vite.config.ts 프록시 또는 백엔드 CORS 확인 (Excel 업로드는 됐으니 이미 OK일 가능성 큼)

3. **TanStack Query 캐시 꼬임**:
   - `queryKey: ['controls', params]` — params가 객체라 깊은 비교가 필요. 객체 참조가 바뀌면 매번 새 요청
   - `searchParams`를 `useState`로 들고 있고, 사용자 입력 시 새 객체로 교체하면 자연스럽게 새 요청 발생

4. **검색 디바운스 동작 변화**:
   - 기존 mock은 즉시 필터링, 이제는 서버 요청 → 디바운스(300ms)가 의미 있어짐
   - 이미 ControlSearchBar에 디바운스 있는지 확인. 없으면 그대로 즉시 호출돼도 OK (서버 부담 적음)

---

## 10. 작업 외 (다음 작업으로 미룸)

- 통제 추가 폼 → `POST /controls` 실연결 (`ICFR_frontend_8`)
- 통제 편집 폼 → `PATCH /controls/{id}` 실연결
- 통제 상세 → `GET /controls/{id}` (현재는 목록 데이터 재사용)
- 통제 삭제 (단건/bulk)
- 위험 매트릭스 시각화

---

## 11. 참조

- 백엔드 검색 API: `backend/app/api/rcm.py` 의 `/controls/search`
- 백엔드 응답 스키마: `backend/app/schemas/rcm.py`
- axios: `frontend/src/lib/axios.ts`
- QueryClient: `frontend/src/lib/queryClient.ts`
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_6_20260530.md`
- 다음 작업: `ICFR_frontend_8` (추가/편집 API 연결)
