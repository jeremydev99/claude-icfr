# PROBE: mutation 라우팅 헬퍼 연결부 + envelope optional 상태 확인

## 목적
envelope optional→required 전환과 mutation 라우팅 헬퍼 배선을 위한 사전 조사.
**읽기 전용. 파일 편집·코드 변경 금지. 확인 결과만 보고할 것.**

## 작업 디렉토리
Set-Location E:\claudeprojects\ICFR\frontend

## 확인 항목 (순서대로)

### 1. envelope optional 필드 현재 위치
- `src/**/types.ts`에서 `ProcessItem` / `SubProcessItem` / `RiskItem`의 `envelope?: SourceEnvelope` optional 선언 확인
- `SourceEnvelope` 타입 정의 위치와 구조

### 2. 라우팅 헬퍼 정의부
- `buildOptionalSourceEnvelope` 정의 위치·시그니처
- 그 외 source/baseline 라우팅 관련 헬퍼가 더 있는지 (예: mutation 시 source 분기 결정 헬퍼)
- controlsAdapter.ts의 `toProcessItems` / `toSubProcessItems` / `toRiskItems` 호출부

### 3. 통제(control) mutation 배선 — 참조 템플릿
통제는 상위 3계층과 동일 계약이므로 이걸 기준으로 상위 3계층을 맞춘다.
- 통제 CRUD mutation 훅(POST/PATCH/DELETE) 위치와 이름
- 통제 mutation이 source/baseline/is_overridden을 요청·응답에서 어떻게 다루는지
- 통제 mutation에서 라우팅 헬퍼를 실제로 호출하는 지점이 있는지

### 4. 상위 3계층 mutation 현황
- Process / SubProcess / Risk에 대한 CRUD mutation 훅이 이미 존재하는지
- 존재한다면: 라우팅 헬퍼 연결 여부, 미연결이면 어디가 비어있는지
- 부재한다면: 그 사실만 기록 (이 프롬프트에서 만들지 않음)

### 5. mutation 파일 구조
- mutation 훅들이 모여있는 디렉토리·파일 패턴 (TanStack Query useMutation 위치)

## 제약
- PowerShell 5.1: `grep` 금지 → `Select-String`, `&&` 금지 → `;`, `2>&1` 금지
- 검색은 Select-String -Pattern 사용
- 파일 편집·생성·삭제·npm 실행 없음

## 산출물
각 항목별로 **파일 경로 + 관련 줄 + 현재 연결 상태(연결됨/미연결/부재)**를 표로 정리.
특히 3번(통제 배선 방식)과 4번(상위 3계층 현황)의 차이가 실행 프롬프트의 핵심이므로 명확히.
