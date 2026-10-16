# ICFR-PROMPT-testfk-idmap

## 목적
Test 계열 FK를 baseline_controls / control_instances 두 컬럼으로 분리(선택지 2)하기 전,
**기존 Test 행의 control_id가 어느 정체성으로 매핑되는지**, 그리고 옛 `controls.id` →
새 정체성 id 로의 **신뢰할 수 있는 매핑 키가 있는지**를 확정한다.
이번 프롬프트도 **읽기 전용 조사만** 한다. 스키마 변경·마이그레이션·시드·쓰기 절대 금지.

## 엄격 제약 (반드시 준수)
- 읽기 전용. INSERT/UPDATE/DELETE/ALTER/alembic 일절 금지.
- 조회는 컨테이너 안: `docker compose exec -T postgres psql -U icfr_user -d icfr_db ...`
- 잘림 방지: `-A -t` 로 뽑아 **파일로 저장 후** 읽어 보고.
- PowerShell 5.1: `&&` 금지(`;`), `2>&1`·`$()`·heredoc 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 컬럼명은 **추정 금지**. 조사 2에서 실제 컬럼을 확인한 뒤 그 이름으로 조사 5/6을 짠다.
- 쓰기가 필요하다고 판단되면 실행하지 말고 멈춰서 보고.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```
(이전 `_probe\q4_cols.txt` 가 있으면 재사용 가능. 없으면 아래가 다시 만든다.)

## 조사 1 — id 데이터 타입 (분기 기준)
세 테이블 id 타입이 같아야 값 비교(조사 5)가 성립한다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT table_name, data_type FROM information_schema.columns WHERE table_schema='public' AND column_name='id' AND table_name IN ('controls','baseline_controls','control_instances') ORDER BY table_name;" > E:\claudeprojects\ICFR\_probe\r1_idtypes.txt
```

## 조사 2 — 링크/자연키 후보 컬럼
옛 controls 를 가리키거나 대응시킬 만한 컬럼(코드/source/legacy/origin 등)을 찾는다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('controls','baseline_controls','control_instances') AND (column_name LIKE '%code%' OR column_name LIKE '%control%' OR column_name LIKE '%source%' OR column_name LIKE '%legacy%' OR column_name LIKE '%origin%' OR column_name LIKE '%ref%') ORDER BY table_name, ordinal_position;" > E:\claudeprojects\ICFR\_probe\r2_linkcols.txt
```

## 조사 3 — baseline_controls / control_instances → controls FK 유무
정식 FK 링크가 있으면 그게 최우선 매핑 키다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name=ccu.constraint_name WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_name IN ('baseline_controls','control_instances') ORDER BY tc.table_name;" > E:\claudeprojects\ICFR\_probe\r3_fkfrom.txt
```

## 조사 4 — Test FK 테이블별 control_id 실제 값
대상: control_risk_assessments, test_runs, control_assertions, deficiencies, design_assessments.
각 테이블마다 distinct control_id 목록만 먼저 뽑는다(멤버십은 조사 5에서).
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT DISTINCT control_id FROM <테이블>;" > E:\claudeprojects\ICFR\_probe\r4_<테이블>.txt
```

## 조사 5 — 정체성 멤버십 (※ 조사 1에서 세 id 타입이 동일할 때만)
각 Test 테이블의 control_id가 baseline / instance 중 어디에 속하는지.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT t.control_id, EXISTS(SELECT 1 FROM baseline_controls b WHERE b.id=t.control_id) AS in_base, EXISTS(SELECT 1 FROM control_instances i WHERE i.id=t.control_id) AS in_inst FROM (SELECT DISTINCT control_id FROM <테이블>) t;" > E:\claudeprojects\ICFR\_probe\r5_<테이블>.txt
```
그리고 옛 controls.id 와 baseline_controls.id 전체 겹침 수:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT (SELECT count(*) FROM controls c JOIN baseline_controls b ON b.id=c.id) AS overlap, (SELECT count(*) FROM controls) AS controls_n, (SELECT count(*) FROM baseline_controls) AS base_n;" > E:\claudeprojects\ICFR\_probe\r5_overlap.txt
```
**id 타입이 서로 다르면** 조사 5는 성립하지 않는다 — 건너뛰고 조사 6(자연키)으로 간다.

## 조사 6 — 자연키 매핑 (조사 2에서 공유 코드 컬럼을 찾았을 때)
예: 양쪽에 `<codecol>` 이 있으면 옛 controls ↔ baseline_controls 대응 수를 센다.
`<codecol>` 은 **조사 2 결과의 실제 컬럼명으로 치환**한다(추정 금지).
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT count(*) AS matched, (SELECT count(*) FROM controls) AS controls_n FROM controls c JOIN baseline_controls b ON b.<codecol>=c.<codecol>;" > E:\claudeprojects\ICFR\_probe\r6_codematch.txt
```

## 조사 7 — resolver 재확인 (코드 읽기)
`backend/app/services/control_resolver.py:19-26` 을 읽어, 정체성 id 규칙(baseline→baseline_controls.id,
add→control_instances.id)이 조사 5 실측과 일치하는지 대조한다.

## 산출 (보고 형식)
1. 세 테이블 id 타입 (동일/상이) — 조사 5 성립 여부.
2. 매핑 키 결론 한 줄: 옛 `controls.id` → 새 정체성 id 를
   ㄱ) FK(조사 3), ㄴ) id 겹침(조사 5-overlap), ㄷ) 자연키 코드(조사 6) 중 **무엇으로** 이을 수 있는지.
   신뢰 가능한 키가 없으면 "없음 — 확인 필요"로 명시.
3. 기존 11건 매핑 표: 각 Test 테이블 control_id → in_base / in_inst / (해당 없으면) 미해결.
   전부 baseline 인지, instance 도 섞였는지, 어디에도 안 걸리는 고아가 있는지.
4. 위 결과로 선택지 2 마이그레이션이 **데이터 손실 없이 가능한지** 판정:
   가능 / 조건부(어떤 행이 문제) / 불가(무엇이 막는지).
5. 판단 못 할 지점은 "확인 필요"로 남긴다(추정 금지).
6. 파일·DB·ClaudeICFR.md 아무것도 수정하지 않았음을 명시.
