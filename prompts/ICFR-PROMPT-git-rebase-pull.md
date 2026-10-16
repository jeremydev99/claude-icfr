# ICFR-PROMPT-git-rebase-pull

## 목적
로컬을 원격(40커밋 앞섬) 위로 **rebase-pull** 해서 히스토리를 선형으로 맞춘다.
로컬 3커밋(df9b542, d929c80, fa8cb9b)을 원격 위로 올려 alembic head 갈라짐을 막는다.
**git 만 다룬다** — DB·alembic·마이그레이션·앱 코드 일절 건드리지 않는다. **push 하지 않는다.**

## 엄격 제약 (반드시 준수)
- 이 프롬프트는 git 조작만. DB 조회·alembic·코드 수정 금지.
- **push 금지**(로컬 3커밋 push 는 별건, 마스터 승인 사항 — CLAUDE.md §8).
- rebase 중 **충돌이 나면 즉시 멈추고 보고**한다. 임의 해결·강행·`--skip`·`--theirs`/`--ours` 자동선택 금지.
- 작업 전 현재 상태를 백업 브랜치로 남긴다(되돌리기 안전망).
- `_probe\`, `prompts\*.md` 등 미추적 파일은 건드리지 않는다(add/commit/stash 하지 말 것).
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
```

## 단계 0 — 현재 상태 스냅샷 (읽기)
```
git status ; git log --oneline -8 ; git rev-parse --abbrev-ref HEAD
```
- 브랜치명, 로컬 HEAD, 미추적/변경 파일을 기록.
- **추적 파일에 커밋 안 된 변경이 있으면 멈추고 보고**(rebase 전에 정리 필요). 미추적(_probe, prompts)만 있으면 계속.

## 단계 1 — 백업 브랜치 (안전망)
현재 HEAD 를 가리키는 백업 브랜치를 만든다(체크아웃하지 않음).
```
git branch backup/pre-rebase-{date}
```
`{date}` 는 오늘 날짜(예 20260921). 생성 확인:
```
git branch --list "backup/*"
```

## 단계 2 — 원격 최신 가져오기 (머지 아님)
```
git fetch origin
```
갈라짐 재확인:
```
git log --oneline --left-right --count HEAD...origin/{branch}
```
`{branch}` 는 단계 0 의 현재 브랜치. 기대: 로컬 3 / 원격 40 근방.

## 단계 3 — rebase 실행
로컬 3커밋을 origin/{branch} 위로 올린다.
```
git rebase origin/{branch}
```
- **충돌 시**: 멈춘다. `git status` 로 충돌 파일 목록만 뽑아 보고하고, 여기서 종료.
  임의 해결 금지 — 사용자/마스터 판단 후 다음 프롬프트로 처리.
- **성공 시**: 계속.

## 단계 4 — 결과 검증 (읽기)
```
git log --oneline -10 ; git status
```
확인 사항:
- 로컬 3커밋(df9b542, d929c80, fa8cb9b)이 원격 최신 위에 **일렬로** 얹혔는지(선형).
- 원격 alembic 2건(user_roles_unique, org_partial_unique)이 히스토리에 포함됐는지.
- working tree clean(미추적 _probe/prompts 제외).
- **origin 보다 로컬이 앞선 커밋이 정확히 3개**인지(`git log --oneline origin/{branch}..HEAD`).

## 산출 (보고 형식)
1. 백업 브랜치명.
2. rebase 결과: 성공/충돌. 충돌이면 충돌 파일 목록과 중단 지점, 그리고 **아무것도 push/변경 안 함** 명시.
3. 성공이면: 현재 HEAD, origin 대비 앞선 커밋 3개 목록, alembic 2건 포함 여부, working tree 상태.
4. **push 하지 않았음** 명시(로컬 3커밋은 마스터 승인 후 별도 push).
5. 다음 단계 안내: 이어서 `orphan-runs-delete.md` → `testfk-migration.md` 단계 A 재개.

## 롤백 (필요 시 참고 — 자동 실행 금지)
rebase 가 꼬였고 되돌려야 하면: `git rebase --abort`(진행 중일 때) 또는
`git reset --hard backup/pre-rebase-{date}`(완료 후 되돌릴 때). 실행은 사용자 지시 후에만.
