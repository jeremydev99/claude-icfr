# ICFR-PROMPT-git-merge-pull-2

## 목적
진행 중인 merge 의 ClaudeICFR.md 충돌 3곳을 **합의된 병합안**대로 해결하고,
`git add` → **merge 커밋**까지 만든다. **로컬에서만** 처리한다 — **push 하지 않는다**(마스터 몫).
DB·alembic·앱 코드는 건드리지 않는다. 편집 대상은 ClaudeICFR.md 1개뿐.

## 대전제 (반드시 준수)
- **push 금지.** 이 작업은 전부 로컬. 협업자·원격에 영향 없음(push 전까지).
- 편집은 ClaudeICFR.md 만. 자동 병합된 ~63개 staged 파일(CLAUDE.md, deploy.yml, alembic 2건 등)은 **건드리지 않는다**.
- 충돌 마커(`<<<<<<<`/`=======`/`>>>>>>>`)를 **전부 제거**한다. 하나라도 남으면 커밋 금지.
- `--theirs`/`--ours` 통째 선택 금지 — 아래 규칙대로 **양쪽을 병합**한다.
- 백업 브랜치 `backup/pre-rebase-20260921` 유지. `_probe\`·`prompts\*.md` 미추적 파일 손대지 않음.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
```

## 단계 0 — merge 진행 상태·안전망 확인 (읽기)
```
git status ; git branch --list "backup/pre-rebase-20260921"
```
- MERGE_HEAD 있는 merge 진행 중 + 백업 브랜치 존재 확인. 아니면 멈추고 보고.
- 충돌 파일이 ClaudeICFR.md(UU) 1개뿐인지 확인. 다른 UU 파일이 있으면 멈추고 보고.

## 단계 1 — 충돌 해결 (ClaudeICFR.md, 아래 규칙대로 편집)

### 충돌 ① §12.2 "담당자/권한" 행 — 한 행으로 병합
- BE 열: **theirs 그대로**(권한 가드·값 검증·중복 방지, require_role_assigner, 5역할 422, 활성 행 부분 유니크).
- FE 열: theirs 의 경고("역할 드롭다운 구 역할명 7종 → 422, FE 수정 대기")를 **"해소됨"으로 갱신**하고,
  그 뒤에 ours 문구 **"ROLE_ASSIGN_OPTIONS/ROLE_LABELS 분리 완료(df9b542·fa8cb9b), 브라우저 확인 대기"** 를 덧붙인다.
- 나머지 열/문구는 양쪽 동일 → 그대로.

### 충돌 ② §13.9-35 — theirs 35 정본, ours 는 36 으로 재번호 + 최신화
- theirs 의 "35. /api/users/roles 권한 가드·값 검증(2026-09-15 발견 → 09-16 BE 해소 → 09-18 운영 검증 완료, FE 드롭다운 잔여)" 및 그 "해소" 상세 문단 → **그대로 유지**.
- ours 의 "역할 UI 맵 분리(ROLE_ASSIGN_OPTIONS/ROLE_LABELS)" 항목 → **번호를 36 으로 변경**해 35 아래에 붙인다.
- **⚠ 최신화(단순 병합 아님)**: ours 의 "라벨 임시값(TODO)/협업자 확정 대기" 표현은 후속 커밋 **fa8cb9b("신규 5역할 라벨 확정")** 기준으로 낡았다. 이를 **"신규 5역할 라벨 확정(fa8cb9b)"** 으로 바꿔 적는다. "브라우저 미검증·push 대기"는 유지.

### 충돌 ③ §14 변경 로그 — theirs 8건 유지, ours 1건 날짜 위치 삽입
- theirs 8건(09-19~09-15, 최신순) → **순서 그대로 유지**.
- ours 1건 **"2026-09-16 / Regina + Claude — ROLE_NAME_OPTIONS 배정용/표시용 맵 분리 (df9b542)"** 를
  최신순 날짜에 맞게 **09-16 위치**(theirs 의 "09-16 역할 배정 가드" 항목 옆)에 끼워넣는다.

편집 후 마커 잔존 검사:
```
git diff --check ; Select-String -Path ClaudeICFR.md -Pattern "^(<<<<<<<|=======|>>>>>>>)"
```
둘 다 결과가 없어야 한다(마커 0). 남아 있으면 커밋하지 말고 보고.

## 단계 2 — staged 확인 후 커밋 (push 안 함)
```
git add ClaudeICFR.md
git status
```
- ClaudeICFR.md 가 해결됨으로 바뀌었고, 다른 UU 없음 확인. 자동 병합 staged 파일은 그대로 둔다.
- merge 커밋 생성(기본 merge 메시지 또는 명확한 한 줄):
```
git commit -m "merge: pull origin (문서 충돌 3곳 병합, 로컬 5역할 라벨 확정 반영)"
```

## 단계 3 — 검증 (읽기, push 안 함)
```
git log --oneline -6 ; git show --no-patch --format="%h parents=%p" HEAD
```
- HEAD 가 **부모 2개인 merge 커밋**인지 확인.
- origin 대비 로컬만 앞선 커밋 확인(merge 커밋 + 로컬 3):
```
git log --oneline origin/{branch}..HEAD
```
`{branch}` 는 현재 브랜치. **push 는 하지 않는다.**

## 산출 (보고 형식)
1. 단계 0: merge 진행 중·백업 브랜치·단일 충돌 확인.
2. 단계 1: 3곳 각각 어떻게 병합했는지 요약(특히 ②의 36 재번호 + fa8cb9b 최신화, ①의 FE 해소됨 갱신). 마커 0 확인.
3. 단계 2: 커밋 해시, staged 파일 수(자동병합분 포함).
4. 단계 3: merge 커밋 부모 2개 확인, origin 대비 앞선 커밋 목록. **push 안 했음** 명시.
5. ClaudeICFR.md 외 무편집, DB/alembic/코드 무변경 명시.
6. 다음 단계 안내: 이어서 `orphan-runs-delete.md`(고아 삭제) → `testfk-migration.md` 단계 A 재개. (원격 alembic 2건의 로컬 DB 적용은 단계 A5 에서 별도 확인.)
