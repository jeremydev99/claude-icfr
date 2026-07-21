# 미비점·개선계획 화면 통합 (탭 분리 → 단일 화면)

## 목표
현재 "미비점" / "개선계획" 탭으로 완전히 분리된 화면을 하나로 통합한다.
미비점 테이블을 메인으로 하고, 각 행에 연결된 개선계획 상태를 함께 보여줘서
미비점과 그 개선계획을 한 화면에서 같이 파악할 수 있게 한다.

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/remediation/pages/RemediationPage.tsx` (현재 구조, 이미 확인함)
- `frontend/src/features/remediation/components/DeficiencyTable.tsx`
- `frontend/src/features/remediation/components/RemediationPlanTable.tsx`
- `frontend/src/features/remediation/components/RemediationPlanCreateDialog.tsx`
- `frontend/src/features/remediation/components/RemediationPlanDetailSheet.tsx`
- `frontend/src/features/remediation/api/useRemediationPlans.ts`

## 접근 방식 (확정)
- BE에 deficiency_id 필터 쿼리 파라미터 없음 → 클라이언트 필터링으로 처리 (BE 수정 요청 없음)
- `usePlans({ skip: 0, limit: 100 })`로 전체 plan을 가져와서 `deficiency_id`로 매칭

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-remediation-unify
```

### 2. DeficiencyTable.tsx 수정
파일: `frontend/src/features/remediation/components/DeficiencyTable.tsx`

- Props에 `plans: RemediationPlan[]` 추가 (부모에서 전체 plan 목록 전달)
- 각 미비점 행 마지막에 "개선계획" 컬럼 추가:
  - 해당 deficiency.id와 일치하는 plan이 **있으면**: 상태 Badge(계획/진행중/완료/승인) + 클릭 시 해당 plan 상세 열기 콜백 호출
  - **없으면**: "개선계획 등록" 작은 버튼 — 클릭 시 해당 deficiency_id를 미리 채운 상태로 등록 Dialog 열기 콜백 호출
- 새 props: `onPlanClick(planId: string)`, `onCreatePlanClick(deficiencyId: string)`

### 3. RemediationPlanCreateDialog.tsx 수정
파일: `frontend/src/features/remediation/components/RemediationPlanCreateDialog.tsx`

- Props에 `prefilledDeficiencyId?: string` 추가
- 전달받으면 deficiency_id Select를 해당 값으로 초기화하고, 필드를 읽기 전용 또는 disabled로 고정 (이미 어떤 미비점에서 진입했는지 명확하므로 재선택 불필요)
- prefilledDeficiencyId가 없으면 기존처럼 자유 선택 유지 (다른 곳에서 재사용 가능성 보존)

### 4. RemediationPage.tsx 재구성
파일: `frontend/src/features/remediation/pages/RemediationPage.tsx`

- 탭 토글(activeTab, "미비점"/"개선계획" 버튼) 완전히 제거
- 헤더 아래 바로 "+ 미비점 등록" 버튼 + DeficiencyTable 하나만 렌더링
- DeficiencyTable에 `plans={planData?.items ?? []}` 전달
- `onPlanClick` → selectedPlanId 세팅 + RemediationPlanDetailSheet 오픈
- `onCreatePlanClick(deficiencyId)` → prefilledDeficiencyId 세팅 + RemediationPlanCreateDialog 오픈
- 기존 RemediationPlanTable는 이 페이지에서 더 이상 사용하지 않음 (파일 자체는 삭제하지 말 것 — 다른 곳에서 참조하지 않는지만 확인하고 그대로 둠)

## 완료 조건
- 탭 없이 미비점 목록 하나의 화면으로 통합
- 각 미비점 행에서 연결된 개선계획 상태 확인 가능
- 미비점에 개선계획이 없으면 그 행에서 바로 등록 가능 (deficiency_id 자동 채움)
- 미비점에 개선계획이 있으면 그 행에서 바로 상세(워크플로·이력) 진입 가능
- TypeScript 오류 없음
- 빌드 통과

### 5. 커밋 & push
```powershell
git add frontend/src/features/remediation/
git commit -m "refactor(frontend): 미비점·개선계획 화면 통합 (탭 분리 제거)"
git push -u origin feature/fe-remediation-unify
```

### 6. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-remediation-unify
git push origin main
```
