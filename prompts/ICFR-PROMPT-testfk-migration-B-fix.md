# ICFR-PROMPT-testfk-migration-B-fix

## 목적
어제 작성한 리비전 `f8a9b0c1d2e3`(test-family control_id 분리)의 **백필 조인 tenant 보정**과
**CHECK 제약 이름 정합**을 확인·반영한다. 리비전 파일만 편집하고 **B2 적용 전 멈춘다**.
**로컬 한정** — DB 스키마 변경(alembic upgrade)·운영 접근·git push 금지.

## 배경 (어제 결정)
- 현재 백필: `UPDATE <t> AS x SET baseline_control_id=b.id FROM controls c, baseline_controls b WHERE x.control_id=c.id AND b.code=c.code AND b.tenant_id=x.tenant_id`
- 문제: controls(c) 에 tenant 조건이 없어, 멀티테넌트에서 code 만 같으면 **다른 tenant 의 baseline 을 끌어올 수 있는 구조**. tenant 1개인 지금은 무해하나 인프라 최종 기준상 지금 박는다.

## 엄격 제약 (반드시 준수)
- 읽기 + **리비전 파일 편집만**. `alembic upgrade`·DDL·DB 쓰기·git 변경 금지.
- 조회는 컨테이너 안 psql. 컬럼 존재는 **추정 금지** — 단계 1로 실제 확인 후 반영.
- 편집 후 **B2 실행하지 말고 STOP**, 변경 전문 보고·승인 대기.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비 (새 세션 — 스택 기동 포함)
```
Set-Location E:\claudeprojects\ICFR
docker compose up -d
```
head 확인(어제 상태 유지 검증):
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\bf_head.txt
```
→ e7f8a9b0c1d2 여야 한다(B 미적용 상태). f8a9b0c1d2e3 이면 이미 적용된 것이니 **멈추고 보고**.

## 단계 1 — controls.tenant_id 존재 확인
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='controls' AND column_name='tenant_id';" > E:\claudeprojects\ICFR\_probe\bf_controls_tenant.txt
```
- **한 줄 나옴(존재)** → 단계 2에서 백필에 `AND c.tenant_id = x.tenant_id` 추가.
- **비어 있음(없음)** → 백필은 code 단독 유지. 이 경우 보정 없이 그 사실만 보고하고, CHECK 이름(단계 3)만 확인.

## 단계 2 — 백필 조인 보정 (controls.tenant_id 있을 때만)
리비전 `backend/alembic/versions/*f8a9b0c1d2e3*` 의 `_backfill_sql` 을 아래로 수정한다:
```
UPDATE {t} AS x SET baseline_control_id = b.id
FROM controls c, baseline_controls b
WHERE x.control_id = c.id
  AND b.code = c.code
  AND b.tenant_id = x.tenant_id
  AND c.tenant_id = x.tenant_id
```
- 세 테이블(x, b, c) 모두 동일 tenant 로 묶여 교차 차단됨.
- 수정 후 `python -m py_compile` 로 구문 확인(파일 경로는 실제 리비전 경로).

## 단계 3 — CHECK 제약 이름 정합 확인
리비전에서 upgrade 의 `create_check_constraint` 이름과 downgrade 의 `drop_constraint` 이름이 **동일**한지 확인.
- 설계 이름 규약: `ck_<t>_ctrl_one`. upgrade 생성명과 downgrade 제거명이 테이블별로 일치해야 downgrade 가 깨지지 않음.
- 불일치가 있으면 downgrade 쪽 이름을 upgrade 와 **동일하게 맞춘다**(이름만 정합, 로직 변경 아님).
- FK 이름(fk_<t>_baseline_control_tenant / fk_<t>_instance_control)도 upgrade/downgrade 정합 재확인.

## 단계 4 — 정적 검증 (DB 무변경)
```
docker compose exec -T backend alembic heads > E:\claudeprojects\ICFR\_probe\bf_heads.txt
```
- head 가 f8a9b0c1d2e3 하나로 유지되고 체인 안 끊겼는지 확인.
- 리비전 파일 `py_compile` 통과 확인. **alembic upgrade 는 실행하지 않는다.**

## 산출 (보고 형식)
1. head 재확인(e7f8… = B 미적용) / controls.tenant_id 존재 여부.
2. 백필 보정: 적용했는지(controls.tenant_id 있을 때) / code 단독 유지(없을 때) — 수정된 `_backfill_sql` 전문.
3. CHECK·FK 이름 정합: upgrade/downgrade 이름 대조 결과, 수정했으면 전/후.
4. py_compile·alembic heads 통과, **DB 미적용·git 무변경·push 안 함** 명시.
5. 다음: 승인 시 `testfk-migration-B.md` 의 B2(적용)~C(검증 assert=469, downgrade 왕복) 진행.
