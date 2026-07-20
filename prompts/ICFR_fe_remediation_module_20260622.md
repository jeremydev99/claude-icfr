# Remediation 모듈: 미비점(Deficiency) + 개선계획(RemediationPlan) 화면 신규

## 목표
미비점 목록·등록·편집 화면과, 개선계획 목록·상세·워크플로 전이·이력 화면을 구축한다.
Test 모듈(2-A, 2-B)과 동일한 패턴을 따른다.

## 범위 제한 (이번 작업 제외)
- DesignAssessment(설계평가)는 이번 범위 제외, 별도 작업으로 진행
- changed_by는 ID만 표시 (사용자 이름 조회 API 연동은 제외)

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/test/` 전체 (구조·패턴 그대로 참고: types.ts, api/, components/, pages/)
- `frontend/src/features/remediation/` 현재 상태

## API 스펙 (확정, prefix: /api/remediation)

### Deficiency
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | /deficiencies?skip=&limit= | - | { items, total, skip, limit } |
| POST | /deficiencies | DeficiencyCreate | DeficiencyRead (201) |
| GET | /deficiencies/{id} | - | DeficiencyRead |
| PATCH | /deficiencies/{id} | DeficiencyUpdate | DeficiencyRead |
| DELETE | /deficiencies/{id} | - | 204 |

```ts
interface DeficiencyCreatePayload {
  code: string              // 1-20자, 필수
  severity: 'low' | 'medium' | 'high'  // 필수
  description: string       // 필수
  status?: 'open' | 'in_progress' | 'closed'  // 기본 'open'
  fiscal_year?: number       // 기본 2025
  test_run_id?: string | null
  control_id?: string | null
}

interface DeficiencyUpdatePayload {
  severity?: 'low' | 'medium' | 'high'
  description?: string
  status?: 'open' | 'in_progress' | 'closed'
  fiscal_year?: number
  control_id?: string | null
  final_conclusion?: string | null
  confirmed_at?: string | null
  confirmed_by_id?: string | null
}

interface Deficiency extends DeficiencyCreatePayload {
  id: string
  final_conclusion: string | null
  confirmed_at: string | null
  confirmed_by_id: string | null
  created_at: string
  updated_at: string
}
```

### RemediationPlan
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | /plans?skip=&limit= | - | { items, total, skip, limit } |
| POST | /plans | RemediationPlanCreate | RemediationPlanRead (201) |
| GET | /plans/{id} | - | RemediationPlanRead |
| PATCH | /plans/{id} | RemediationPlanUpdate | RemediationPlanRead |
| DELETE | /plans/{id} | - | 204 |
| POST | /plans/{id}/transition | { to_status, reason? } | RemediationPlanRead |
| GET | /plans/{id}/history | - | { items, total } |

```ts
type RemediationStatus = 'planned' | 'in_progress' | 'completed' | 'approved'

interface RemediationPlanCreatePayload {
  deficiency_id: string      // 필수
  owner_id: string            // 필수
  target_date: string         // 필수, date
  action_plan: string         // 필수
  improvement_description?: string | null
  priority?: 'High' | 'Medium' | 'Low'  // 기본 'Medium'
  owner_opinion?: string | null
  reviewer_opinion?: string | null
}

interface RemediationPlanUpdatePayload {
  target_date?: string
  action_plan?: string
  improvement_description?: string | null
  priority?: 'High' | 'Medium' | 'Low'
  owner_opinion?: string | null
  reviewer_opinion?: string | null
}

interface RemediationPlan extends RemediationPlanCreatePayload {
  id: string
  status: RemediationStatus
  approved_by_id: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

interface RemediationTransitionRequest {
  to_status: 'in_progress' | 'completed' | 'approved'
  reason?: string | null
}

interface RemediationStatusHistory {
  id: string
  remediation_plan_id: string
  from_status: RemediationStatus | null
  to_status: RemediationStatus
  changed_by_id: string
  changed_at: string
  reason: string | null
}
```

**워크플로 규칙**: planned → in_progress → completed → approved (역방향 불가, 위반 시 422)

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-remediation-module
```

### 2. types.ts 신규 생성
파일: `frontend/src/features/remediation/types.ts`

위 모든 타입 정의 + 라벨 매핑 상수:
- `SEVERITY_LABELS` (low/medium/high → 낮음/중간/높음)
- `DEFICIENCY_STATUS_LABELS` (open/in_progress/closed → 한국어)
- `REMEDIATION_STATUS_LABELS` (planned/in_progress/completed/approved → 계획/진행중/완료/승인)
- `PRIORITY_LABELS` (High/Medium/Low → 상/중/하)
- Badge 클래스 상수 (test/types.ts 패턴 참고)

### 3. API 파일 신규 생성
파일: `frontend/src/features/remediation/api/deficiencyApi.ts`
- fetchDeficiencies, createDeficiency, fetchDeficiencyDetail, updateDeficiency, deleteDeficiency

파일: `frontend/src/features/remediation/api/remediationPlanApi.ts`
- fetchPlans, createPlan, fetchPlanDetail, updatePlan, deletePlan, transitionPlan, fetchPlanHistory

### 4. 훅 파일 신규 생성
파일: `frontend/src/features/remediation/api/useDeficiencies.ts`
- useDeficiencies, useCreateDeficiency, useUpdateDeficiency, useDeleteDeficiency

파일: `frontend/src/features/remediation/api/useRemediationPlans.ts`
- usePlans, useCreatePlan, usePlanDetail, useUpdatePlan, useDeletePlan, useTransitionPlan, usePlanHistory

### 5. Deficiency 컴포넌트
파일: `frontend/src/features/remediation/components/DeficiencyTable.tsx`
- 컬럼: code, severity(Badge), description(축약), status(Badge), fiscal_year, 액션(편집·삭제)
- 행 클릭 시 onRowClick 콜백 (상세는 이번 범위에서는 단순 편집 Dialog로 충분, 별도 Sheet 불필요)

파일: `frontend/src/features/remediation/components/DeficiencyFormDialog.tsx`
- 등록/편집 겸용 Dialog. code, severity, description, status, fiscal_year, control_id 입력

### 6. RemediationPlan 컴포넌트
파일: `frontend/src/features/remediation/components/RemediationPlanTable.tsx`
- 컬럼: action_plan(축약), priority(Badge), status(Badge), owner_id, target_date, 액션
- 행 클릭 시 상세 패널 오픈

파일: `frontend/src/features/remediation/components/RemediationPlanCreateDialog.tsx`
- deficiency_id, owner_id, target_date, action_plan, priority 입력 (Test의 CreateTestRunDialog 패턴 참고)

파일: `frontend/src/features/remediation/components/RemediationPlanDetailSheet.tsx`
- TestRunDetailSheet 패턴 그대로 참고
- 기본 정보 섹션 (deficiency_id, owner_id, target_date, action_plan, priority, opinion들)
- 워크플로 전이 버튼 (NEXT_TRANSITION 맵: planned→in_progress→completed→approved)
- 이력 타임라인 (changed_by_id를 짧게 표시, 이름 조회 없음)

### 7. 페이지 구성
파일: `frontend/src/features/remediation/pages/RemediationPage.tsx`

- 상단 탭 또는 토글로 "미비점" / "개선계획" 두 뷰 전환 (간단한 버튼 그룹으로 충분, 복잡한 라우팅 불필요)
- 미비점 뷰: DeficiencyTable + 등록 버튼 + DeficiencyFormDialog
- 개선계획 뷰: RemediationPlanTable + 등록 버튼 + RemediationPlanCreateDialog + RemediationPlanDetailSheet

## 완료 조건
- 미비점 목록·등록·편집·삭제 실 API 동작
- 개선계획 목록·등록 실 API 동작
- 개선계획 상세 패널에서 워크플로 전이(4단계) 작동
- 이력 타임라인 표시 (changed_by_id 그대로 노출, 추가 조회 없음)
- TypeScript 오류 없음
- 빌드 통과

### 8. 커밋 & push
```powershell
git add frontend/src/features/remediation/
git commit -m "feat(frontend): Remediation 모듈 — 미비점·개선계획 CRUD 및 워크플로"
git push -u origin feature/fe-remediation-module
```

### 9. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-remediation-module
git push origin main
```
