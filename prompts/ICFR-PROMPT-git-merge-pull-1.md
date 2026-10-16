# ICFR-PROMPT-git-merge-pull-1

## 목적
진행 중인 rebase 를 abort 하고, 개정된 CLAUDE.md §8.3 방침대로 **`git pull --no-rebase`(merge)** 를 실행한다.
merge 충돌(ClaudeICFR.md)의 **양쪽 버전 텍스트만 추출해 보고하고 멈춘다.**
이 프롬프트는 **충돌을 해결하지 않는다.** commit·push 하지 않는다. DB·alembic·앱 코드 안 건드린다.

## 엄격 제약 (반드시 준수)
- git 조작만. 충돌 **해결 금지**(파일 편집·`git add`·`git commit` 금지).
- push 금지. `--skip`·`--theirs`/`--ours` 자동선택·임의 병합 금지.
- 백업 브랜치 `backup/pre-rebase-20260921` 는 유지(삭제 금지).
- `_probe\`, `prompts\*.md` 미추적 파일은 건드리지 않는다(add/stash 하지 말 것).
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
```

## 단계 0 — 백업 브랜치 존재 확인
```
git branch --list "backup/pre-rebase-20260921"
```
없으면 **멈추고 보고**(안전망 없이 진행 금지). 있으면 계속.

## 단계 1 — rebase abort (진행 전 상태 fa8cb9b 로 복귀)
```
git rebase --abort
```
복귀 확인:
```
git status ; git log --oneline -4
```
- HEAD 가 fa8cb9b 이고 working tree clean(미추적 제외)인지 확인. 아니면 멈추고 보고.

## 단계 2 — merge pull (§8.3 방침)
```
git fetch origin
```
현재 브랜치명 확인:
```
git rev-parse --abbrev-ref HEAD
```
그 브랜치로 merge pull:
```
git pull --no-rebase origin {branch}
```
`{branch}` 는 바로 위에서 확인한 이름.
- 충돌이 나면(예상: ClaudeICFR.md) 계속 단계 3 으로. **해결하지 말 것.**
- 충돌 없이 끝나면 단계 3 은 건너뛰고 산출 3-b 로 보고.

## 단계 3 — 충돌 지점 추출 (읽기만, 해결 금지)
충돌 파일 목록:
```
git diff --name-only --diff-filter=U > E:\claudeprojects\ICFR\_probe\mg_conflicts.txt
```
ClaudeICFR.md 의 충돌 구간(`<<<<<<<` ~ `=======` ~ `>>>>>>>`)을 있는 그대로 파일로 떠서 본다:
```
git diff ClaudeICFR.md > E:\claudeprojects\ICFR\_probe\mg_claudeicfr_diff.txt
```
각 충돌 hunk 마다 **양쪽 버전(ours=로컬 문서 커밋 / theirs=원격 문서 커밋)의 원문**을 절 번호(§14/§12.2/§13.9 등)와 함께 정리한다. **어느 쪽도 고르지 말고**, 원문만 보고한다.

## 산출 (보고 형식)
1. 백업 브랜치 확인, rebase abort 후 HEAD(=fa8cb9b) 복귀 확인.
2. `git pull --no-rebase` 결과: merge 진행 중인지, 충돌 파일 목록.
3-a. (충돌 시) ClaudeICFR.md 충돌 hunk 별로: 절 번호 · ours 원문 · theirs 원문 — 3곳 전부. **해결 안 함** 명시.
3-b. (충돌 없을 시) merge 완료 여부, HEAD, working tree 상태.
4. commit·push·파일수정 아무것도 안 했음 명시. DB/alembic/코드 무변경 명시.
5. 다음 단계 안내: 추출된 3곳으로 병합안을 확정한 뒤, 후속 프롬프트에서 해결·merge 커밋(push 는 별도 마스터 승인).
