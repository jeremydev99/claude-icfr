# Test 모듈 2-A: TestRun 상세 패널 + 워크플로 전이 + 이력 타임라인

## 목표
TestRun 목록에서 행 클릭 시 슬라이드 패널이 열리고,
상세 정보 + 워크플로 전이 버튼 + 상태 이력 타임라인을 표시한다.

## 참고 패턴
- `frontend/src/features/rcm/components/ControlDetailSheet.tsx` — 슬라이드 패널 구조 그대로 참고
- `frontend/src/features/test/types.ts` — 기존 타입 활용

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/test/types.ts`
- `frontend/src/features/test/api/testRunsApi.ts`
- `frontend/src/features/test/components/TestRunTable.tsx`
- `frontend/src/features/test/pages/TestPage.tsx`
- `frontend/src/features/rcm/components/ControlDetailSheet.tsx` (참고용)

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-test-detail-2a
```

### 2. types.ts 추가
파일: `frontend/src/features/test/types.ts`

아래 타입 추가:
```ts
// 워크플로 전이 요청
export interface TransitionRequest {
  action: 'start' | 'complete' | 'approve' | 'reopen'
  comment?: string
}

// 상태 이력 단건
export interface TestStatusHistory {
  id: string
  test_run_id: string
  from_status: TestRunStatus | null
  to_status: TestRunStatus
  changed_by: string
  changed_at: string
  comment?: string
}
```

### 3. testRunsApi.ts 추가
파일: `frontend/src/features/test/api/testRunsApi.ts`

기존 함수 아래에 추가:
- `fetchTestRunDetail(id)` → GET `/api/test/runs/{id}`
- `fetchTestRunHistory(id)` → GET `/api/test/runs/{id}/history`
- `transitionTestRun(id, payload: TransitionRequest)` → POST `/api/test/runs/{id}/transition`

### 4. useTestRuns.ts 추가
파일: `frontend/src/features/test/api/useTestRuns.ts`

기존 훅 아래에 추가:
- `useTestRunDetail(id)` — useQuery, enabled: !!id
- `useTestRunHistory(id)` — useQuery, enabled: !!id
- `useTransitionTestRun()` — useMutation, 성공 시 detail + history + list 쿼리 invalidate

### 5. TestRunDetailSheet.tsx 신규 생성
파일: `frontend/src/features/test/components/TestRunDetailSheet.tsx`

ControlDetailSheet.tsx 패턴 그대로 참고하여 구성:

**Props:**
```ts
interface Props {
  runId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}
```

**섹션 구성 (3개):**

#### 섹션 1 — 기본 정보
| 필드 | 표시 |
|------|------|
| 통제 코드 | control_id (또는 연결된 code) |
| 회계연도 | fiscal_year |
| 테스터 | tester_id |
| 테스트일 | test_date |
| 테스트 방법 | inspection/reperformance/observation/inquiry 체크 표시 |
| 샘플 수 | sample_size |
| 결과 | RESULT_LABELS Badge |

#### 섹션 2 — 워크플로 전이
현재 status에 따라 버튼 표시:
| 현재 상태 | 버튼 | action |
|-----------|------|--------|
| planned | 테스트 시작 | start |
| in_progress | 테스트 완료 | complete |
| completed | 승인 | approve |
| approved | 재오픈 | reopen |

- 버튼 클릭 → `useTransitionTestRun` 호출
- 로딩 중 disabled 처리

#### 섹션 3 — 상태 이력 타임라인
- `useTestRunHistory(runId)` 데이터 사용
- 최신순 정렬
- 각 항목: `from_status → to_status`, `changed_by`, `changed_at` (날짜 포맷)
- shadcn/ui 없이 간단한 세로 타임라인 (border-l + dot 패턴)

### 6. TestRunTable.tsx 수정
파일: `frontend/src/features/test/components/TestRunTable.tsx`

- 행 클릭 시 `onRowClick(run.id)` 콜백 호출하도록 수정
- cursor-pointer 클래스 추가

### 7. TestPage.tsx 수정
파일: `frontend/src/features/test/pages/TestPage.tsx`

- `selectedRunId` state 추가 (`string | null`, 초기값 null)
- `detailOpen` state 추가 (boolean)
- TestRunTable에 `onRowClick` prop 연결
- `<TestRunDetailSheet>` 추가

## 완료 조건
- TestRun 목록 행 클릭 → 슬라이드 패널 열림
- 상세 정보 표시 (실 API)
- 현재 상태에 맞는 전이 버튼 표시 및 클릭 작동
- 상태 이력 타임라인 표시
- TypeScript 오류 없음
- 빌드 통과

### 8. 커밋 & push
```powershell
git add frontend/src/features/test/
git commit -m "feat(frontend): Test 모듈 2-A — TestRun 상세 패널 + 워크플로 전이 + 이력 타임라인"
git push -u origin feature/fe-test-detail-2a
```

### 9. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-test-detail-2a
git push origin main
```
