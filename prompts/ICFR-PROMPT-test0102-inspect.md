# ICFR-PROMPT-test0102-inspect

## 목적
고아 test_run 2건 — `test-001`(id `019eca33-fa4f-7d50-83f2-483c5b294437`),
`test-002`(id `019eca33-a692-7c31-8fb6-6aa038c12019`) — 이 test-003 과 같은
**개발용 더미인지** 눈으로 확정한다. 확정되면 세 건을 묶어 삭제로 넘어간다.
이번 프롬프트는 **읽기 전용 조사만** 한다. 삭제·수정·마이그레이션·시드·쓰기 절대 금지.

## 엄격 제약 (반드시 준수)
- 읽기 전용. DELETE/INSERT/UPDATE/ALTER/alembic 일절 금지.
- 조회는 컨테이너 안: `docker compose exec -T postgres psql -U icfr_user -d icfr_db ...`
- 잘림 방지: `-x`(확장 출력)로 뽑아 **파일로 저장 후** 읽어 보고.
- PowerShell 5.1: `&&` 금지(`;`), `2>&1`·`$()`·heredoc 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 컬럼명은 이전 `_probe\i0_cols.txt` 재사용(없으면 test003-inspect 조사 0 재실행). 추정 금지.
- 대상 id 2개 고정. soft delete 된 step 도 포함해 전부 본다.

## 준비
```
Set-Location E:\claudeprojects\ICFR
docker compose up -d
```

## 조사 1 — test_run 본체 2건 (전체 컬럼)
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -x -c "SELECT * FROM test_runs WHERE id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019') ORDER BY id;" > E:\claudeprojects\ICFR\_probe\j1_runs.txt
```

## 조사 2 — test_steps (삭제 표시 포함 전부)
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -x -c "SELECT * FROM test_steps WHERE test_run_id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019') ORDER BY test_run_id;" > E:\claudeprojects\ICFR\_probe\j2_steps.txt
```

## 조사 3 — 상태/승인 이력
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -x -c "SELECT * FROM test_status_history WHERE test_run_id IN ('019eca33-fa4f-7d50-83f2-483c5b294437','019eca33-a692-7c31-8fb6-6aa038c12019') ORDER BY test_run_id;" > E:\claudeprojects\ICFR\_probe\j3_history.txt
```

## 산출 (보고 형식)
run 2건 각각:
1. 요약: 생성자·생성/수정 시각·상태·결과, 절차/모집단/담당자/비고가 비었는지, 승인까지 갔는지.
2. step 내용: 실제 감사 절차 텍스트인지 / 테스트 입력(예: "apple", 자모 분리, "재수정")인지.
3. 판별 한 줄(사실 기반): "test-003 과 동일한 개발용 더미로 보임 / 다름 — 근거".
   **폐기 여부는 사용자 결정이므로 결정하지 않는다.**
4. 셋(001·002·003)을 묶어 삭제할 때 함께 사라지는 하위 행(삭제 표시 포함) 총 재확인.
5. 파일·DB·ClaudeICFR.md 아무것도 수정하지 않았음을 명시.
