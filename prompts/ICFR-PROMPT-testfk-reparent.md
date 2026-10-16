# ICFR-PROMPT-testfk-reparent

## 목적
로컬 커밋된 리비전 `6b6d7fd94f0d`(test-family split)가 origin 에 병합된 `b1c2d3e4f5a6`(scoping refine)
와 **같은 부모(a9b0c1d2e3f4)** 를 가져 alembic branch(head 2개)가 될 상황이다.
로컬 리비전을 **origin tip(b1c2d3e4f5a6) 뒤로 재배치**(down_revision 변경)해 단일 head 로 되돌린다.
**revision ID 는 6b6d7fd94f0d 그대로 유지**(ID 충돌 아님, 부모만 겹침). **DB 무변경. push 안 함.**
fkless(스키마 실변경)는 **다음 프롬프트** — 이 프롬프트는 git+체인 정리까지만, fkless 전 STOP.

## 확정 사실 (Claude Code fetch 로 확인됨)
- origin/main 3커밋 앞섬(…→70d765c, 6-1b 스코핑 정제). 새 리비전 `b1c2d3e4f5a6`(down_revision=a9b0c1d2e3f4) 병합됨.
- 로컬 `6b6d7fd94f0d`(down_revision=a9b0c1d2e3f4)는 커밋 `0707e45`(미push).
- 둘이 a9b0c1d2e3f4 아래 형제 → 재배치로 로컬을 b1c2d3e4f5a6 뒤에 직렬화.

## 엄격 제약 (반드시 준수)
- **순서 엄수**: 대피 → pull → 재배치 → 커밋 반영 → 검증. 로컬 리비전이 versions/ 에 있는 채 pull 하면 branch.
- **revision ID 는 바꾸지 않는다**(6b6d7fd94f0d 유지). **down_revision 만** a9b0c1d2e3f4 → b1c2d3e4f5a6.
- **DB 무변경**: `alembic upgrade/downgrade` 실행 금지. 로컬 DB head(6b6d7fd94f0d)는 그대로 둔다.
- pull 문서 충돌(§14 등) 나면 **원문만 떠서 멈추고 보고** — 임의 해결 금지.
- push 금지(마이그레이션 포함 커밋은 마스터). 백업 브랜치 유지.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
git fetch origin ; git log --oneline -3 origin/main ; git status
```
- origin/main head=70d765c 확인, 로컬 HEAD=0707e45, 브랜치명 기록.
백업 브랜치:
```
git branch backup/pre-reparent-{date}
```

## 단계 1 — 로컬 리비전 대피 (versions/ 밖으로 이동)
```
Move-Item backend\alembic\versions\*6b6d7fd94f0d*test_family*split*.py E:\claudeprojects\ICFR\_probe\STASH_reparent_split.py
```
(대상 1개 확인 — 여러 개면 멈추고 보고.) versions/ 에 6b6d7fd94f0d 없어야 함.
※ 이건 워킹트리 이동일 뿐이라 커밋 0707e45 에는 아직 파일이 남아 있음 — 단계 3에서 정리.

## 단계 2 — origin pull (merge)
```
git rev-parse --abbrev-ref HEAD
git pull --no-rebase origin {branch}
```
- 충돌 없으면 계속. b1c2d3e4f5a6 유입·origin 3커밋 반영 확인.
- 충돌 시: 파일 목록 + 원문 `_probe` 로 떠서 **멈추고 보고**. 재배치 진행 금지.
- 주의: 대피본이 versions/ 밖에 있어도 커밋 0707e45 의 6b6d7fd94f0d 파일은 병합 대상에 남아 있을 수 있음 — merge 후 versions/ 에 그 파일이 되살아나면 단계 3에서 재배치로 흡수.

## 단계 3 — 재배치 + 커밋 반영
로컬 test-family split 리비전 파일을 versions/ 에 두되(대피본 기준 또는 merge 로 돌아온 것),
**down_revision 만** 변경하고 나머지는 그대로:
- `down_revision = 'b1c2d3e4f5a6'` (기존 'a9b0c1d2e3f4' 에서 변경)
- revision = '6b6d7fd94f0d' 유지, 파일명 유지, upgrade()/downgrade() 본문(FK 2개·CHECK·백필·완화) **그대로**.
- 대피본(_probe\STASH_reparent_split.py)이 versions/ 밖에 중복으로 남지 않게 정리(versions/ 에 정본 1개만).
`python -m py_compile` 통과 확인.
로컬 커밋 0707e45 에 이 변경을 반영(push 안 한 로컬 커밋이므로 amend 안전):
```
git add backend\alembic\versions\*6b6d7fd94f0d*.py
git commit --amend --no-edit
```
- amend 후 그 커밋이 merge 로 들어온 히스토리 위에 올바로 얹혔는지 확인(로그).

## 단계 4 — 정적 검증 (DB 무변경)
- versions/ 전수: down_revision=='b1c2d3e4f5a6' 인 파일이 우리 6b6d7fd94f0d **하나뿐**, 그 자식 없음(단일 head).
- a9b0c1d2e3f4 의 자식이 b1c2d3e4f5a6 하나로 정리됐는지(형제 해소).
- revision ID 중복 없음(전수).
- **alembic upgrade/downgrade 실행 안 함.** 로컬 DB head 는 여전히 6b6d7fd94f0d(질의로만 확인):
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\rp_dbhead.txt
```
→ 6b6d7fd94f0d(DB 안 건드렸으니 그대로). 파일 체인상 down_revision 만 바뀐 것이라, 재빌드·재적용은 fkless 프롬프트에서 함께 처리.

## 산출 (보고 형식)
1. 백업 브랜치, origin/main head=70d765c, pull 충돌 유무(있으면 원문·중단).
2. 재배치: revision=6b6d7fd94f0d(유지), down_revision=b1c2d3e4f5a6(변경), 본문 그대로 확인.
3. 커밋 amend 결과(해시), 히스토리 정합.
4. 정적 검증: 단일 head, 형제 해소, ID 중복 없음, py_compile 통과.
5. **DB 무변경(로컬 head 6b6d7fd94f0d 그대로)·push 안 함** 명시.
6. 다음: `testfk-migration-fkless.md`(FK 제거 재작업) 진행 — 이제 체인이 b1c2d3e4f5a6 뒤로 정리됐으니 그 위에서 downgrade→수정→재적용.
