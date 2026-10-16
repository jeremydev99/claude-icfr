# ICFR-PROMPT-testfk-revid-rebase

## 목적
로컬 미커밋 리비전(f8a9b0c1d2e3, test-family split)이 origin 에 이미 병합된 **동일 ID 별개 리비전(EUC)**
과 충돌한다. 로컬 리비전을 잠시 대피 → origin pull(merge) → **origin tip 뒤로 새 ID 재배치** →
정적 검증한다. **B2(스키마 적용) 전에 멈춘다.** DB 적용·push 안 함.

## 확정 사실 (Claude Code fetch 로 확인됨)
- origin 체인(확정·병합): `e7f8a9b0c1d2 → f8a9b0c1d2e3(EUC) → a9b0c1d2e3f4(scoping)` = origin/main head.
- 로컬 f8a9b0c1d2e3(test-family split)은 ID 우연 충돌. 양보하는 쪽은 **로컬** — origin tip(a9b0c1d2e3f4) 뒤에 **새 ID**로 얹는다.
- 두 마이그레이션은 완전히 다른 작업이라 **내용 병합 금지**.

## 엄격 제약 (반드시 준수)
- **순서 엄수**: 대피 → pull → 재배치 → 검증. 로컬 리비전이 versions/ 에 있는 채로 pull 하면 alembic 즉시 깨짐.
- 대피는 **이동(백업)**이지 삭제 아님. 재배치 후 원본은 versions/ 에 없어야 한다(새 파일로 대체).
- pull 문서 충돌(ClaudeICFR.md 등) 나면 **원문만 떠서 멈추고 보고** — 임의 해결·`--theirs`/`--ours` 금지.
- `alembic upgrade`·DDL·DB 쓰기 금지. **B2 전 STOP.** push 금지(마이그레이션 포함 커밋은 마스터 몫).
- tenant 백필 보정(`c.tenant_id=x.tenant_id`)·CHECK/FK 이름은 **그대로 유지**.
- 백업 브랜치 있으면 유지. PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 단계 0 — 상태 스냅샷 + 안전망 (읽기)
```
git status ; git log --oneline -5 ; git fetch origin ; git log --oneline -3 origin/main
```
- 현재 브랜치·로컬 HEAD·미커밋 상태 기록. origin/main head 가 a9b0c1d2e3f4 인지 확인.
백업 브랜치(현재 HEAD 고정):
```
git branch backup/pre-revid-rebase-{date}
```

## 단계 1 — 로컬 리비전 대피 (versions/ 밖으로 이동)
로컬 test-family split 파일을 versions/ 밖 보관 위치로 **이동**한다(삭제 아님):
```
Move-Item backend\alembic\versions\*f8a9b0c1d2e3*test*split*.py E:\claudeprojects\ICFR\_probe\STASH_testfk_split.py
```
(정확한 파일명은 실제 경로로. 대상이 1개인지 먼저 확인 — 여러 개면 멈추고 보고.)
확인: versions/ 에 f8a9b0c1d2e3(split) 이 더 이상 없어야 한다.

## 단계 2 — origin pull (merge)
```
git rev-parse --abbrev-ref HEAD
git pull --no-rebase origin {branch}
```
`{branch}` 는 현재 브랜치.
- 충돌 없이 끝나면 계속. EUC(f8a9)·scoping(a9b0) 마이그레이션이 versions/ 에 들어왔는지 확인.
- 충돌 시(문서 등): 충돌 파일 목록 + ClaudeICFR.md 등 원문을 `_probe` 에 떠서 **멈추고 보고**. 재배치 진행 금지.

## 단계 3 — 로컬 리비전 재배치 (새 ID, tip 뒤)
대피본(STASH_testfk_split.py)을 versions/ 로 되살리되 **재배치**한다:
- 새 revision ID 발급: 기존 체인 패턴(12자리 hex)과 겹치지 않는 새 값(예: alembic revision 이 생성하는 형식). versions/ 및 origin 체인의 어떤 ID 와도 충돌하지 않을 것.
- `down_revision = 'a9b0c1d2e3f4'` 로 변경(현재 tip).
- 파일명도 새 ID·날짜 규약에 맞게 리네임하여 versions/ 에 배치. 대피본은 versions/ 밖에 남겨둠(중복 방지).
- upgrade()/downgrade() 본문은 **그대로 유지** — 특히:
  - 백필: `... AND b.tenant_id = x.tenant_id AND c.tenant_id = x.tenant_id`
  - CHECK 이름 `ck_{t}_ctrl_one`(upgrade/downgrade 동일), FK 이름 `fk_{t}_baseline_control_tenant` / `fk_{t}_instance_control`.

## 단계 4 — 정적 검증 (DB 무변경)
```
python -m py_compile backend\alembic\versions\<새파일>.py
```
컨테이너에 파일 반영은 이미지 재빌드 필요하므로, 이번엔 **로컬 파일 기준**으로 체인 정합을 확인:
- versions/ 에 down_revision=='a9b0c1d2e3f4' 인 파일이 우리 새 리비전 **하나뿐**인지.
- 같은 revision ID 를 쓰는 파일이 versions/ 에 **없는지**(충돌 해소 확인).
- 우리 새 ID 를 down_revision 으로 삼는 파일이 없어(단일 head) 분기 없는지.
- **alembic upgrade 는 실행하지 않는다.**
```
git status
```
→ 대피/재배치 결과가 스테이징 안 된 변경으로 보이는지 확인(add/commit 하지 않음).

## 산출 (보고 형식)
1. 백업 브랜치명, origin/main head=a9b0c1d2e3f4 확인.
2. pull 결과: 충돌 유무(있으면 원문 보고·중단), EUC·scoping 유입 확인.
3. 재배치: 새 revision ID, down_revision=a9b0c1d2e3f4, 새 파일명. 백필 tenant 보정·CHECK/FK 이름 **유지** 확인.
4. 정적 검증: py_compile 통과, ID 중복 없음, 단일 head, 분기 없음. **DB 미적용·git add/commit 안 함·push 안 함** 명시.
5. 다음: 승인 시 재빌드→B2(적용)→C(검증 assert=469, orphan=0, downgrade 왕복). 마이그레이션 포함 커밋 push 는 마스터.
