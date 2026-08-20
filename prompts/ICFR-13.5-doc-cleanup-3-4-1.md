# ICFR-13.5 문서 정리 — 높은 심각도 3+4+1 + Regina 문서 역할 확인

## 목적
스캔에서 나온 높은 심각도 항목 중 코드 무영향·회귀 위험 없는 **문서 3건**을 정리한다.
추가로 Regina_ClaudeContext.md의 **역할·구조를 확인만** 하여 보고한다(폐기/유지 판단은 사용자 몫).

## 대상 (이번에 실제 수정)
- 항목3: ADR SSOT 결손 해소
- 항목4: 존재하지 않는 docs 경로 참조 정리
- 항목1: 모듈 수 불일치 정리

## 스코프 가드 (엄수)
- **문서(.md)만 수정.** 코드 파일(.ts/.tsx/.py 등) 절대 건드리지 않는다.
- 아래 명시된 파일·섹션 외 **다른 문서 수정 금지**.
- Regina_ClaudeContext.md는 이번에 **수정하지 않는다**(역할 확인·보고만).
- 정보 갱신 시 **없는 사실을 지어내지 않는다.** 원문(ADR 프롬프트 파일 등)에서 확인된 내용만 반영.
- bypass/무승인 모드 사용 금지 — 편집은 per-command 승인으로.

## 작업 상세

### 항목3 — ADR-0024/0025/0027 §10 요약 추가 (SSOT 결손 해소)
1. 원문 위치 확인·발췌: `prompts/ICFR_adr_0024_*.md`, `ICFR_adr_0025_*.md`, `ICFR_adr_0027_*.md`
   - 각 ADR의 **제목/결정 요지/상태**만 짧게 추출(전체 통독 금지)
2. `ClaudeICFR.md` §10(ADR 목록)에 각 ADR을 **10줄 이내**로 요약 추가
   - 형식은 §10의 기존 ADR 기재 형식을 그대로 따를 것
   - ADR-0027은 "skip 금지 / 2차 테넌트 온보딩 선결" 성격 명시
3. 이미 §14 변경로그·본문이 이 ADR들을 인용 중이므로, 번호·제목이 인용부와 **일치**하는지 확인

### 항목4 — 미존재 docs 경로 참조 정리
- 대상: `CLAUDE.md §3`, `README.md` 핵심문서표에서 참조하는 `docs/adr/`, `docs/api/`, `docs/erd/`
- 실제 해당 디렉터리 존재 여부 먼저 확인:
  - `Test-Path E:\claudeprojects\ICFR\docs\adr; Test-Path E:\claudeprojects\ICFR\docs\api; Test-Path E:\claudeprojects\ICFR\docs\erd`
- 존재하지 않으면 해당 참조에 **"(예정)"** 표기 추가(경로 자체는 향후 계획일 수 있으므로 삭제보다 표기 우선)
  - 단, 명백히 폐기된 참조로 판단되면 삭제하되 **판단 근거를 보고**할 것

### 항목1 — 모듈 수 불일치 정리
- `README.md:22-32`이 모듈 "9개"로 기재, `ClaudeICFR.md:39-50`은 "11개"(Report·Test 포함)
- **ClaudeICFR.md를 정답(SSOT)으로 간주.** README.md 모듈 목록을 현재 상태에 맞춰 갱신
  - 또는 README에서 목록 나열을 걷어내고 "모듈 목록은 ClaudeICFR.md §참조"로 단일화(권장 — 재발 방지)
  - 둘 중 어느 쪽으로 갈지 판단하고, 판단 근거를 보고

### Regina 문서 — 역할 확인만 (수정 금지)
- `Regina_ClaudeContext.md`를 열어 **구조(섹션 목록)와 용도**를 파악
- 확인 보고 항목:
  1. 이 문서의 목적/역할 (무엇을 위한 문서인가)
  2. 섹션 구성 요약
  3. ClaudeICFR.md와 **역할이 겹치는지**(중복 문서인지) 아니면 별도 용도인지
  4. 마지막 갱신 시점과 stale 정도
- **판단·수정은 하지 않는다.** 위 보고만.

## 커밋 원칙
- 문서 수정이므로 `docs:` 커밋으로 묶는다(feat/fix와 분리).
- 이번 건은 코드 무영향·회귀 위험 없음 → **커밋까지 진행, push는 사용자 확인 후**.
  (Regina 문서 폐기/유지 방향이 아직 안 정해졌으므로 관련 변경 없음을 커밋 메시지에 반영)
- 커밋 전 변경된 문서 diff 요약을 보고할 것.

## 산출물
1. 항목3/4/1 각각 무엇을 어떻게 바꿨는지 diff 요약
2. Regina_ClaudeContext.md 역할 확인 보고(위 4항목)
3. `docs:` 커밋 메시지 초안

## PowerShell 5.1 제약
- `&&` 금지 → `;` 또는 명령 분리
- `grep` 금지 → `Select-String`
- `cd` 금지 → `Set-Location E:\claudeprojects\ICFR`
- bash 경로·heredoc·`2>&1` 금지
- 단일 명령 965 bytes 이내

---
ICFR-13.5-doc-cleanup-3-4-1.md 진행해줘
