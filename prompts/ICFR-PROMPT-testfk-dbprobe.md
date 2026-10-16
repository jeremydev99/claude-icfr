# ICFR-PROMPT-testfk-dbprobe

## 목적
Test 모듈 FK를 control_instances/baseline_controls로 옮기는 방향(선택지 A)의
정확한 모양을 잡기 위한 **읽기 전용 DB/코드 확인**.
이번 프롬프트는 조사만 한다. 스키마 변경·마이그레이션·시드·쓰기는 절대 하지 않는다.

## 엄격 제약 (반드시 준수)
- 읽기 전용. INSERT/UPDATE/DELETE/ALTER/alembic 일절 금지.
- 조회는 컨테이너 안에서: `docker compose exec -T postgres psql -U icfr_user -d icfr_db ...`
- psql 출력 잘림 방지: `-A -t` 로 뽑아 **파일로 저장한 뒤** 그 파일을 읽어 보고한다.
- PowerShell 5.1: `&&` 금지(`;` 사용), `2>&1`·`$()`·heredoc 금지, `cd` 대신 `Set-Location`.
- 단일 명령 965바이트 이하.
- 무언가 쓰기가 필요하다고 판단되면 **실행하지 말고 멈춰서 보고**한다.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 조사 1 — control 계열 테이블 존재 여부
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'controls', to_regclass('public.controls') IS NOT NULL UNION ALL SELECT 'control_instances', to_regclass('public.control_instances') IS NOT NULL UNION ALL SELECT 'baseline_controls', to_regclass('public.baseline_controls') IS NOT NULL;" > E:\claudeprojects\ICFR\_probe\q1_exists.txt
```

## 조사 2 — 존재하는 테이블 행수
조사1에서 exists=t 인 테이블만 대상으로, 각각:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT '<테이블>', count(*) FROM <테이블>;" > E:\claudeprojects\ICFR\_probe\q2_<테이블>.txt
```

## 조사 3 — FK 실태 (핵심)
Test 계열 테이블의 FK와, control 계열을 가리키는 모든 FK를 한 번에.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name, tc.constraint_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name=ccu.constraint_name WHERE tc.constraint_type='FOREIGN KEY' AND (ccu.table_name IN ('controls','control_instances','baseline_controls') OR tc.table_name LIKE 'test%' OR tc.table_name='control_risk_assessments') ORDER BY tc.table_name;" > E:\claudeprojects\ICFR\_probe\q3_fk.txt
```

## 조사 4 — control 계열 컬럼 구조 (PK·주요 컬럼)
FK를 어디로 옮길지 판단용.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('controls','control_instances','baseline_controls') ORDER BY table_name, ordinal_position;" > E:\claudeprojects\ICFR\_probe\q4_cols.txt
```

## 조사 5 — Test 계열 테이블 행수 (A 위험 확인)
`test%` 및 `control_risk_assessments` 각 테이블 count(*). 비어 있으면 마이그레이션 데이터 위험 0.
(조사3 결과에 나온 Test 계열 테이블 목록을 대상으로 각각 실행 → `_probe\q5_<테이블>.txt`)

## 조사 6 — 코드 확인 (읽기)
- `backend/app/models/test_module.py` 의 16, 54번째 줄 근처 FK 정의 확인 — 실제로 `controls.id`를 가리키는지.
- RCM 통제 저장 경로(`/api/rcm/controls` 라우트/모델)가 `control_instances`에 쓰는지 확인.

## 산출 (보고 형식)
1. `_probe\*.txt` 를 읽어 아래 표로 정리:
   - control 계열 3개 테이블: 존재/행수
   - Test 계열 FK: (테이블.컬럼 → 참조테이블.컬럼) 목록, 특히 control_risk_assessments의 control_id가 지금 가리키는 곳
   - control_instances / baseline_controls 의 PK 컬럼명
   - Test 계열 테이블 행수 (전부 0인지)
2. 위 사실만으로 **FK 이전 대상**을 한 줄로 결론: control_risk_assessments.control_id →
   `control_instances.id` 인지 `baseline_controls.id` 인지 (근거 함께).
3. 판단 못 할 지점이 있으면 "확인 필요"로 남긴다(추정 금지).
4. 파일·DB·ClaudeICFR.md 아무것도 수정하지 않았음을 명시.
