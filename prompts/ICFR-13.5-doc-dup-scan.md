# ICFR-13.5 문서 중복 정리 — 스캔 조사 전용

## 목적
프로젝트 문서(마크다운/프롬프트/상태보드/ADR) 전반의 **중복 지점을 식별**한다.
이번 작업은 **조사(read-only)만** 한다. 삭제/병합/수정/커밋 없음.

## 스코프 가드 (엄수)
- 문서 **수정·삭제·이동 금지**. 열람·검색만.
- 코드 파일(.ts/.tsx/.py 등)은 대상 아님. **문서만**(.md 위주).
- 새 파일 생성 금지(보고는 대화창에 텍스트로). git 조작 금지.
- 큰 문서는 **필요한 부분만** 발췌 확인(전체 통독 금지).

## 조사 항목

### 1. 문서 인벤토리
- 프로젝트 내 문서 목록 수집
  - `Get-ChildItem -Path E:\claudeprojects\ICFR -Recurse -Include *.md -File | Where-Object { $_.FullName -notmatch "node_modules" } | Select-Object FullName, Length`
- 각 문서의 역할 한 줄 요약(상태보드 / 프롬프트 / ADR / README / 기타)

### 2. 중복 유형별 식별
아래 3가지 관점으로 중복을 찾는다.

**(a) 문서 간(cross-file) 중복**
- 같은 정보가 여러 문서에 반복 기재된 곳
  - 예: 스택 정보, 경로/URL, 계정 정보, 워크플로 절차, 아키텍처 설명 등이 상태보드·README·프롬프트에 중복
- 검색 예: `Select-String -Path E:\claudeprojects\ICFR\*.md,E:\claudeprojects\ICFR\prompts\*.md -Pattern "icfr.synap.co.kr|EXCEL_UPLOAD_LOCKED|SourceEnvelope|cascade" -List`

**(b) 문서 내(within-file) 중복**
- ClaudeICFR.md 등 상태보드에서 같은 항목이 12/13/14 섹션에 중복 기재되거나, 오래된 항목과 갱신 항목이 병존하는 곳
- 완료된 항목이 여전히 "진행 중/대기"로 남아 있는 stale 기재

**(c) 프롬프트 파일 간 중복**
- prompts\ 폴더 내 ICFR-*.md 들이 동일 스코프 가드/PowerShell 제약/워크플로 문구를 반복하는지(이건 의도된 반복일 수 있음 — 판단만)

### 3. stale/모순 탐지
- 완료됐는데 미완료로 적힌 항목, 서로 모순되는 기재(예: 같은 커밋/상태가 다르게 기록)
- 버려진(더 이상 참조 안 되는) 문서 후보

## 산출물 (보고 형식 — 대화창 텍스트)
1. 문서 인벤토리: 파일 / 역할 / 크기 (표 또는 목록)
2. 중복 지점 목록: 각 항목마다
   - 유형 (a/b/c)
   - 무슨 정보가
   - 어느 문서:라인 vs 어느 문서:라인 에 중복
   - 심각도(높음=모순/stale, 중간=단순 반복, 낮음=의도된 반복 가능)
3. stale/모순 항목 별도 목록
4. 정리 방향 제안(어떤 걸 단일 소스로 두고 어디를 참조로 바꿀지) — **제안만**, 실행 금지

## PowerShell 5.1 제약
- `&&` 금지 → `;` 또는 명령 분리
- `grep` 금지 → `Select-String`
- `cd` 금지 → `Set-Location E:\claudeprojects\ICFR`
- bash 경로·heredoc·`2>&1` 금지
- 단일 명령 965 bytes 이내

---
ICFR-13.5-doc-dup-scan.md 진행해줘
