# ICFR-PROMPT-2A3-1-envelope-required

## 목적
RCM 흡수 레이어의 `SourceEnvelope` 관련 필드(`source` / `baseline_id` / `is_overridden`)를 **optional → required**로 전환한다. 조회 응답에 envelope가 항상 존재함이 확정됐으므로, 타입 계약을 optional에서 required로 좁혀 이후 mutation 배선(2-A-3-2)이 안전한 전제 위에서 진행되게 한다.

이번 작업은 **조회 계층 타입 정합성 전환만** 수행한다. mutation 훅 생성·UI 배선·lock 해제는 이번 범위가 아니다(2-A-3-2).

## 배경 (확정된 사실)
- 백엔드 리졸버(`control_resolver.py:_resolve_layer`)가 응답 dict에 envelope 필드를 **flat top-level**로 항상 채워 내려준다:
  - `source`: `"baseline"` | `"tenant"`
  - `baseline_id`: baseline id 또는 `None`(tenant add인 경우)
  - `is_overridden`: 서버 읽기 시점 계산값(`inst.action == "override"` → true). **DB 물리 컬럼 아님.**
- `is_overridden`은 물리 컬럼이 아니라 서버 계산값임이 코드로 확정됨(ClaudeICFR.md 13.4 항목6).
- 현재 FE 흡수 레이어는 이 필드들을 **optional**로 두고 어댑터에서 safe undefined fallback으로 처리 중(commit cfaf4a7). 흡수-준비 상태이며 아직 required가 아님.
- 기존 단위 테스트: `sourceEnvelope.test.ts` 17개 통과(buildSourceEnvelope / buildOptionalSourceEnvelope / isBaseline / isTenantAdd / resolveDeleteSemantics).

## 최우선 사전 확인 (구현 전 반드시 수행, 결과 보고)
required 전환의 핵심 리스크: **4계층(process / sub_process / risk / control) 중 하나라도 조회 응답에 envelope를 채워 내려주지 않으면, required 전환이 그 계층 조회를 런타임에서 깨뜨린다.**

따라서 코드 수정 전에 다음을 먼저 확인하고 보고할 것:
1. **백엔드 4계층 응답에 envelope flat 필드가 모두 실재하는지** — `control_resolver.py` / `rcm.py`에서 process / sub_process / risk / control 각 조회 응답이 `source` / `baseline_id` / `is_overridden`을 실제로 내려주는지 코드로 확인. controls만 되고 상위 계층은 아직 안 내려주는 경우가 있으면, 그 계층은 이번 required 전환에서 **제외**하고 별도 항목으로 분리해 보고.
2. **FE 흡수 레이어 현재 optional 지점 목록** — DTO 타입 / 도메인 타입 / 어댑터에서 `source?` / `baseline_id?` / `is_overridden?` optional로 선언된 지점을 4계층 각각에 대해 Select-String으로 찾아 목록화.
3. 위 1·2 결과를 대조해, **실제 required 전환 가능한 계층**을 확정한 뒤 진행. (백엔드가 안 내려주는 계층을 FE에서 required로 만들면 안 됨 — 추정 금지, 코드 근거로만 판단.)

이 사전 확인 결과를 먼저 보고하고, 전환 대상 계층이 확정되면 코드 수정으로 진행한다.

## 작업 범위 (사전 확인 통과 계층에 한해)
1. **DTO 타입**: envelope 필드 optional(`?`) 제거 → required.
2. **도메인 타입**: `SourceEnvelope` 및 이를 포함하는 도메인 타입에서 envelope 관련 optional 제거 → required.
3. **어댑터**: optional 전제의 safe undefined fallback을, required 전제에 맞게 정리. (fallback이 더 이상 도달 불가능하면 제거하되, 방어적으로 남길 필요가 있는 지점은 근거와 함께 판단.)
4. **빌드/타입 정합**: optional 제거로 발생하는 컴파일 에러 지점을 required 계약에 맞게 수정.

## 범위 밖 (이번 작업에서 하지 말 것)
- mutation 훅(`usePatchControl` / `useDeleteControl` 등) **생성 금지**. 이번엔 조회 계층 타입 전환만.
- 수정/삭제 UI 배선, 확인 다이얼로그, mutation lock 해제 **금지**(2-A-3-2).
- 헬퍼(`isBaseline` / `isTenantAdd` / `resolveDeleteSemantics`)를 UI/mutation에 **연결 금지**(정의는 유지, 배선은 다음 단계).
- 백엔드 코드 / API 계약 변경 **금지**.
- create(신규 tenant add) 관련 작업 **금지**.

## 완료 기준
- 사전 확인에서 통과한 계층의 envelope 필드가 DTO·도메인·어댑터에서 required로 전환됨.
- `sourceEnvelope.test.ts` 17개 전부 통과 유지(required 전환으로 깨지는 테스트가 있으면 원인 보고 후 조정).
- `npm run build`(tsc+vite) TS 에러 0건.
- 브라우저(RCM 관리 화면) 재확인: 통제 목록 정상 렌더링, source 배지 정상, 콘솔 envelope 계약 위반 에러 0건. (전환 대상에서 제외된 계층이 있으면 그 사유를 함께 기록.)

## PowerShell 5.1 제약 (엄수)
- `&&`, `||`, `|`, `$()`, `2>&1`, heredoc, `grep`, `head` 금지. 시퀀싱은 `;` 또는 개별 명령.
- 파일 검색은 `grep` 대신 `Select-String`.
- 경로는 `E:\` 스타일, `Set-Location` 사용. 단일 명령 965바이트 미만.
- 테스트/빌드는 개별 명령으로: `Set-Location E:\claudeprojects\ICFR\frontend` 후 `npx vitest run <경로>` / `npm run build` 각각 실행(와일드카드 금지).

## 커밋
- 논리 단위 분리: required 전환(refactor/feat) 커밋과 문서(docs) 커밋을 나눈다.
- 전환 대상에서 제외된 계층이 있으면 그 사유를 ClaudeICFR.md에 known limitation으로 기록.
- 커밋 메시지 예:
  - `refactor(rcm): SourceEnvelope 필드 optional→required 전환 (조회 계층)`
  - `docs(state): envelope required 전환 반영 및 전환 범위 기록`
- required 전환은 조회 계층 전반에 닿는 변경이므로, **브라우저 검증 완료 후 push**. 검증 전 자동 push 금지 — 검증 결과 확인 후 사용자 승인.

---
ICFR-PROMPT-2A3-1-envelope-required.md 진행해줘
