# ICFR-PROMPT-testfk-migration

## 목적
Test 계열 5개 테이블의 `control_id`(옛 controls.id 참조)를 정체성 체계에 맞게
**`baseline_control_id` / `instance_control_id` 두 컬럼으로 분리**한다(선택지 2).
스키마 사실을 먼저 확인하고(단계 A), 그 규약에 맞춰 alembic 마이그레이션을 초안·**로컬 적용·검증**한다(단계 B~C).
**운영 적용·push 는 하지 않는다** — 마스터 검토 후 마스터가 직접.

## 대상 테이블 (5)
control_risk_assessments, test_runs, control_assertions, deficiencies, design_assessments

## 설계값 (확정안 — 단계 A 사실과 충돌하면 멈추고 보고)
1. 새 컬럼 2개: `baseline_control_id`, `instance_control_id` — **둘 다 NULL 허용**.
2. CHECK: **둘 다 non-null 금지**(둘 다 NULL 은 허용). deficiencies 의 control_id NULL 2건과 향후 add-통제 케이스를 위해 "정확히 하나"가 아니라 "둘 다 아님"으로 둔다.
3. 기존 `control_id`: **제거하지 않고 NULL 허용으로만 완화**(additive, 되돌리기 쉬움). 컬럼 제거는 앱 코드 전환 후 별도 마이그레이션.
4. FK 규약: `baseline_control_id` 는 **기존 baseline_controls 참조 규약과 동일하게**(복합 FK `(tenant_id, baseline_control_id) → baseline_controls(tenant_id, id)` 인지 단일 FK 인지 단계 A 에서 확인 후 일치). `instance_control_id → control_instances(id)`.
5. 데이터 백필: 기존 `control_id`(옛 controls.id) → `baseline_control_id` 로 **code 조인**(controls.code = baseline_controls.code, **동일 tenant 내**). 현재 Test 행은 전부 baseline 대응(이전 조사). control_id NULL 은 둘 다 NULL 유지.
6. **선행조건: 고아 test_run 3건(test-001/002/003) 삭제 완료.** 안 됐으면 마이그레이션 진행 금지.

## 엄격 제약 (반드시 준수)
- 대상은 **로컬 icfr_db 뿐**. 운영 접속·운영 적용·git push 금지(마스터 몫).
- 단계 A(확인)·단계 C(검증)는 읽기 전용. 단계 B 는 마이그레이션 파일 **작성**과 **로컬 적용**만.
- 스키마 사실은 **추정 금지** — 단계 A 로 실제 확인한 값으로만 마이그레이션을 짠다. 확인 안 된 값이 있으면 멈추고 보고.
- 적용 전 대상 테이블 백업을 `_probe` 에 남긴다.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 마이그레이션 파일과 `_probe\*` 백업 외 다른 코드·ClaudeICFR.md 수정 금지.

## 준비
```
Set-Location E:\claudeprojects\ICFR
docker compose up -d
```

## 단계 A — 스키마 사실 확인 (읽기 전용, 멈춰 보고)

### A0 — 선행조건: 고아 삭제 완료 확인
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT count(*) FROM test_runs WHERE id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6');" > E:\claudeprojects\ICFR\_probe\m0_orphan.txt
```
→ 0 이 아니면 **멈추고 보고**(먼저 orphan-runs-delete 완료 필요).

### A1 — 5개 테이블의 tenant_id 유무 + control_id 타입
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT table_name, column_name, is_nullable, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('control_risk_assessments','test_runs','control_assertions','deficiencies','design_assessments') AND column_name IN ('tenant_id','control_id') ORDER BY table_name, column_name;" > E:\claudeprojects\ICFR\_probe\m1_cols.txt
```

### A2 — baseline_controls 참조 규약 (복합 FK 인지)
기존에 baseline_controls 를 참조하는 FK 들이 (tenant_id, id) 복합인지 단일인지 본다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT tc.table_name, tc.constraint_name, string_agg(kcu.column_name,',' ORDER BY kcu.ordinal_position) AS cols, ccu.table_name AS ref FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name=ccu.constraint_name WHERE tc.constraint_type='FOREIGN KEY' AND ccu.table_name='baseline_controls' GROUP BY 1,2,4 ORDER BY 1;" > E:\claudeprojects\ICFR\_probe\m2_basefk.txt
```

### A3 — baseline_controls / control_instances PK·유니크 (복합 FK 대상 존재 확인)
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT tc.table_name, tc.constraint_type, string_agg(kcu.column_name,',' ORDER BY kcu.ordinal_position) FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name WHERE tc.table_name IN ('baseline_controls','control_instances') AND tc.constraint_type IN ('PRIMARY KEY','UNIQUE') GROUP BY 1,2 ORDER BY 1,2;" > E:\claudeprojects\ICFR\_probe\m3_pk.txt
```

### A4 — code 조인 안전성 재확인 (동일 tenant, 1:1)
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT (SELECT count(*) FROM controls) AS controls_n, (SELECT count(*) FROM controls c JOIN baseline_controls b ON b.code=c.code) AS code_match, (SELECT count(*) FROM (SELECT code FROM baseline_controls GROUP BY code HAVING count(*)>1) x) AS base_dup;" > E:\claudeprojects\ICFR\_probe\m4_join.txt
```

### A5 — alembic 현재 head 확인
```
docker compose exec -T backend alembic current > E:\claudeprojects\ICFR\_probe\m5_alembic.txt
```

**단계 A 종료: 위 결과를 보고한다.** 설계값(특히 4번 복합 FK 여부, 5번 code 1:1)과 실제가
일치하면 단계 B 로. 어긋나면 마이그레이션을 어떻게 조정할지 먼저 합의.

## 단계 B — 마이그레이션 작성 + 로컬 적용 (승인 후)

### B0 — 대상 테이블 백업 (롤백 안전망)
5개 테이블을 `_probe\backup_premigration_<table>.csv` 로 COPY TO STDOUT (utf8) 백업. 각 파일 비어있지 않은지 확인.

### B1 — 마이그레이션 파일 생성
`alembic revision -m "split test-family control_id into baseline/instance"` 로 빈 리비전을 만들고,
`upgrade()` / `downgrade()` 를 아래 규약으로 채운다(에디터로 작성, 단계 A 실측 반영):

upgrade() — 5개 테이블 각각:
- `add_column baseline_control_id` (uuid, nullable=True)
- `add_column instance_control_id` (uuid, nullable=True)
- FK: baseline_control_id → baseline_controls (A2 규약대로. 복합이면 (tenant_id, baseline_control_id)→(tenant_id, id))
- FK: instance_control_id → control_instances(id)
- CHECK `NOT (baseline_control_id IS NOT NULL AND instance_control_id IS NOT NULL)`
- 데이터 백필: `UPDATE <t> SET baseline_control_id = b.id FROM controls c JOIN baseline_controls b ON b.code=c.code AND b.tenant_id=<t>.tenant_id WHERE <t>.control_id = c.id;`
  (tenant 조인은 A1 에서 tenant_id 가 실재하는 테이블에만. 없으면 code 단독 조인 — A4 가 1:1 보장 시)
- 기존 `control_id` 를 `alter_column ... nullable=True` 로 완화(제거하지 않음)

downgrade() — 역순: CHECK/FK/새 컬럼 제거, control_id nullable 원복. (백필 데이터는 downgrade 시 소실되므로 주석 명기.)

### B2 — 로컬 적용
```
docker compose exec -T backend alembic upgrade head > E:\claudeprojects\ICFR\_probe\b2_upgrade.txt
```
에러면 원인 보고(자동 재시도·강행 금지).

## 단계 C — 검증 (읽기 전용)
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'cra_filled', count(*) FROM control_risk_assessments WHERE baseline_control_id IS NOT NULL UNION ALL SELECT 'cra_orphan', count(*) FROM control_risk_assessments WHERE control_id IS NOT NULL AND baseline_control_id IS NULL AND instance_control_id IS NULL UNION ALL SELECT 'assert_filled', count(*) FROM control_assertions WHERE baseline_control_id IS NOT NULL;" > E:\claudeprojects\ICFR\_probe\c1_verify.txt
```
기대: control_id 가 있던 실무 행은 baseline_control_id 채워짐, orphan(백필 실패) 0.
control_assertions 는 93 채워짐. deficiencies 의 NULL 2건은 두 컬럼 모두 NULL 유지.
downgrade 리허설도 1회 권장: `alembic downgrade -1` 후 재 `upgrade head` 로 왕복 검증.

## 산출 (보고 형식)
1. 단계 A: tenant_id 유무·control_id 타입 / baseline FK 복합 여부 / code 1:1 여부 / alembic head — 그리고 설계값과의 일치/불일치.
2. 단계 B: 생성한 리비전 파일 경로, upgrade 성공 여부, 백업 파일.
3. 단계 C: 백필 검증 수치(채워짐/orphan/NULL 유지), 왕복 검증 결과.
4. **운영 미적용·미push 명시** — 마스터 검토·push 대기.
5. 마이그레이션 파일·`_probe\*` 외 무수정 명시.
