# ICFR-PROMPT-testfk-migration-B

## 목적
Test 계열 5개 테이블의 `control_id`(옛 controls.id)를 `baseline_control_id` / `instance_control_id`
두 컬럼으로 분리하는 **마이그레이션을 작성(B1)** 하고, **검토 승인 후 로컬 적용(B2)·검증(C)** 한다.
단계 A 로 사실 확인 완료. **B1 작성 직후 반드시 멈춰 보고**한다(적용 금지).
**로컬 한정** — 운영 접근·git push 금지. push 는 마스터가 백업 후 직접(마이그레이션 포함 커밋).

## 단계 A 확정값 (그대로 사용, 추정 금지)
- down_revision = **e7f8a9b0c1d2** (현재 head)
- 대상 5테이블: control_risk_assessments, test_runs, control_assertions, deficiencies, design_assessments
- 5테이블 모두 tenant_id NOT NULL. control_id 는 uuid. deficiencies.control_id 만 NULL 허용, 나머지 4개는 NOT NULL.
- 복합 FK 규약(기존과 동일, **컬럼 순서 주의**): `(baseline_control_id, tenant_id) → baseline_controls(id, tenant_id)` — 대상 유니크 `uq_baseline_controls_id_tenant(id, tenant_id)` 존재.
- instance FK: `instance_control_id → control_instances(id)` **단일 FK**(tenant 복합 아님).
- 백필: code 조인(controls.code = baseline_controls.code) + **동일 tenant**. 매핑 불가 0건(A 확인).
- 검증 기대값: control_assertions 백필 **469** 채워짐(93 아님).

## 설계값
1. 새 컬럼 `baseline_control_id`(uuid, nullable), `instance_control_id`(uuid, nullable).
2. CHECK: `NOT (baseline_control_id IS NOT NULL AND instance_control_id IS NOT NULL)` (둘 다 non-null 금지, 둘 다 NULL 허용).
3. 기존 `control_id`: **제거하지 않고** 4테이블을 nullable 로 완화(deficiencies 는 이미 nullable).
4. control_id NULL 행(deficiencies 2건)은 두 새 컬럼 모두 NULL 유지.

## 엄격 제약 (반드시 준수)
- 대상은 **로컬** icfr_db. 운영 접근·git push 금지.
- **B1 에서 마이그레이션 파일을 작성만 하고 STOP** — `alembic upgrade` 절대 실행 금지. 리비전 전문을 보고하고 승인 대기.
- B2(적용)는 **사용자 승인 이후에만**. 적용 실패 시 멈추고 로그 보고(강행·임의 DDL 금지).
- 적용 전 대상 5테이블 백업(`\copy`+`docker compose cp`, Out-File 금지).
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 편집·생성은 새 alembic 리비전 파일과 `_probe\*` 뿐. 다른 코드·문서·git 무변경.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 단계 B0 — 대상 5테이블 백업
각 테이블을 컨테이너 \copy 로 만들고 host 로 cp. 예:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -c "\copy control_risk_assessments TO '/tmp/pm_cra.csv' WITH CSV HEADER"
docker compose cp postgres:/tmp/pm_cra.csv E:\claudeprojects\ICFR\_probe\pm_control_risk_assessments.csv
```
test_runs, control_assertions, deficiencies, design_assessments 도 동일 패턴. 파일 존재·행수 확인.
현재 head 재확인:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\pm_head_before.txt
```
→ e7f8a9b0c1d2 확인.

## 단계 B1 — 마이그레이션 작성 (작성만, 적용 금지, STOP)
```
docker compose exec -T backend alembic revision -m "split test-family control_id into baseline/instance"
```
생성된 리비전 파일을 열어 `down_revision = 'e7f8a9b0c1d2'` 확인 후, upgrade()/downgrade() 를 아래대로 채운다.

upgrade() — 5테이블 각각:
- `op.add_column baseline_control_id` (UUID, nullable=True)
- `op.add_column instance_control_id` (UUID, nullable=True)
- 복합 FK: `create_foreign_key(None, <t>, 'baseline_controls', ['baseline_control_id','tenant_id'], ['id','tenant_id'])` — **컬럼 순서 정확히**.
- 단일 FK: `create_foreign_key(None, <t>, 'control_instances', ['instance_control_id'], ['id'])`.
- CHECK: `create_check_constraint('ck_<t>_ctrl_one', <t>, 'NOT (baseline_control_id IS NOT NULL AND instance_control_id IS NOT NULL)')`.
- 백필: `op.execute("UPDATE <t> AS x SET baseline_control_id = b.id FROM controls c JOIN baseline_controls b ON b.code = c.code AND b.tenant_id = x.tenant_id WHERE x.control_id = c.id")`.
- control_id 완화(NOT NULL 인 4테이블만): `op.alter_column('<t>', 'control_id', nullable=True)`. (deficiencies 는 생략.)

downgrade() — 역순: CHECK drop → 두 FK drop → 두 컬럼 drop → control_id 를 NOT NULL 로 원복(4테이블).
※ 주의 주석: downgrade 는 백필된 baseline/instance 값을 잃는다. control_id 원복 전 4테이블에 control_id NULL 행이 있으면 NOT NULL 복원이 실패할 수 있음(현재는 없음).

**여기서 STOP.** 리비전 파일 전문을 산출로 보고하고 **승인 대기**. B2 로 진행하지 말 것.

## 단계 B2 — 로컬 적용 (※ 승인 후에만)
```
docker compose exec -T backend alembic upgrade head > E:\claudeprojects\ICFR\_probe\pm_upgrade.txt
```
실패면 원인 보고(백업으로 복구 가능, 자동 재시도 금지).

## 단계 C — 검증 (읽기)
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'cra', count(*) FILTER (WHERE baseline_control_id IS NOT NULL) FROM control_risk_assessments UNION ALL SELECT 'runs', count(*) FILTER (WHERE baseline_control_id IS NOT NULL) FROM test_runs UNION ALL SELECT 'assert', count(*) FILTER (WHERE baseline_control_id IS NOT NULL) FROM control_assertions UNION ALL SELECT 'def_filled', count(*) FILTER (WHERE baseline_control_id IS NOT NULL) FROM deficiencies UNION ALL SELECT 'orphan', count(*) FILTER (WHERE control_id IS NOT NULL AND baseline_control_id IS NULL AND instance_control_id IS NULL) FROM control_assertions;" > E:\claudeprojects\ICFR\_probe\pm_verify.txt
```
기대: cra=2, runs=1, **assert=469**, def_filled=2, orphan=0. deficiencies NULL 2건은 두 컬럼 NULL 유지.
head 확인(새 리비전) 및 downgrade 왕복 리허설:
```
docker compose exec -T backend alembic downgrade -1 ; docker compose exec -T backend alembic upgrade head
```
왕복 후 위 검증 쿼리 재실행값이 동일한지 확인.

## 산출 (보고 형식)
1. B0: 백업 5파일 경로·행수, head_before=e7f8a9b0c1d2.
2. B1: 생성 리비전 파일 경로, `down_revision` 값, **upgrade()/downgrade() 전문** — 그리고 **미적용 상태**임을 명시하고 승인 대기.
3. (승인·적용 후) B2: upgrade 결과, 새 head.
4. C: 검증 카운트(cra2/runs1/assert469/def2/orphan0), downgrade 왕복 결과.
5. 로컬 한정·git 무변경·push 안 함 명시. 다음: 마스터가 백업 후 push(마이그레이션 포함 커밋).
