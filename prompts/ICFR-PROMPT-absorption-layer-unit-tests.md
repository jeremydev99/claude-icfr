# ICFR-PROMPT: 흡수 레이어 순수 로직 단위 테스트

## 목적
`cfaf4a7`로 확정된 흡수 레이어(flat→nested `SourceEnvelope` 어댑터 + 라우팅 헬퍼)의
**순수 로직**에 대한 단위 테스트를 작성한다. 백엔드 2-A-2 재마이그레이션과 무관하게
지금 진행 가능한 유일한 확정 범위다.

## 스코프 가드 (엄수)
- 뮤테이션 와이어링 **금지** — 헬퍼를 create/edit/delete/upload에 연결하지 않는다.
- 필드 optional→required 전환 **금지** — 2-A-3에서 할 일이다.
- API 계약 변경 **금지** — 어댑터/헬퍼 구현 로직을 바꾸지 않는다. **테스트만 추가**한다.
- 확정되지 않은 동작은 테스트하지 않는다. (아래 미해결 이슈 참고)

## 사전 확인 (테스트 작성 전 반드시)
1. Vitest 설치/설정 여부 확인 (`package.json`의 devDependencies + `vitest.config.*` 또는
   `vite.config.*`의 test 블록). 없으면 **여기서 멈추고 보고** — 세팅 여부는 사용자 판단 필요.
2. 대상 파일 실제 구현 상태 확인. 흡수 레이어가 "준비만" 된 상태로 기록돼 있어,
   헬퍼가 실제로 구현돼 있는지 먼저 확인한다:
   - flat→nested `SourceEnvelope` 어댑터 함수
   - `isBaseline`, `isTenantAdd`, `resolveDeleteSemantics`
   구현이 없으면 **멈추고 보고**. 스텁만 있으면 그 범위만 명시.

## 대상 파일 읽기 (토큰 최적화)
전체 통독 금지. 위 어댑터/헬퍼 **함수 본문과 시그니처만** 짧게 읽고,
실제 구현 로직에 맞춰 테스트를 작성한다. (동작을 추정하지 말 것.)

## 테스트 대상 및 케이스

### 1. flat→nested SourceEnvelope 어댑터
DTO의 flat 최상위 필드(`source`, `baseline_id`, `is_overridden`, `id`)를
nested 도메인 `SourceEnvelope`로 조립하는 로직.
- flat 필드가 모두 존재 → nested 객체 정상 조립
- flat 필드가 없음(optional, 레거시 응답) → 안전 처리(undefined/null 미크래시)
- `id`가 기존 item identity 필드를 재사용하는지 (nested wrapper 아님) 확인

### 2. isBaseline
실제 구현 기준(예: `source`/`baseline_id`)에 맞춰:
- baseline 아이템 → true
- tenant-added 아이템 → false
- 레거시(envelope 없음) 아이템 → 구현된 폴백 동작

### 3. isTenantAdd
`action` 기반 판정 로직에 맞춰:
- tenant-added → true
- baseline / overridden → false

### 4. resolveDeleteSemantics
`baseline_control_id`(nullable) + `action` 조합 기반:
- baseline 원본
- tenant 추가분
- override 분
각 케이스에서 반환되는 삭제 시맨틱 검증.

## 미해결 이슈 (테스트에서 회피)
overlay 판정은 `is_overridden` boolean 컬럼이 아니라 **`baseline_control_id` + `action`**
기반이다. resolver가 `action`→`is_overridden` 매핑을 제공하는지는 **미확정**.
따라서 어댑터 테스트는 "wire에서 온 flat 필드를 그대로 nested로 조립"하는 확정 동작만
검증한다. `action`으로부터 `is_overridden`을 **파생하는** 로직은 테스트하지 않는다
(확정 시 별도 추가).

## 마무리
- `npm run build` (TS 0 에러) + 테스트 실행 통과 확인.
- 결과 요약: 대상 함수, 케이스 수, 통과/실패, 사전 확인에서 걸린 항목.
- 문서/체인지로그는 아직 갱신하지 않는다(검증 대기 항목과 함께 다음 커밋에서).

---
`ICFR-PROMPT-absorption-layer-unit-tests.md 진행해줘`
