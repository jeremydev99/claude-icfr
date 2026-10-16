# ICFR-PROMPT-doc-freshen-amend

## 목적
방금 merge 커밋(783bad2)의 ClaudeICFR.md 에 남은 **낡은 문구 2곳**을 갱신하고,
`git commit --amend` 로 그 merge 커밋에 합친다. **로컬만** — **push 하지 않는다**.
편집 대상은 ClaudeICFR.md 1개뿐. DB·alembic·앱 코드 무변경.

## 대전제 (반드시 준수)
- **push 금지.** amend 는 로컬 커밋만 고쳐 쓴다(783bad2 는 아직 원격에 없으므로 안전).
- 편집은 ClaudeICFR.md 만. 다른 파일·`_probe\`·`prompts\*.md` 손대지 않음.
- 사실 기반 최신화만 — 없는 내용 창작 금지. 두 지점 외 다른 절 수정 금지.
- 백업 브랜치 `backup/pre-rebase-20260921` 유지.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 줄바꿈은 현재 파일과 동일(CRLF) 유지.

## 준비
```
Set-Location E:\claudeprojects\ICFR
```

## 단계 0 — 상태 확인 (읽기)
```
git log --oneline -3 ; git status
```
- HEAD 가 783bad2(merge, 부모 2개)이고 추적 파일 clean 인지 확인. 아니면 멈추고 보고.
- **HEAD 가 이미 origin 에 push 됐으면(origin/{branch} 에 783bad2 존재) amend 금지** — 멈추고 보고(히스토리 재작성 위험).
```
git branch -r --contains 783bad2
```
결과에 origin/{branch} 가 없어야 안전.

## 단계 1 — 문구 갱신 (ClaudeICFR.md 2곳)

### 갱신 ① §13.9-43 본문의 13.9-24 문구
- 현재: "13.9-24(기존 3행 의미 불명확)는 그대로 남아 있다" 취지의 문장.
- 사실: 원격이 **2026-09-18 시드 정리로 13.9-24 를 해소**했다.
- 조치: 해당 문장을 **"13.9-24 는 2026-09-18 시드 정리로 해소됨"** 취지로 갱신.
  (43번의 나머지 본문·번호·소제목은 그대로.)

### 갱신 ② §13.9-35 의 "FE 드롭다운 잔여" 표기에 해소 포인터 추가
- 현재: 35번 본문에 "잔여 ①: FE 드롭다운"(미해소로 읽힘)이 남아 있음.
- 사실: 그 FE 잔여는 **이번 커밋의 13.9-43(df9b542·fa8cb9b)에서 해소**됨.
- 조치: 35번 본문은 두고, 그 잔여 줄 끝에 **"→ 13.9-43 에서 해소"** 포인터 한 조각만 덧붙인다.
  (35번 본문 삭제·재작성 금지 — 포인터만 추가.)

### 마커·정합 검사
```
git diff --check ; Select-String -Path ClaudeICFR.md -Pattern "13.9-24|13.9-43|잔여" | Select-Object -First 20
```
- 충돌 마커 0. 두 지점이 의도대로 바뀌었는지 눈으로 확인. 그 외 diff 가 없는지:
```
git diff --stat
```
→ ClaudeICFR.md 만 바뀌어 있어야 한다.

## 단계 2 — merge 커밋에 amend (push 안 함)
```
git add ClaudeICFR.md
git commit --amend --no-edit
```
- `--no-edit` 로 기존 merge 메시지 유지. 새 커밋 해시가 생김(merge 커밋의 부모 2개는 유지되는지 확인).
```
git show --no-patch --format="%h parents=%p" HEAD
```
→ 부모 2개 유지 확인. (amend 가 merge 커밋의 부모를 보존하는지 반드시 확인 — 안 되면 멈추고 보고, 절대 push 금지.)

## 단계 3 — 검증 (읽기, push 안 함)
```
git log --oneline -6 ; git log --oneline origin/{branch}..HEAD
```
`{branch}` 는 현재 브랜치. origin 대비 앞선 커밋이 여전히 4개(amend된 merge + 로컬 3)인지 확인. **push 하지 않는다.**

## 산출 (보고 형식)
1. 단계 0: HEAD=merge 커밋 확인, 783bad2 가 원격에 없어 amend 안전함 확인.
2. 단계 1: 갱신 ①②를 실제로 어떻게 바꿨는지(전/후 문구), 다른 곳 무변경(diff --stat) 확인.
3. 단계 2: amend 후 새 커밋 해시, **부모 2개 유지** 확인.
4. 단계 3: origin 대비 앞선 커밋 4개, **push 안 했음** 명시.
5. ClaudeICFR.md 외 무편집, DB/alembic/코드 무변경 명시.
6. 다음 단계 안내: 이어서 `orphan-runs-delete.md`(고아 3건 삭제) → `testfk-migration.md` 단계 A.
