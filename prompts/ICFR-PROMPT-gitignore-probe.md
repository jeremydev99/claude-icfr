# ICFR-PROMPT-gitignore-probe

## 목적
`_probe/`(실삭제 데이터가 든 백업 CSV·조사 산출물)를 `.gitignore` 에 추가해
push 대기 중인 리포에 **실수 커밋되는 사고를 원천 차단**한다.
**로컬만** — push 하지 않는다. DB·alembic·앱 코드·다른 문서 무변경.

## 엄격 제약 (반드시 준수)
- 편집 대상은 `.gitignore` 1개뿐. 이미 있으면 **끝에 한 줄 추가**(기존 내용 보존, 재정렬·삭제 금지).
- push 금지. 이 변경으로 새 커밋을 **만들지 여부는 아래 단계 3 판단**(기본: 워킹트리 반영까지만, 커밋은 선택).
- `_probe\` 안의 파일은 손대지 않는다(백업 CSV 보존).
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
```

## 단계 0 — 현재 상태 확인 (읽기)
`.gitignore` 존재 여부와 이미 `_probe` 항목이 있는지, `_probe\` 가 이미 추적 중인지 확인.
```
git ls-files _probe/ ; Test-Path .gitignore ; Select-String -Path .gitignore -Pattern "_probe" -SimpleMatch
```
- `git ls-files _probe/` 결과가 **비어 있어야** 정상(미추적). 만약 추적 중인 파일이 나오면 **멈추고 보고**(그 파일 처리 방침을 먼저 정해야 함 — 임의 `git rm` 금지).
- `.gitignore` 에 이미 `_probe` 가 있으면 추가 불필요 → 산출로 그 사실만 보고하고 종료.

## 단계 1 — .gitignore 에 한 줄 추가
`.gitignore` 가 없으면 생성, 있으면 끝에 아래 한 줄을 추가(기존 줄 보존):
```
_probe/
```
확인:
```
Select-String -Path .gitignore -Pattern "_probe" -SimpleMatch
git status --short
```
- `_probe\` 이하가 더 이상 `git status` 의 미추적 목록에 뜨지 않아야 한다(무시됨). `.gitignore` 만 변경/미추적으로 보여야 한다.

## 단계 2 — 무시 동작 검증 (읽기)
```
git check-ignore _probe/backup_test_runs.csv
```
→ 경로가 그대로 출력되면 무시 규칙이 걸린 것(정상). 아무것도 안 나오면 규칙이 안 먹은 것 → 보고.

## 단계 3 — 커밋 여부
- **기본: 커밋하지 않고 워킹트리 변경으로만 둔다**(다음 문서/설정 커밋 때 함께 올릴 수 있게). push 안 함.
- 다만 `.gitignore` 변경이 미추적/미커밋으로 남으면 다음 작업에서 헷갈릴 수 있으므로,
  **원하면** 단독 커밋 1개로 남긴다(push 금지):
```
git add .gitignore
git commit -m "chore: ignore _probe/ (local backup/probe artifacts)"
```
  커밋했으면 로컬 앞선 커밋이 5개가 됨을 산출에 명시. (이 커밋도 마스터 승인 후 push.)
  ※ 커밋할지 말지는 사용자 지시에 따른다. 지시 없으면 커밋하지 말고 워킹트리 변경으로만 두고 보고.

## 산출 (보고 형식)
1. `_probe\` 추적 여부(미추적 확인), `.gitignore` 기존 `_probe` 유무.
2. 추가한 줄과 `git check-ignore` 결과(무시 적용 확인).
3. 커밋했는지 여부(했다면 해시·앞선 커밋 수), **push 안 했음** 명시.
4. `.gitignore` 외 무편집, `_probe\` 파일 보존, DB/alembic/코드 무변경 명시.
5. 다음 단계 안내: 이어서 `testfk-migration.md` 단계 A(A0~A5) 재개.
