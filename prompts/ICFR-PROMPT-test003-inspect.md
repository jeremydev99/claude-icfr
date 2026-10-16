# ICFR-PROMPT-test003-inspect

## 목적
고아 test_run `test-003`(id `019ece3b-7d67-72f1-bc70-980db54d65b6`)이
**실제 평가 흔적인지 개발용 더미인지** 사용자가 눈으로 판별할 수 있도록,
그 test_run 의 전체 내용(본체 행 + step 4건 + 상태/승인 이력)을 그대로 떠서 보여준다.
이번 프롬프트는 **읽기 전용 조사만** 한다. 삭제·수정·마이그레이션·시드·쓰기 절대 금지.

## 엄격 제약 (반드시 준수)
- 읽기 전용. DELETE/INSERT/UPDATE/ALTER/alembic 일절 금지.
- 조회는 컨테이너 안: `docker compose exec -T postgres psql -U icfr_user -d icfr_db ...`
- 잘림 방지: `-x`(확장 출력) 또는 `-A -t` 로 뽑아 **파일로 저장 후** 읽어 보고.
- PowerShell 5.1: `&&` 금지(`;`), `2>&1`·`$()`·heredoc 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- 컬럼명 추정 금지. 조사 0에서 실제 컬럼을 확인한 뒤 그 이름으로 뽑는다.
- 대상 id 고정: `019ece3b-7d67-72f1-bc70-980db54d65b6`.

## 준비
```
Set-Location E:\claudeprojects\ICFR
docker compose up -d
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 조사 0 — 컬럼 확인 (추정 금지)
test_runs / test_steps / test_status_history 의 실제 컬럼을 먼저 본다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('test_runs','test_steps','test_status_history') ORDER BY table_name, ordinal_position;" > E:\claudeprojects\ICFR\_probe\i0_cols.txt
```

## 조사 1 — test_run 본체 (전체 컬럼)
누가·언제 만들었는지, 상태, 제목/설명, 결론 등을 전부 본다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -x -c "SELECT * FROM test_runs WHERE id='019ece3b-7d67-72f1-bc70-980db54d65b6';" > E:\claudeprojects\ICFR\_probe\i1_run.txt
```

## 조사 2 — test_steps 4건 (전체 컬럼)
step 내용이 실제 절차인지, 빈 껍데기인지 본다.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -x -c "SELECT * FROM test_steps WHERE test_run_id='019ece3b-7d67-72f1-bc70-980db54d65b6' ORDER BY 1;" > E:\claudeprojects\ICFR\_probe\i2_steps.txt
```

## 조사 3 — 상태/승인 이력 (전체 컬럼)
전환 시각·행위자·상태값을 본다. 실제 승인 흐름을 탔는지 판별의 핵심.
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -x -c "SELECT * FROM test_status_history WHERE test_run_id='019ece3b-7d67-72f1-bc70-980db54d65b6' ORDER BY 1;" > E:\claudeprojects\ICFR\_probe\i3_history.txt
```

## 조사 4 — 행위자 이름 매핑 (이력에 user id 만 있을 때)
조사 1/3 에 나온 created_by / 행위자 컬럼이 user id(uuid)면, 누구인지 이름으로 바꿔 본다.
`<usercol>` 과 `<idlist>` 는 조사 0/1/3 의 실제 컬럼·값으로 치환(추정 금지).
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT id, email, full_name FROM users WHERE id IN (<idlist>);" > E:\claudeprojects\ICFR\_probe\i4_users.txt
```

## 산출 (보고 형식)
1. test_run 요약: 생성자(이름), 생성/수정 시각, 상태, 제목·설명, 결론값(있으면).
2. step 4건: 각 step 의 내용 요약 — 실제 절차 텍스트가 있는지 / 비어있는지.
3. 이력: 상태 전환 목록(시각 · 행위자 이름 · from→to). 승인 단계까지 갔는지 명시.
4. 판별 소견 한 줄(사실 기반만): "실제 평가를 돌린 흔적으로 보임 / 개발용 더미로 보임 /
   판단 불가 — 근거". **폐기 여부는 사용자 결정 사항이므로 결정하지 않는다.**
5. 파일·DB·ClaudeICFR.md 아무것도 수정하지 않았음을 명시.
