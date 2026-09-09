# IMPL: canEditHierarchy — can_write 연결

## 목적
`canEditHierarchy()` 하드코딩 `true`를 제거하고, `/me` 응답의 백엔드 계산값 `can_write`로 편집 게이트를 판정한다.

배경: 백엔드 배포 완료. `/me`(UserRead) **top-level**에 두 필드가 추가됐다.
- `can_write: boolean` — `core/permissions.can_write` 계산값(require_write와 동일 함수). **버튼 숨김/비활성은 이 값으로.**
- `tenant_roles: string[]` — 활성 테넌트 운영 역할. 이번 작업엔 안 쓰지만 타입엔 넣어둔다(다음 역할 UI 안내 문구용).
- **FE는 external_auditor를 재판정하지 않는다.** `can_write`를 그대로 쓴다(권한 단일 소스). `can_write`는 UX 전용 — 서버가 최종 403.

## 제약 (엄수)
- 토큰 최적화: 전체 통독 금지. 아래 대상 파일·호출부만 읽는다.
- 새 라이브러리 도입 금지.
- 터미널 쓸 경우 PowerShell 5.1 (`grep`→`Select-String`, `&&`→`;`, `cd`→`Set-Location`).
- **push·배포 금지.** 구현·리포트까지만. 편집 게이트 변경이라 브라우저 검증 후 별도 지시로 push한다.

## 사전 검토 (구현 전 반드시)
1. `frontend/src/features/rcm/permissions.ts` — canEditHierarchy 현재 시그니처와 **모든 호출부** 확인. 훅 컨텍스트(컴포넌트)에서 불리는지 순수 함수에서 불리는지 판단 → store 접근 방식 결정 (`useAuthStore(selector)` vs `useAuthStore.getState()`).
2. `frontend/src/features/auth/store.ts` — `UserProfile` 타입 정의 위치, `/me` 응답이 store에 담기는 방식 확인(응답 spread인지 필드 명시 매핑인지).

## 구현
### A. 타입 / 매핑
- `UserProfile`에 필드 추가:
  - `can_write: boolean`
  - `tenant_roles: string[]`
- `/me` 응답 매핑이 필드를 **명시 선택**하는 구조면 두 필드도 매핑에 추가. spread면 타입 추가만으로 흐른다.

### B. canEditHierarchy
- 하드코딩 `true` 제거.
- 현재 사용자의 `can_write`를 반환. 사전 검토에서 정한 접근 방식 사용.
- **폴백: user 없음 / 미로그인 → `false`** (편집 버튼 숨김이 안전).
- ADR-0031 참조 주석 갱신(더 이상 미확정 아님 — `can_write`가 판정 소스).
- external_auditor·tenant_roles로 재판정하는 코드 넣지 말 것. `can_write` 하나만 본다.

### C. (가능하면) 단위 테스트
- 판정 로직을 순수하게 분리할 수 있으면(예: user를 받아 boolean 반환하는 헬퍼), vitest로 3케이스 고정: `can_write=true→true`, `false→false`, `user=null→false`. **jsdom 불필요**(DOM 없음). 깔끔히 분리 안 되면 생략하고 브라우저+백엔드 테스트에 의존.

## 보고
- 변경 파일·diff 요약.
- canEditHierarchy 호출부 목록과 선택한 store 접근 방식.
- `/me` 매핑이 spread였는지 명시 매핑이었는지.
- 단위 테스트 추가 여부.
- **push 안 함 확인.**

끝나면 위 리포트만. push·배포는 하지 않는다.
