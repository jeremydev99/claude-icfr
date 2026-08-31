# ICFR-PROMPT-hierarchy-crud-survey

## 목적
상위 3계층(process / sub_process / risk) CRUD를 프론트에 배선하기 **전에**, 실제 백엔드 규격·기존 프론트 패턴·UI 배치 자리를 확정한다. 이 조사 없이 코딩에 들어가면 "배선할 자리 없는 함수"만 쌓이거나, UI 형태를 나중에 갈아엎는 retrofit이 발생한다.

## 절대 원칙
- **읽기 전용.** 코드/문서/DB 어떤 것도 수정·생성·삭제하지 않는다. `git`/파일 편집/마이그레이션/seed 금지.
- **추정 금지.** 특히 API 규격·DB는 실제 파일 내용을 읽어서 사실만 보고. 확인 안 된 건 "미확인"으로 명시.
- 조사만 하고, 배선 방안 제안·설계 결정은 하지 않는다(그건 이 조사 결과를 받아 별도 논의).

## 조사 항목

### 1. 백엔드 상위 3계층 CRUD API 실제 규격 (추정 금지, rcm.py 실제 확인)
`backend/app/api/rcm.py`와 관련 스키마(`backend/app/schemas/rcm.py`)를 읽고, process / sub_process / risk 각각에 대해:
- 실제 존재하는 엔드포인트 (메서드 + 경로). create/update/delete 각각 있는지, 없으면 "없음" 명시.
- 요청 payload 스키마 (필드명·타입·필수 여부). 특히 `action`(adopt/exclude/override/add) 필드를 어떻게 받는지.
- 응답 형태가 통제와 동일한 **flat envelope**(`source` / `baseline_id` / `is_overridden` + `id`)인지 실제로 확인.
- 어서션 junction(control↔assertion)이 상위계층 CRUD와 어떻게 얽히는지 (cascade 규칙이 API 응답/동작에 어떻게 드러나는지).

### 2. Scoping 화면 원래 설계 의도
- `frontend/src/` 에서 Scoping 관련 컴포넌트/라우트를 찾아 현재 상태 확인 (지금 "준비중 — Phase 1 구현 예정" 플레이스홀더).
- 코드·주석·인접 문서(ClaudeICFR.md, docs/adr)에서 Scoping이 **상위계층 관리(제외/포함/CRUD)를 담을 자리로 설계됐는지** 단서 확인.
- Phase 1 범위에 상위계층 관리가 포함되는지, 아니면 별개인지 근거와 함께 판별. 근거 없으면 "설계 의도 불명확"으로 명시.

### 3. 기존 control CRUD 배선 패턴 (재사용 대상 식별)
control이 이미 가진 배선을 계층으로 정리:
- API 함수: `controlsApi.ts`의 통제 CRUD 함수 구조 (fetch/create/update/delete 각 시그니처).
- mutation 훅: `useControls.ts`의 훅 구조 (useDeleteControl 등, TanStack Query invalidation 패턴).
- 어댑터: `controlsAdapter.ts` / `sourceEnvelope.ts`의 DTO→도메인 변환 + envelope 조립 + `resolveDeleteSemantics` 패턴.
- UI: `RcmPage.tsx`의 삭제 버튼 → 확인 다이얼로그(DeleteConfirmDialog) → mutation 흐름.
- 이 중 상위 3계층에 **그대로 재사용 가능한 것 / 계층별로 새로 만들어야 하는 것**을 구분.

### 4. 상위계층 조회 데이터가 지금 프론트 어디까지 들어와 있는지
- `controlsApi.ts`의 `fetchProcesses` / `fetchSubProcesses` / `fetchRisksBySubProcessId`가 현재 **어디서 호출**되는지 (필터 드롭다운 채우는 용도만인지, 목록 렌더링에도 쓰이는지).
- 상위계층을 **목록으로 보여주는 화면/컴포넌트가 존재하는지** (CRUD 버튼을 얹을 목록 UI가 이미 있는지, 아니면 목록 자체를 새로 만들어야 하는지).
- `ProcessItem` / `SubProcessItem` / `RiskItem` 타입의 현재 필드 구조 (envelope optional 필드 포함 여부 재확인).

## 산출물 형식
항목별로 "확인된 사실"과 "미확인/불명확"을 분리해서 표 또는 짧은 불릿으로 보고. 각 사실에는 근거 파일·라인을 붙일 것. 마지막에 한 줄 요약: **상위계층 관리 UI를 놓을 자리가 (a) 이미 있음 / (b) Scoping에 만들어야 함 / (c) 신규 화면 필요** 중 어디인지, 근거와 함께 잠정 판별(확정 아님, 논의용).

## 실행 후
조사 결과를 받아 배선 접근·범위(계층별 파일럿 vs 3계층 일괄, UI 형태·위치)를 논의하고, OK 후 실제 배선 프롬프트를 작성한다. **이 프롬프트 단계에서는 배선을 시작하지 않는다.**
