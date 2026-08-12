# ICFR-PROMPT-process-filter-dynamic

## 목적
RCM 통제 목록의 프로세스 필터 드롭다운이 하드코딩된 데모 값(`O2C/P2P/R2R/HR/ITG`)을 쓰고 있어, 실제 baseline 프로세스 코드(`EL/EX/FA/FR/HR/IT/SD/TR`, 8개)와 맞지 않아 HR을 제외한 모든 필터가 0건이 되는 버그를 수정한다. 하드코딩 배열을 제거하고 `GET /api/rcm/processes`에서 동적으로 옵션을 받아온다.

## 배경 (확정된 사실)
- 버그 원인: `frontend/src/features/rcm/components/ControlSearchBar.tsx:24`
  `const PROCESSES = ['O2C', 'P2P', 'R2R', 'HR', 'ITG']` — API 호출 없는 하드코딩. Phase 0 데모 데이터 값이며 baseline seed 도입 후 갱신 안 됨.
- 실제 DB `baseline_processes` 8개 코드/이름 (레거시 `processes` 활성 8행과 코드·이름 완전 동일):
  - EL 전사 / EX 경비관리 / FA 고정자산관리 / FR 재무결산과 보고 / HR 급여 및 인사관리 / IT 정보시스템관리 / SD 매출관리 / TR 자금관리
- 사용할 엔드포인트: `GET /api/rcm/processes` (backend/app/api/rcm.py:56-61, 이미 존재)
  - 응답 형태: `{ items: [ProcessRead...], total, skip, limit }`
  - `ProcessRead`: `id / code / name / description / created_at / updated_at`
  - 정확한 코드가 내려옴이 확인됨. 신규 백엔드 작업 불필요 — 프론트 단독 작업.

## 작업 범위
1. `ControlSearchBar.tsx`의 하드코딩 `PROCESSES` 배열 제거.
2. `GET /api/rcm/processes`를 TanStack Query로 호출해 동적으로 옵션 구성.
   - 프로젝트의 query key factory 패턴을 따를 것(RCM 쿼리 키 중앙화 구조 준수).
   - X-Tenant-Id 헤더 주입 축은 이미 axios 레이어에 live 상태이므로 별도 처리 불필요 — 기존 API 클라이언트/훅 패턴을 그대로 사용.
3. 드롭다운 옵션 렌더링:
   - **라벨(표시): `code — name`** 형식 (예: `EL — 전사`, `FA — 고정자산관리`).
   - **필터 value(선택값): `code`만** — 기존 필터 로직이 code 기준으로 거는 것을 유지. 라벨만 바꾸고 필터 키/동작은 변경 금지.
   - 기존 "전체" 옵션 유지.
4. 로딩/빈 상태 처리: 옵션 로딩 중에는 드롭다운이 깨지지 않게(빈 배열이어도 "전체"는 노출) 처리.

## 기존 코드 영향 사전 검토 (구현 전 반드시 확인)
- **필터 value가 code 기준인지 확인**: 현재 프로세스 필터가 선택값을 무엇으로 상태 관리/쿼리에 전달하는지(code인지 name인지) 먼저 코드로 확인한 뒤, code 유지 원칙에 맞춰 라벨만 교체. 만약 현재 로직이 code가 아닌 다른 키를 쓰고 있으면 진행 전 보고할 것.
- **`PROCESSES` 상수 재사용처 확인**: 이 상수를 다른 컴포넌트/파일에서 import해 쓰는 곳이 있는지 검색(Select-String). 있으면 함께 처리하거나 영향 범위를 보고.
- **쿼리 키 충돌 없는지 확인**: 새로 추가하는 processes 쿼리 키가 기존 키 팩토리와 충돌/중복되지 않도록.

## 범위 밖 (이번 작업에서 하지 말 것)
- mutation 연결(2-A-3) 관련 어떤 배선도 하지 않는다.
- envelope 필드 optional→required 전환 안 함.
- API 계약/백엔드 코드 변경 안 함.
- controls 목록 조회 로직 자체는 손대지 않음(필터 옵션 소스만 교체).

## 알려진 한계 (문서에 기록)
- `GET /api/rcm/processes`는 아직 resolver 기반이 아니라 레거시 `processes` 테이블을 직접 조회한다(resolve_processes 병합 경로 아님). 현재 tenant 1개 · instance 전부 0건(암묵 adopt)이라 실질 차이 없음.
- 향후 processes도 baseline/instance 병합(2-B급 전환)되어 tenant add/override 프로세스가 생기면, 이 엔드포인트도 resolver 기반으로 같이 갱신되어야 필터에 반영됨. 이 점을 `ClaudeICFR.md`의 해당 섹션(known limitation)에 기록할 것.

## 완료 기준
- 브라우저(RCM 관리 화면)에서 프로세스 필터 드롭다운이 실제 8개 코드(`EL — 전사` … `TR — 자금관리`)로 표시된다.
- 각 프로세스 필터 선택 시 실제 통제가 걸린다(0건 버그 해소). 참고 기대 분포(합계 93): EL 37 / EX 3 / FA 7 / FR 12 / HR 10 / IT 2 / SD 8 / TR 14.
- `npm run build` TS 에러 0건.
- 콘솔 envelope 계약 위반 에러 0건 유지.

## PowerShell 5.1 제약 (엄수)
- `&&`, `||`, `|`, `$()`, `2>&1`, heredoc, `grep`, `head` 금지. 명령 시퀀싱은 `;` 또는 개별 명령으로 분리.
- 파일 검색은 `grep` 대신 `Select-String` 사용.
- 경로는 `E:\` 스타일. `Set-Location` 사용.
- 단일 명령 965바이트 미만.

## 커밋
- 논리 단위 분리: 필터 수정(feat/fix) 커밋과 문서(docs, known limitation) 커밋을 나눈다.
- 커밋 메시지 예:
  - `fix(rcm): 프로세스 필터 드롭다운을 GET /api/rcm/processes 동적 조회로 전환`
  - `docs(state): 프로세스 필터 동적화 반영 및 processes resolver 미전환 한계 기록`
- 저위험(프론트 필터 옵션 소스 교체) 작업이므로 push 자동 승인 대상.

---
ICFR-PROMPT-process-filter-dynamic.md 진행해줘
