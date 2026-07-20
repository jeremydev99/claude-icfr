# UX 일관성 개선: 삭제 버튼·날짜·빈 목록·로딩 통일

## 목표
완성된 5개 모듈(rcm, test, remediation, evidence, users)에서 발견된 UX 불일치를 통일한다.
기능 변경 없이 표현만 일관되게 맞춘다.

## 범위 / 원칙
- 기능·로직·API 변경 금지. 순수 표현(스타일·문구·포맷) 통일만.
- 아키텍처 전환(ADR-0025)과 무관.
- 액션 버튼 표현(아이콘 vs 텍스트, hover 노출 등)은 이번 범위 **제외** — 화면 성격마다 달라 무리한 통일은 오히려 어색함.

## 사전 확인 (읽기만, 수정 금지)
- 각 모듈 테이블 컴포넌트 (rcm/ControlTable, test/TestRunTable, remediation/DeficiencyTable·RemediationPlanTable, evidence/EvidenceTable, users/UserTable·UserRoleTable)
- 삭제 다이얼로그가 있는 컴포넌트들
- `frontend/src/lib/utils.ts` (공통 유틸 위치 확인)

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-ux-consistency
```

### 2. 공통 날짜 포맷 유틸 추가
파일: `frontend/src/lib/utils.ts` (없으면 적절한 공통 위치)

- `formatDate(dateStr: string | null | undefined): string` 추가
  - null/빈값이면 빈 문자열 또는 '-' 반환
  - 유효한 날짜면 `YYYY-MM-DD` 형식으로 반환 (예: 2024-01-15)
- 모든 모듈에서 이 함수를 쓰도록 교체:
  - Test, Remediation: 기존 `dateStr.slice(0, 10)` → `formatDate(dateStr)`
  - Evidence: 기존 toLocaleDateString → `formatDate(...)`
  - Users: 기존 `toLocaleDateString('ko-KR')` (2024. 1. 15. 형식) → `formatDate(...)`
  - 결과적으로 전 화면이 `YYYY-MM-DD`로 통일

### 3. 삭제 버튼 스타일 통일
대상: Remediation(미비점), Users 등 `bg-red-600` 하드코딩된 삭제 버튼

- `bg-red-600 hover:bg-red-700` 하드코딩 → shadcn 표준 `variant="destructive"`로 교체
- 이미 `variant="destructive"`를 쓰는 RCM·Evidence는 그대로 유지
- 결과적으로 모든 삭제 확정 버튼이 동일한 destructive variant 사용

### 4. 빈 목록 안내 문구 통일
대상: RCM, Users(사용자) — 현재 짧은 문구만 있음

- 다른 모듈처럼 "안내 + 액션 유도" 형태로 통일:
  - RCM: 예) "등록된 통제가 없습니다." (검색 결과 없음과 최초 빈 상태를 구분해서, 검색 결과 없음은 "검색 결과가 없습니다" 유지, 데이터 자체가 없을 때만 액션 안내)
  - Users(사용자): "등록된 사용자가 없습니다. 사용자 등록 버튼으로 첫 사용자를 추가하세요."
- 문구 톤은 기존 다른 모듈(Test·Remediation)과 맞춤 ("~ 버튼으로 첫 ~를 추가하세요")

### 5. 로딩 상태 통일
전 모듈 테이블 로딩 표현을 하나로:

- 패턴: `Loader2` 아이콘(animate-spin) + "불러오는 중..." 텍스트, 아이콘 크기 `h-5 w-5`로 통일
- Test·Remediation·Users(아이콘만) → 텍스트 추가
- Evidence(텍스트만) → 아이콘 추가
- RCM(이미 아이콘+텍스트) → 크기만 h-5 w-5로 맞춤

## 완료 조건
- 전 화면 날짜가 YYYY-MM-DD로 동일하게 표시
- 모든 삭제 확정 버튼이 variant="destructive" 사용
- RCM·Users 빈 목록에 액션 안내 문구 표시 (RCM은 검색 결과 없음과 구분)
- 전 모듈 로딩 표현 통일 (아이콘+텍스트, h-5 w-5)
- 기능 변화 없음
- TypeScript 오류 없음
- 빌드 통과

### 6. 커밋 & push
```powershell
git add frontend/src/
git commit -m "style(frontend): UX 일관성 개선 — 날짜·삭제버튼·빈목록·로딩 통일"
git push -u origin feature/fe-ux-consistency
```

### 7. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-ux-consistency
git push origin main
```
