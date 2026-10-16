# ICFR-PROMPT-testfk-orphan-count

## 목적
고아 test_runs 3건(옛 code `test-001`, `test-002`, `test-003` 통제를 가리킴)을
정리 삭제하기 **전에**, 함께 지워질 하위 행(test_steps, test_status_history) 건수를 확정한다.
이번 프롬프트는 **읽기 전용 조사만** 한다. 삭제·스키마 변경·마이그레이션·시드·쓰기 절대 금지.

## 엄격 제약 (반드시 준수)
- 읽기 전용. DELETE/INSERT/UPDATE/ALTER/alembic 일절 금지.
- 조회는 컨테이너 안: `docker compose exec -T postgres psql -U icfr_user -d icfr_db ...`
- 잘림 방지: `-A -t` 로 뽑아 **파일로 저장 후** 읽어 보고.
- PowerShell 5.1: `&&` 금지(`;`), `2>&1`·`$()`·heredoc 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 대상 test_run id 는 **추정 금지**. 조사 1에서 실제 id 를 확정한 뒤 그 값으로 조사 2/3 을 짠다.
- 쓰기가 필요하다고 판단되면 실행하지 말고 멈춰서 보고.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 조사 1 — 대상 test_run 확정
옛 controls.code 가 test-001/002/003 인 통제를 가리키는 test_runs 행을 id 로 확정한다.
(Test FK 는 아직 옛 controls.id 를 가리키므로 controls 로 조인한다.)
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT tr.id, c.code FROM test_runs tr JOIN controls c ON c.id=tr.control_id WHERE c.code IN ('test-001','test-002','test-003') ORDER BY c.code;" > E:\claudeprojects\ICFR\_probe\o1_targets.txt
```
→ `o1_targets.txt` 의 id 목록이 조사 2/3 의 대상이다. 3건이 아니면 멈추고 보고.

## 조사 2 — test_steps 하위 건수
조사 1의 test_run id 들에 딸린 test_steps 수. `<ids>` 는 o1 의 실제 id 를 `'a','b','c'` 형태로 치환.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT run_id, count(*) FROM test_steps WHERE run_id IN (<ids>) GROUP BY run_id ORDER BY run_id;" > E:\claudeprojects\ICFR\_probe\o2_steps.txt
```
※ test_steps 의 test_run 참조 컬럼명이 `run_id` 가 아닐 수 있다. 확실치 않으면 먼저
`information_schema.columns` 로 test_steps 의 컬럼을 확인하고 실제 이름으로 치환한다(추정 금지).

## 조사 3 — test_status_history 하위 건수
같은 대상에 딸린 test_status_history 수. 참조 컬럼명도 조사 2와 동일하게 실제 확인 후 치환.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT run_id, count(*) FROM test_status_history WHERE run_id IN (<ids>) GROUP BY run_id ORDER BY run_id;" > E:\claudeprojects\ICFR\_probe\o3_history.txt
```

## 조사 4 — 그 밖의 참조 (안전 확인)
이 3개 test_run 을 참조하는 **다른** FK 가 있는지 확인해, 삭제 시 예상 못 한 연쇄가 없는지 본다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT tc.table_name, kcu.column_name, ccu.table_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name=ccu.constraint_name WHERE tc.constraint_type='FOREIGN KEY' AND ccu.table_name='test_runs' ORDER BY tc.table_name;" > E:\claudeprojects\ICFR\_probe\o4_refs.txt
```

## 산출 (보고 형식)
1. 대상 test_run 3건: id ↔ code 표.
2. 하위 건수 표: test_run id 별 test_steps 수 / test_status_history 수, 그리고 **총합**.
3. test_runs 를 참조하는 FK 테이블 목록(조사 4). test_steps/test_status_history 외에
   다른 참조가 있으면 삭제 범위에 포함됨을 명시.
4. "삭제 시 함께 사라지는 행: test_runs 3 + steps N + history M (+기타 K) = 합계" 한 줄 요약.
5. 판단 못 할 지점은 "확인 필요"로 남긴다(추정 금지).
6. 파일·DB·ClaudeICFR.md 아무것도 수정하지 않았음을 명시.
