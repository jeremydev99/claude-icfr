# PROMPT: envelope optional → required 전환 (Process/SubProcess/Risk)

## 목적
상위 3계층(Process/SubProcess/Risk)의 `envelope` 필드를 optional에서 required로 조인다.
조회가 전부 resolver 경유로 넘어와 envelope 없을 경로가 사라졌으므로(TrustBuilder 확정),
타입을 required로 조여 향후 envelope 누락 경로를 컴파일 단계에서 차단한다.

**조회 경로만 건드린다. mutation·신규 화면은 이 프롬프트 범위 아님.**

## 작업 디렉토리
Set-Location E:\claudeprojects\ICFR\frontend

## 사전 조건 (조사 완료 사실 — 재확인만, 추정 금지)
- `src/features/rcm/types.ts`: ProcessItem(109) / SubProcessItem(117) / RiskItem(126)에 `envelope?: SourceEnvelope` optional 선언 존재
- `src/features/rcm/api/sourceEnvelope.ts`:
  - `buildSourceEnvelope` (21-45): required 빌더, 부재 시 throw / PROD 안전값 폴백 — **통제(control)가 이미 사용 중인 검증된 빌더**
  - `buildOptionalSourceEnvelope`: optional 빌더, 부재 시 undefined
  - `SourceEnvelope` 타입 정의 (13-18): {id, source, baseline_id, is_overridden}
- `src/features/rcm/api/controlsAdapter.ts`: toProcessItems(64) / toSubProcessItems(76) / toRiskItems(89)에서 현재 `buildOptionalSourceEnvelope` 호출 중
- 통제(toControl:44)는 이미 `buildSourceEnvelope`(required) 사용 → 이 패턴을 상위 3계층에 맞춘다

## 변경 작업

### 1. types.ts — optional 제거
ProcessItem / SubProcessItem / RiskItem 세 곳:
- `envelope?: SourceEnvelope` → `envelope: SourceEnvelope`

### 2. controlsAdapter.ts — required 빌더로 교체
toProcessItems / toSubProcessItems / toRiskItems 세 곳:
- `buildOptionalSourceEnvelope(...)` → `buildSourceEnvelope(...)`
- import 문에 `buildSourceEnvelope`가 없으면 추가. `buildOptionalSourceEnvelope`가 이 파일에서 더 이상 안 쓰이면 import에서 제거

### 3. buildOptionalSourceEnvelope 잔여 사용처 확인
- Select-String으로 `buildOptionalSourceEnvelope` 전체 사용처 검색
- 상위 3계층 어댑터 외 다른 사용처가 있으면 **건드리지 말고 보고만**. 없으면 정의 자체 제거는 하지 않고 그대로 둔다(이번 범위 아님, 별도 정리)

## 검증 (필수)

### 타입 체크
- `npx tsc --noEmit` 실행 → envelope 관련 타입 에러 0건 확인
- required 전환으로 새 에러가 뜨면, 그 위치가 조회 경로인지 mutation/기타 경로인지 구분해서 보고. 조회 경로 밖이면 임의 수정 말고 멈추고 보고

### 브라우저 회귀 확인
아래를 먼저 켜고 진행:
- 백엔드/DB 컨테이너: docker compose up -d
- 프론트: frontend 디렉토리에서 npm run dev
확인 항목:
- RCM 매트릭스 93건 정상 렌더
- 프로세스/서브프로세스/리스크 컬럼 정상
- source 배지(baseline 표시) 정상 노출
- 콘솔 에러 없음

## push 판단
- 조회 경로 한정 변경 + 통제 검증 패턴 재사용 + 타입체크·브라우저 회귀 통과 → **저위험, 자동 push 승인**
- 단 tsc에서 조회 경로 밖 에러가 나오면 push 전 멈추고 보고

## 커밋 분리
- feat/fix 커밋: types.ts + controlsAdapter.ts 변경 (envelope required 전환)
- docs 커밋: ClaudeICFR.md §12/§14 업데이트 (envelope optional→required 전환 완료 기록, 2-A-3 관련 상태 갱신)
- 두 커밋 분리, --no-ff merge to main

## 제약
- PowerShell 5.1: `grep` 금지 → `Select-String`, `&&` 금지 → `;`, `2>&1` 금지, `cd` 대신 `Set-Location`
- 단일 명령 965바이트 제한, 다단계는 별도 명령 분리
- alembic 등 DB 스키마 변경 명령 없음 (이번 작업은 프론트 타입만)
