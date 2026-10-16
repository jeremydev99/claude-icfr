# ICFR-PROMPT-testfk-migration-fkless

## 목적
Test 계열 마이그레이션 `6b6d7fd94f0d` 를 **FK 없는 버전**으로 재작업한다.
코드베이스 지배 관례(FK 없이 resolver 검증, 13.9-27)에 맞추기 위함. **push 전이라 지금 리비전 직접 수정 가능.**
컬럼 2개·CHECK·백필·control_id 완화는 **유지**, DB FK 2개만 제거한다.
**로컬 한정** — 운영 접근·git push 금지. 협업 영역과 겹치지 않으나 시작 전 원격 변화 확인.

## 배경
- `6b6d7fd94f0d` 는 이미 **로컬 DB 에 적용됨**. 파일만 고치면 DB 와 어긋나므로 downgrade → 파일 수정 → 재적용 순서 필수.
- 현재 리비전 내용: 새 컬럼 2개 + 복합 FK(baseline) + 단일 FK(instance) + CHECK + 백필 + control_id 완화.
- 목표: FK 2개 제거. 나머지 전부 유지. resolver 검증은 **다음 프롬프트**(모델/서비스 전환)에서 추가.

## ⚠ 무결성 공백 주의
FK 제거 후 resolver 검증이 생기기 전까지 baseline/instance 컬럼에 임의 uuid 가 들어가도 DB 가 막지 못한다.
이 프롬프트 이후 **바로 모델·서비스 전환이 따라와야** 공백이 닫힌다. 그 사이 로컬에서 해당 컬럼 수동 주입 금지.

## 엄격 제약 (반드시 준수)
- 대상은 **로컬** icfr_db + 로컬 리비전 파일. 운영 접근·git push 금지.
- downgrade/upgrade 는 alembic 으로만. 임의 DDL·데이터 수정 금지.
- 리비전 파일 외 코드·문서·git 커밋 변경 금지(파일 수정은 워킹트리에만, add/commit 안 함).
- 실패 시 멈추고 로그 보고(백업 있음). 강행·자동 재시도 금지.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비 + 원격 변화 확인 (협업 안전)
```
Set-Location E:\claudeprojects\ICFR
docker compose up -d
git fetch origin ; git log --oneline -3 origin/main
```
- origin/main head 가 우리가 아는 tip(a9b0c1d2e3f4 반영 커밋) 대비 **새로 앞서갔는지** 확인.
- **새 커밋이 있으면**(특히 alembic/평가회차 관련) 멈추고 보고 — 동시 작업 충돌 가능. 없으면 계속.
- 현재 head 확인:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\fl_head_before.txt
```
→ 6b6d7fd94f0d 여야 한다.

## 단계 0 — 백업 재확인
`_probe\pm_*.csv`(5테이블) 존재·행수 재확인. 없으면 \copy+docker cp 로 다시 뜬다(Out-File 금지).

## 단계 1 — downgrade (6b6d7fd94f0d 되돌림)
```
docker compose exec -T backend alembic downgrade -1 > E:\claudeprojects\ICFR\_probe\fl_downgrade.txt
```
head 가 a9b0c1d2e3f4 로 내려갔는지 확인. FK·CHECK·새 컬럼이 제거되고 control_id 가 NOT NULL 로 복원됐는지 확인:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\fl_head_mid.txt
```

## 단계 2 — 리비전 파일 수정 (FK 제거)
`backend\alembic\versions\*6b6d7fd94f0d*test_family*split*.py` 수정:
- upgrade(): `create_foreign_key(... 'baseline_controls' ...)` 와 `create_foreign_key(... 'control_instances' ...)` **두 줄 제거**.
- **유지**: add_column ×2(baseline_control_id/instance_control_id, nullable), create_check_constraint(ck_{t}_ctrl_one), 백필 UPDATE(`AND b.tenant_id=x.tenant_id AND c.tenant_id=x.tenant_id`), control_id nullable 완화(4테이블).
- downgrade(): 대칭으로 **drop_constraint(fk_...) 두 줄 제거**. 유지: CHECK drop, 컬럼 2개 drop, control_id NOT NULL 복원.
- revision/down_revision(a9b0c1d2e3f4)·파일명은 **그대로**(내용만 FK-less 로).
- `python -m py_compile <파일>` 통과 확인.

## 단계 3 — 재빌드 → 재적용
```
docker compose build backend
docker compose up -d backend
```
startup 에서 alembic 이 6b6d7fd94f0d(FK-less)를 재적용. 로그 안 찍히면 DB 상태로 검증.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\fl_head_after.txt
```
→ 6b6d7fd94f0d 복귀.

## 단계 4 — 검증 (읽기)
컬럼 존재 + FK 부재 + CHECK 존재를 한 번에:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'cols', count(*) FROM information_schema.columns WHERE table_name='control_assertions' AND column_name IN ('baseline_control_id','instance_control_id') UNION ALL SELECT 'fk_base', count(*) FROM information_schema.table_constraints WHERE constraint_name='fk_control_assertions_baseline_control_tenant' UNION ALL SELECT 'fk_inst', count(*) FROM information_schema.table_constraints WHERE constraint_name='fk_control_assertions_instance_control' UNION ALL SELECT 'chk', count(*) FROM information_schema.table_constraints WHERE constraint_name='ck_control_assertions_ctrl_one';" > E:\claudeprojects\ICFR\_probe\fl_verify.txt
```
기대: cols=2, **fk_base=0, fk_inst=0**, chk=1.
백필 보존 재확인:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'assert', count(*) FILTER (WHERE baseline_control_id IS NOT NULL) FROM control_assertions UNION ALL SELECT 'orphan', count(*) FILTER (WHERE control_id IS NOT NULL AND baseline_control_id IS NULL AND instance_control_id IS NULL) FROM control_assertions;" > E:\claudeprojects\ICFR\_probe\fl_backfill.txt
```
→ assert=469, orphan=0.
downgrade 왕복 리허설:
```
docker compose exec -T backend alembic downgrade -1 ; docker compose exec -T backend alembic upgrade head
```
왕복 후 검증값 동일 확인.

## 산출 (보고 형식)
1. 원격 변화 확인 결과(새 커밋 유무), head_before=6b6d7fd94f0d.
2. downgrade 성공(head a9b0c1d2e3f4).
3. 리비전 수정: 제거한 FK 2줄(upgrade/downgrade), 유지 항목 확인, py_compile 통과.
4. 재적용 후 head=6b6d7fd94f0d.
5. 검증: cols=2 / fk_base=0 / fk_inst=0 / chk=1 / assert=469 / orphan=0 / 왕복 동일.
6. **로컬 한정·git add/commit 안 함·push 안 함** 명시. 리비전 파일은 워킹트리 변경으로만 존재.
7. 다음: 모델 4파일 새 컬럼 매핑 + resolver 검증(무결성 공백 닫기) → 라우트 → 시드 확인.
