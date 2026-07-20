# Test 모듈 2-B: TestStep CRUD + TestRun 편집

## 목표
TestRunDetailSheet 안에 TestStep 섹션 추가 (목록 + 추가 + 편집 + 삭제)
TestRun 편집 Dialog 추가 (평가일·결과·샘플수 등 수정 가능)

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/test/types.ts`
- `frontend/src/features/test/api/testRunsApi.ts`
- `frontend/src/features/test/api/useTestRuns.ts`
- `frontend/src/features/test/components/TestRunDetailSheet.tsx`

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-test-step-2b
```

### 2. types.ts 추가
파일: `frontend/src/features/test/types.ts`

아래 타입 추가:
```ts
export interface TestStep {
  id: string
  test_run_id: string
  step_order: number
  description: string
  result: 'pass' | 'fail'
  created_at: string
}

export interface TestStepCreatePayload {
  test_run_id: string
  step_order: number
  description: string
  result: 'pass' | 'fail'
}

export interface TestStepUpdatePayload {
  description?: string
  result?: 'pass' | 'fail'
}

export interface TestRunUpdatePayload {
  test_date?: string | null
  result?: TestResult | null
  sample_size?: number | null
  inspection?: boolean
  reperformance?: boolean
  observation?: boolean
  inquiry?: boolean
}
```

### 3. testRunsApi.ts 추가
파일: `frontend/src/features/test/api/testRunsApi.ts`

기존 함수 아래에 추가:
- `updateTestRun(id, payload: TestRunUpdatePayload)` → PATCH `/api/test/runs/{id}`
- `fetchTestSteps(runId)` → GET `/api/test/steps?run_id={runId}`
- `createTestStep(payload: TestStepCreatePayload)` → POST `/api/test/steps`
- `updateTestStep(id, payload: TestStepUpdatePayload)` → PATCH `/api/test/steps/{id}`
- `deleteTestStep(id)` → DELETE `/api/test/steps/{id}`

### 4. useTestRuns.ts 추가
파일: `frontend/src/features/test/api/useTestRuns.ts`

기존 훅 아래에 추가:
- `useUpdateTestRun()` — useMutation, 성공 시 detail 쿼리 invalidate
- `useTestSteps(runId)` — useQuery, enabled: !!runId
- `useCreateTestStep()` — useMutation, 성공 시 steps 쿼리 invalidate
- `useUpdateTestStep()` — useMutation, 성공 시 steps 쿼리 invalidate
- `useDeleteTestStep()` — useMutation, 성공 시 steps 쿼리 invalidate

### 5. TestRunDetailSheet.tsx 수정
파일: `frontend/src/features/test/components/TestRunDetailSheet.tsx`

#### 5-1. 헤더에 편집 버튼 추가
- 상단 우측에 "편집" 버튼 → `editOpen` state true

#### 5-2. TestStep 섹션 추가 (기존 섹션 아래)
- `useTestSteps(runId)` 데이터 사용
- 테이블 구성:

| 순서 | 설명 | 결과 | 액션 |
|------|------|------|------|
| 1 | 설명 텍스트 | pass/fail Badge | 편집·삭제 버튼 |

- 테이블 하단 "단계 추가" 버튼
- 추가/편집 시 인라인 폼 (description 입력 + result select + 저장/취소)
- 삭제 시 confirm Dialog (RCM 패턴 동일하게)
- `approved` 상태일 때는 추가·편집·삭제 버튼 비활성화 (잠금 처리)

### 6. TestRunEditDialog.tsx 신규 생성
파일: `frontend/src/features/test/components/TestRunEditDialog.tsx`

```ts
interface Props {
  run: TestRun
  open: boolean
  onOpenChange: (open: boolean) => void
}
```

편집 가능 필드:
- 평가일 (test_date) — date input
- 결과 (result) — select (pass/fail/n/a)
- 샘플 수 (sample_size) — number input
- 평가 방법 4개 (inspection/reperformance/observation/inquiry) — checkbox

저장 → `useUpdateTestRun()` 호출 → 성공 시 Dialog 닫기

### 7. TestRunDetailSheet.tsx에 TestRunEditDialog 연결
- `editOpen` state 추가
- `<TestRunEditDialog>` 렌더링

## 완료 조건
- TestStep 목록 표시 (실 API)
- TestStep 추가·편집·삭제 작동
- approved 상태에서 수정 버튼 비활성화
- TestRun 편집 Dialog에서 평가일·결과·샘플수 수정 가능
- TypeScript 오류 없음
- 빌드 통과

### 8. 커밋 & push
```powershell
git add frontend/src/features/test/
git commit -m "feat(frontend): Test 모듈 2-B — TestStep CRUD + TestRun 편집"
git push -u origin feature/fe-test-step-2b
```

### 9. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-test-step-2b
git push origin main
```
