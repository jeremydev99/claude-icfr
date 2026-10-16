# ICFR-PROMPT-orphan-runs-delete

## 목적
**로컬** icfr_db 의 고아 test_run 3건(test-001/002/003)과 하위 행을 **물리 삭제**한다.
백업 + 단일 트랜잭션 + 카운트 어서션으로 안전하게 처리한다.
예상 삭제 = test_steps 4 · test_status_history 10 · test_runs 3 = **합계 17행**.

## 엄격 제약 (반드시 준수)
- 대상은 **로컬 icfr_db 뿐**. 운영 접속·운영 조작 절대 금지.
- 파괴적 작업. 순서 엄수: 단계0 트리거확인 → 단계1 백업 → 단계2 프리뷰 → **여기서 멈춰 보고** →
  사용자 승인 후에만 단계3 삭제. **승인 없이 단계3 실행 금지.**
- 백업 3파일이 없거나 예상 행수(3/4/10)와 다르면 **삭제로 넘어가지 말고 멈춘다.**
- 삭제는 단일 트랜잭션. 삭제 건수가 4/10/3 과 정확히 일치하지 않으면 예외로 **전체 롤백**.
- soft delete 아님 — 물리 DELETE. approved 잠금 레코드라도 DB 직접 삭제.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 이 프롬프트가 만드는 산출물은 `_probe\backup_*.csv` 3개와 `_probe\cleanup_orphans.sql` 뿐.
  그 외 파일·코드·ClaudeICFR.md 수정 금지.

## 대상 id (고정)
- test-001 : 019eca33-fa4f-7d50-83f2-483c5b294437
- test-002 : 019eca33-a692-7c31-8fb6-6aa038c12019
- test-003 : 019ece3b-7d67-72f1-bc70-980db54d65b6

## 준비
```
Set-Location E:\claudeprojects\ICFR
docker compose up -d
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 단계 0 — DELETE 트리거/규칙 확인 (있으면 멈춤)
세 테이블에 DELETE 를 가로채는 트리거나 rule 이 있으면 삭제가 튕길 수 있다. 있으면 **진행 말고 보고**.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT event_object_table, trigger_name, event_manipulation FROM information_schema.triggers WHERE event_object_table IN ('test_runs','test_steps','test_status_history') ORDER BY 1;" > E:\claudeprojects\ICFR\_probe\d0_triggers.txt
```
결과가 비어 있으면(트리거 없음) 계속. DELETE 관련 트리거가 있으면 멈추고 보고.

## 단계 1 — 백업 (CSV 3파일)
※ Out-File utf8 에 BOM 이 붙을 수 있음 — 복구 시 첫 컬럼에서 BOM 제거 필요(주석으로 남길 것).
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -c "COPY (SELECT * FROM test_runs WHERE id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6')) TO STDOUT WITH CSV HEADER" | Out-File E:\claudeprojects\ICFR\_probe\backup_test_runs.csv -Encoding utf8
```
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -c "COPY (SELECT * FROM test_steps WHERE test_run_id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6')) TO STDOUT WITH CSV HEADER" | Out-File E:\claudeprojects\ICFR\_probe\backup_test_steps.csv -Encoding utf8
```
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -c "COPY (SELECT * FROM test_status_history WHERE test_run_id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6')) TO STDOUT WITH CSV HEADER" | Out-File E:\claudeprojects\ICFR\_probe\backup_test_status_history.csv -Encoding utf8
```
백업 검증: 세 파일이 각각 헤더 + 데이터행(runs 3 / steps 4 / history 10)을 담고 있는지 행수로 확인.
하나라도 어긋나면 **멈추고 보고**, 단계2/3 진행 금지.

## 단계 2 — 삭제 프리뷰 (읽기 전용)
실제 삭제 없이 삭제될 건수를 센다. 4 / 10 / 3 이어야 한다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'steps', count(*) FROM test_steps WHERE test_run_id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6') UNION ALL SELECT 'history', count(*) FROM test_status_history WHERE test_run_id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6') UNION ALL SELECT 'runs', count(*) FROM test_runs WHERE id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6') UNION ALL SELECT 'def_ref', count(*) FROM deficiencies WHERE test_run_id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6');" > E:\claudeprojects\ICFR\_probe\d2_preview.txt
```
→ steps=4, history=10, runs=3, **def_ref=0** 확인.
**여기서 멈추고 보고한다.** 프리뷰 수치와 트리거 유무를 사용자에게 알리고, 승인 전까지 단계3 실행 금지.
(def_ref 이 0 이 아니면 미비점이 이 run 을 참조 중이므로 절대 진행 말고 보고.)

## 단계 3 — 삭제 실행 (※ 사용자 승인 후에만)
아래 내용 그대로 `E:\claudeprojects\ICFR\_probe\cleanup_orphans.sql` 파일로 저장(에디터로 작성, heredoc 금지):
```sql
-- cleanup_orphans.sql : 로컬 icfr_db 고아 test_run 3건 + 하위 물리 삭제
-- 단일 트랜잭션. 삭제 건수가 steps=4 / history=10 / runs=3 과 다르면 예외 → 전체 롤백.
-- 복구: _probe\backup_*.csv 를 COPY <table> FROM ... WITH CSV HEADER (BOM 있으면 제거 후)
BEGIN;
DO $$
DECLARE
  del_steps int; del_hist int; del_runs int;
  ids uuid[] := ARRAY[
    '019eca33-fa4f-7d50-83f2-483c5b294437',
    '019eca33-a692-7c31-8fb6-6aa038c12019',
    '019ece3b-7d67-72f1-bc70-980db54d65b6'
  ]::uuid[];
BEGIN
  DELETE FROM test_steps          WHERE test_run_id = ANY(ids);
  GET DIAGNOSTICS del_steps = ROW_COUNT;
  DELETE FROM test_status_history WHERE test_run_id = ANY(ids);
  GET DIAGNOSTICS del_hist = ROW_COUNT;
  DELETE FROM test_runs           WHERE id = ANY(ids);
  GET DIAGNOSTICS del_runs = ROW_COUNT;
  IF del_steps <> 4 OR del_hist <> 10 OR del_runs <> 3 THEN
    RAISE EXCEPTION 'ABORT count mismatch: steps=% hist=% runs=% (expected 4/10/3)',
      del_steps, del_hist, del_runs;
  END IF;
  RAISE NOTICE 'OK deleted steps=% hist=% runs=%', del_steps, del_hist, del_runs;
END $$;
COMMIT;
```
컨테이너로 복사 후 실행:
```
docker compose cp E:\claudeprojects\ICFR\_probe\cleanup_orphans.sql postgres:/tmp/cleanup_orphans.sql
```
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -f /tmp/cleanup_orphans.sql
```
출력의 `OK deleted ...` NOTICE 를 확인. `ABORT`/ERROR 가 뜨면 롤백된 것이므로 원인 보고.

## 단계 4 — 삭제 검증 (읽기)
세 run id 와 하위가 모두 사라졌고, deficiencies·다른 데이터는 그대로인지 확인.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'runs_left', count(*) FROM test_runs WHERE id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019','019ece3b-7d67-72f1-bc70-980db54d65b6') UNION ALL SELECT 'runs_total', count(*) FROM test_runs UNION ALL SELECT 'steps_total', count(*) FROM test_steps UNION ALL SELECT 'hist_total', count(*) FROM test_status_history UNION ALL SELECT 'def_total', count(*) FROM deficiencies;" > E:\claudeprojects\ICFR\_probe\d4_verify.txt
```
→ runs_left=0, runs_total 은 삭제 전보다 3 줄어든 값이어야 한다.

## 산출 (보고 형식)
1. 단계0: DELETE 트리거 유무.
2. 단계1: 백업 3파일 경로·행수 (3/4/10 일치 여부).
3. 단계2: 프리뷰 카운트(steps/history/runs/def_ref) → **여기서 보고하고 승인 대기**.
4. (승인·실행 후) 단계3: 실제 삭제 카운트, 어서션 통과(OK) 또는 롤백(ABORT) 여부.
5. 단계4: 검증 결과(runs_left=0, 총계 변화).
6. `_probe\backup_*.csv` 3개와 `cleanup_orphans.sql` 외 아무것도 수정하지 않았음을 명시.
