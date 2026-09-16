# ICFR-PROMPT-role-map-split

## 목적
`ROLE_NAME_OPTIONS` 한 덩어리가 **셀렉터 저장값**과 **표시 라벨**을 동시에 먹여서, 신규 역할 배정 시 구·PascalCase(`ExternalAuditor`)가 저장되고 백엔드(`external_auditor`)와 어긋나는 구조를 분리한다. **이번 작업은 FE 내부 구조(맵 분리)만.** 실제 배정값 wire·검증·API 변경은 하지 않는다.

## 하드 룰 (반드시 준수)
- **로컬 변경만. git push / 배포 절대 금지.** 커밋까지만(원하면), push는 사용자.
- 백엔드·마이그레이션·API 호출부·검증 로직 **손대지 않는다.**
- 신규 5역할 한글 라벨은 **임시값**이다(협업자 미확정). TODO 주석으로 임시임을 명시.
- PowerShell 5.1: `&&` 금지(`;` 사용), `grep` 금지(`Select-String`), `cd` 대신 `Set-Location`.

## 대상 파일 (먼저 실물 확인 후 수정)
- 정의: `frontend/src/features/users/types.ts` (ROLE_NAME_OPTIONS, 61–69 부근)
- 사용처:
  - `UserRoleFormDialog.tsx` (36, 171) — 역할 선택 `<Select>` 옵션
  - `UserDetailSheet.tsx` (20, 43) — `roleLabel()` 라벨 변환
  - `UserRoleTable.tsx` (14, 40) — `roleLabel()` 테이블 뱃지

## 작업
1. **types.ts에 맵 2개로 분리**
   - `ROLE_ASSIGN_OPTIONS` — **배정용, 신규 5역할만 선택 가능**. 값은 snake_case 정규값:
     `icfr_manager`, `ceo`, `auditor`, `external_auditor`, `sys_admin` (ADR-0031)
     라벨은 임시 한글 + `// TODO: 협업자 라벨 확정 대기` 주석.
   - `ROLE_LABELS` — **표시용, 구7종 + 신규5역할 전체** `Record<string,string>`.
     구7종(`Administrator/ProcessOwner/ControlOwner/Tester/Reviewer/ExternalAuditor/Executive`)은 **기존 한글 라벨 그대로 유지**(뱃지 공백 방지).
2. **roleLabel() 헬퍼** → `ROLE_LABELS[role_name] ?? role_name` 로 통일(미지 값은 원문 문자열 폴백, 절대 공백 금지). UserDetailSheet·UserRoleTable 둘 다 이 헬퍼 참조.
3. **UserRoleFormDialog 셀렉터** → `ROLE_ASSIGN_OPTIONS` 참조(신규 5역할만 노출).
4. 기존 `ROLE_NAME_OPTIONS` export를 참조하는 **다른 import가 없는지 확인**(현재 위 3곳 외 없음으로 파악됨). 남아있으면 알리고 멈춘다.

## 검증
- `npm run typecheck` (또는 tsc) 통과.
- users feature 테스트만 실행(와일드카드 금지): 예 `npx vitest run src/features/users`.
- 브라우저 확인 필요 시: `docker compose up -d` 후 프론트 기동해 역할 셀렉터에 신규 5역할만 뜨는지, 기존 사용자 뱃지가 안 깨지는지 눈으로 확인.

## 폴백 (회귀 위험 큰 경우만)
- `roleLabel()` 시그니처/호출부가 얽혀 깔끔한 분리가 위험하면, **types.ts 맵 분리만 먼저** 반영하고 호출부 교체는 별도 커밋으로 쪼갠다. 이때 그 위험을 명시 보고.

---
`ICFR-PROMPT-role-map-split.md 진행해줘`
