# ICFR_frontend_10_20260612.md — Phase 1: Test 모듈 1단계 — TestRun 목록 + 추가

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-06-12 |
| 작업 유형 | Test 모듈 1단계 — TestRun(평가 실행) 목록 + 평가 추가 (실 API) |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 Test 작업1 |
| 결정 출처 | claude.ai 사전 승인 (2026-06-12) |
| 예상 작업 시간 | 2~2.5시간 |
| 영향 파일 | `frontend/src/features/test/` 신규 생성 (placeholder 교체) |
| 커밋 메시지 제안 | `feat(frontend): Test 모듈 1단계 — TestRun 목록 + 추가 (실 API)` |
| 브랜치 | `feature/fe-test-list-create` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 진입 방식 | 사이드바 "Test" 메뉴 → 독립 페이지 (`/test`) |
| 이번 범위 | **목록 + 추가만** — 상세·워크플로·이력은 2단계로 분리 |
| 평가 유형 | TestRun만 (RAWC는 별도 작업) |
| 데이터 | 처음부터 실 API (mock 단계 건너뜀, RCM에서 패턴 확립됨) |
| API 호출 | TanStack Query (useQuery + useMutation) |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.11 Test 모듈 명세, 섹션 5.3.3 D 그룹 ERD, ADR-0017),
`CLAUDE.md` (섹션 9 명세 동기화 체크),
`backend/app/api/test.py` 의 `/runs` 엔드포인트, `backend/app/schemas/test.py` 를 먼저 확인하고 아래 구현해줘.

**작업 시작 전 필수 체크**:
1. `git fetch origin && git checkout main && git pull` 으로 최신 상태
2. `feature/fe-test-list-create` 브랜치 생성
3. 백엔드 컨테이너 healthy 확인 (`docker compose ps`)
4. 백엔드 응답 스키마 정확히 파악 — `TestRunOut`(또는 응답 모델)의 모든 필드 정리

---

## 1. 핵심 설계 원칙

- **RCM 패턴 따르기**: useControls 패턴 그대로 적용 (controlsApi.ts → testRunsApi.ts)
- **요청 페이로드 분리**: `TestRun`(응답) vs `TestRunCreatePayload`(요청)
- **유니크 제약 에러 처리**: 같은 통제 + 같은 연도에 이미 TestRun 있으면 409 → 사용자에게 명확히 안내
- **통제 선택**: TestRun 추가 시 통제를 선택해야 함 → `controlsApi.fetchControls`로 통제 목록 가져와서 검색·선택
- **상세보기는 다음 작업**: 통제코드/연도/상태 등만 목록에 표시, 클릭 시 "준비중" 또는 비활성화

---

## 2. 생성 파일 구조

```
frontend/src/features/test/
├── types.ts                            ← 신규: TestRun 관련 타입 전체
├── api/
│   ├── testRunsApi.ts                  ← 신규: fetchTestRuns, createTestRun
│   └── useTestRuns.ts                  ← 신규: TanStack Query 훅
├── components/
│   ├── TestRunTable.tsx                ← 신규: 평가 목록 테이블
│   ├── TestRunSearchBar.tsx            ← 신규: 검색/필터
│   ├── CreateTestRunDialog.tsx         ← 신규: 평가 추가 Dialog
│   └── ControlSelector.tsx             ← 신규: 통제 선택 (Dialog 내부에서 사용)
└── pages/
    └── TestPage.tsx                    ← 수정: placeholder → 목록 화면
```

---

## 3. types.ts

백엔드 스키마와 100% 매칭. 백엔드 코드 확인 후 보정 필수.

```typescript
export type TestRunStatus = 'planned' | 'in_progress' | 'completed' | 'approved'
export type TestResult = 'pass' | 'fail' | 'n/a'

export interface TestRun {
  id: string
  control_id: string
  fiscal_year: number
  status: TestRunStatus
  tester_id: string | null
  test_date: string | null  // YYYY-MM-DD
  result: TestResult | null

  // 평가 절차 관련
  wtt_summary: string | null
  existing_process_notes: string | null
  method_inquiry: boolean
  method_observation: boolean
  method_inspection: boolean
  method_reperformance: boolean
  population: string | null
  test_frequency: 'O' | 'D' | 'W' | 'M' | 'Q' | 'A' | null
  sample_size: number | null
  procedure: string | null

  // 승인
  approved_by_id: string | null
  approved_at: string | null

  // 표시용 (백엔드 응답에 포함되는지 확인 필요 — 없으면 별도 호출)
  control_code?: string
  control_name?: string

  created_at: string
  updated_at: string
}

export interface TestRunCreatePayload {
  control_id: string
  fiscal_year: number
  // 추가 시 status는 백엔드가 자동 'planned' 세팅
  // 나머지 필드는 선택 — 우선 빈 값으로 시작 가능
  tester_id?: string | null
  test_date?: string | null
  population?: string | null
  test_frequency?: string | null
  sample_size?: number | null
  procedure?: string | null
}

export interface TestRunListResponse {
  items: TestRun[]
  total: number
  skip: number
  limit: number
}

export interface TestRunSearchParams {
  fiscal_year?: number
  status_filter?: TestRunStatus
  skip?: number
  limit?: number
}

// 라벨 매핑
export const STATUS_LABELS: Record<TestRunStatus, string> = {
  planned: '계획',
  in_progress: '진행중',
  completed: '완료',
  approved: '승인',
}

export const RESULT_LABELS: Record<TestResult, string> = {
  pass: '적합',
  fail: '부적합',
  'n/a': '해당없음',
}
```

> **확인 필요**: TestRun 응답에 `control_code`, `control_name`이 포함되는지. 없으면 별도로 controls API 호출해서 매핑 필요. 백엔드 코드 확인 후 결정.

---

## 4. testRunsApi.ts

```typescript
import axiosInstance from '@/lib/axios'

export async function fetchTestRuns(
  params: TestRunSearchParams
): Promise<TestRunListResponse> {
  const cleanParams: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value
    }
  }
  const res = await axiosInstance.get<TestRunListResponse>(
    '/api/test/runs',
    { params: cleanParams }
  )
  return res.data
}

export async function createTestRun(
  payload: TestRunCreatePayload
): Promise<TestRun> {
  const res = await axiosInstance.post<TestRun>('/api/test/runs', payload)
  return res.data
}
```

---

## 5. useTestRuns.ts (TanStack Query 훅)

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchTestRuns, createTestRun } from './testRunsApi'

export function useTestRuns(params: TestRunSearchParams) {
  return useQuery({
    queryKey: ['testRuns', params],
    queryFn: () => fetchTestRuns(params),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 30,
  })
}

export function useCreateTestRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createTestRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testRuns'] })
    },
  })
}
```

---

## 6. TestPage.tsx (placeholder 교체)

기존 placeholder 컴포넌트 제거, 실제 화면으로:

```tsx
export default function TestPage() {
  const currentYear = new Date().getFullYear()
  const [searchParams, setSearchParams] = useState<TestRunSearchParams>({
    fiscal_year: currentYear,
    skip: 0,
    limit: 20,
  })
  const [createOpen, setCreateOpen] = useState(false)

  const { data, isLoading, isError, error, refetch } = useTestRuns(searchParams)

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold">평가 (Test)</h1>
      <p className="mt-2 text-muted-foreground">
        통제별 운영평가 계획·실행·결과 관리
      </p>

      <TestRunSearchBar value={searchParams} onChange={setSearchParams} />
      <TestRunTable
        data={data}
        isLoading={isLoading}
        isError={isError}
        error={error}
        onAddClick={() => setCreateOpen(true)}
      />
      <CreateTestRunDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultFiscalYear={searchParams.fiscal_year ?? currentYear}
        onSuccess={() => {
          setCreateOpen(false)
          toast.success('평가가 추가되었습니다')
          refetch()
        }}
      />
    </div>
  )
}
```

---

## 7. TestRunSearchBar.tsx

상단 검색/필터. 단순하게:

```
[연도: 2026 ▼]  [상태: 전체 ▼]                    [+ 평가 추가]
```

- 연도 선택: 최근 3년 정도 + 다음해 (`currentYear - 2 ~ currentYear + 1`)
- 상태 필터: 전체 / planned / in_progress / completed / approved (한글 라벨 표시)
- 변경 시 `searchParams` 갱신 → 자동 재조회
- 우상단에 "+ 평가 추가" 버튼

---

## 8. TestRunTable.tsx

shadcn `Table` 사용. RCM 패턴 그대로.

**컬럼:**

| 컬럼 | 내용 | 비고 |
|---|---|---|
| 통제코드 | `control_code` | 백엔드 응답에 없으면 controls API로 매핑 (다음 섹션) |
| 통제명 | `control_name` | |
| 평가연도 | `fiscal_year` | |
| 상태 | `status` | Badge — 계획/진행중/완료/승인 (색상 구분: planned=회색, in_progress=파랑, completed=초록, approved=보라) |
| 결과 | `result` | Badge — 적합/부적합/해당없음/— |
| 평가일 | `test_date` | "—"로 fallback |
| 평가자 | `tester` | 사용자 ID 대신 이름 표시 필요 (다음 작업에서 user API 연결, 이번엔 ID나 "—" 표시) |
| 액션 | "상세" 버튼 | 클릭 시 "준비중 (다음 업데이트)" 토스트 — 상세보기는 2단계 작업 |

- 로딩/에러 상태 RCM 패턴 동일
- 페이지네이션 하단 (RCM과 동일)
- 빈 상태: "등록된 평가가 없습니다. '평가 추가' 버튼으로 첫 평가를 만들어주세요."

---

## 9. control_code/control_name 매핑 처리

**시나리오 A: 백엔드 응답에 포함되어 있음** → 그대로 사용

**시나리오 B: 백엔드 응답에 없음**
- TestRun 목록 받은 후, `control_id` 모두 모아서 한 번에 controls API로 매핑
- 또는 각 행에서 개별 `useQuery(['control', control_id])` 호출 (N+1 우려)
- **권장**: 백엔드에서 함께 내려주도록 협업자 요청 검토 (확장 필요 시 보고하고 멈춤)

> 작업 시작 시 백엔드 응답 확인 → 없으면 일단 N+1 안 일으키도록 client-side 매핑 (목록에서 한 번에 controls 조회) + 협업자 요청 메모.

---

## 10. CreateTestRunDialog.tsx

shadcn `Dialog`. 단순한 폼:

```
┌────────────────────────────────────────────┐
│  평가 추가                            [X]   │
├────────────────────────────────────────────┤
│                                             │
│  통제 *                                     │
│  [통제를 선택하세요... ▼]                  │
│  (선택 시 ControlSelector Dialog 열림)      │
│                                             │
│  평가 연도 *                                │
│  [2026]                                     │
│                                             │
│  ───────────────────────────                │
│  ⓘ 평가는 '계획(planned)' 상태로            │
│  생성됩니다. 세부 절차·결과는 상세 화면에서 │
│  입력하세요. (다음 업데이트 예정)           │
│                                             │
├────────────────────────────────────────────┤
│                       [취소]  [추가]        │
└────────────────────────────────────────────┘
```

**핵심:**
- 통제 선택: 별도 컴포넌트(`ControlSelector`)로 분리 — 통제 검색·선택 가능
- 평가 연도: 기본값은 현재 연도 또는 검색바의 fiscal_year
- 검증: 둘 다 필수
- 추가 클릭 → `createTestRun({ control_id, fiscal_year })` 호출
- **409 에러** (유니크 제약): "해당 통제의 N년 평가가 이미 존재합니다" 토스트 명확히 표시
- 다른 에러는 일반 메시지

---

## 11. ControlSelector.tsx

통제 선택 sub-dialog. 가벼운 검색 + 선택:

- 상단 검색창: 통제 코드/이름 입력 → `fetchControls({ q })` 호출 (debounce 300ms)
- 결과 목록: 최대 20건 카드 형태로 표시
  ```
  ┌────────────────────────────┐
  │ EL-010-10                  │
  │ 윤리경영의 정책 수립        │
  │ 프로세스: EL · 위험: 낮음   │
  └────────────────────────────┘
  ```
- 카드 클릭 → 선택 + Selector 닫힘 + 부모(`CreateTestRunDialog`)에 통제 정보 전달
- 선택된 통제는 부모 Dialog에 "EL-010-10 - 윤리경영의 정책 수립" 형태로 표시

---

## 12. 에러 처리 표준

`extractErrorMessage` 함수 재사용 (RCM에서 이미 만든 거). 추가로:

- **409 Conflict** (유니크 제약): "해당 통제의 {fiscal_year}년 평가가 이미 존재합니다. 기존 평가를 수정하거나 다른 연도를 선택해주세요."
- **422 Validation**: 백엔드 detail에서 어떤 필드 잘못됐는지 표시
- **그 외**: 일반 메시지

토스트로 표시 (sonner).

---

## 13. 완료 후 필수 작업

### 13.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: Test 모듈 FE 컬럼 → `🔄 진행중` + 비고 "목록·추가 (실 API)"
- **섹션 14**: "Regina: Test 모듈 1단계 — TestRun 목록·추가 화면 (실 API)" 한 줄
- **섹션 18.2**: 일일 진행 로그 (2026-06-12)

### 13.2 git 작업

```bash
git checkout -b feature/fe-test-list-create
# 작업 진행
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_10_20260612.md
git commit -m "feat(frontend): Test 모듈 1단계 — TestRun 목록 + 추가 (실 API)"
git push -u origin feature/fe-test-list-create
```

> Windows PowerShell 호환 — 한 줄 메시지로.

### 13.3 동작 확인 체크리스트
- [ ] `npm run build` 통과
- [ ] 사이드바 "Test" 메뉴 클릭 → 평가 목록 화면 표시
- [ ] 평가 목록이 백엔드 실 데이터로 표시됨 (시드 데이터 또는 빈 상태)
- [ ] 연도 필터 변경 → 결과 갱신
- [ ] 상태 필터 변경 → 결과 갱신
- [ ] "+ 평가 추가" 클릭 → Dialog 열림
- [ ] 통제 선택 → ControlSelector에서 검색·선택 → Dialog에 표시
- [ ] 연도 입력 후 "추가" → 토스트 + 목록 즉시 갱신
- [ ] 같은 통제·같은 연도로 또 추가 시도 → 409 에러 안내 메시지
- [ ] 페이지 새로고침 후에도 데이터 유지 (실 API니까 당연)
- [ ] 행의 "상세" 버튼 클릭 → "준비중" 토스트 표시 (2단계 작업)

---

## 14. 작업 외 (다음 작업으로 미룸 — 2단계)

- TestRun 상세 화면 (모든 필드 + 평가 절차 표시)
- 워크플로 전이 버튼 (planned → in_progress → completed → approved)
- 상태 변경 이력 타임라인 (`GET /runs/{id}/history`)
- TestStep 관리 (추가/수정/삭제 인라인)
- 결과 입력 (pass/fail/n/a) + 평가 방법 체크박스 4종
- 승인 워크플로
- 평가자(`tester_id`) 사용자 이름 표시 (user API 연결)

또한 다음 작업으로:
- RAWC (위험평가) 화면
- TestRun 편집 (PATCH)
- TestRun 삭제

---

## 15. 참조

- Test 모듈 명세: `ClaudeICFR.md` 섹션 4.11
- Test ERD: `ClaudeICFR.md` 섹션 5.3.3 (D 그룹)
- 백엔드 Test API: `backend/app/api/test.py`
- 백엔드 Test 스키마: `backend/app/schemas/test.py`
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_9_20260611.md` (RCM CRUD 실 API)
- 다음 작업: `ICFR_frontend_11` (Test 모듈 2단계 — 상세·워크플로·이력)
