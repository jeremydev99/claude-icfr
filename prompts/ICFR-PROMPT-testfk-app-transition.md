# ICFR-PROMPT-testfk-app-transition

## 목적
FK-less 마이그레이션으로 열린 **무결성 공백을 닫는다**: Test 생성 라우트가 resolver 로
control_id 를 검증·분해해 baseline_control_id / instance_control_id 두 컬럼을 채우게 한다.
이로써 원래 문제였던 **시드 409 도 해소**된다.
**로컬 한정** — 커밋·push 안 함(전환 완결 후 마이그레이션 리비전과 함께 커밋). 단계별 검증.

## 범위 (좁힘 — 확정)
- **대상 4개**: control_risk_assessments(RAWC), test_runs, deficiencies, design_assessments 의 **생성 라우트·모델**.
- **제외(별도 작업)**: control_assertions(레거시 Excel 업로드 경로 rcm.py:1497) — Test 라우트 밖이라 이번 미포함.
- **제외(별도 논의)**: `(control_id, fiscal_year)` 유니크 3곳(RAWC/TestRun/DesignAssessment) — 이번에 손대지 않음.
- kind 필터 추가는 **다음 프롬프트**(별도 커밋).

## 정독 확정 사실 (resolver-route-read 결과)
- resolver: `_resolve_assertion_target(db, control_id)` (실제 위치 api/rcm.py:980-999). 없는 id → **조용히 None**.
  반환 `tuple[UUID|None, UUID|None]`: baseline 유래=(control_id, None), add=(None, inst.id). 두 컬럼 채우기에 충분.
- 기존 관례: 모든 호출부가 `if target is None: raise HTTPException(404)`. **우리도 동일 패턴.**
- 라우트 4곳: `Model(**body.model_dump())` 그대로 저장, 검증 없음(test_module.py:92,157 / remediation.py:62,224). tenant_id 자동 주입.
- 스키마: control_id UUID 필수(Deficiency만 Optional), Update 스키마는 control_id 안 받음. 새 컬럼 응답 노출 불필요, **요청 바디는 control_id 유지·서버가 분해**.

## 엄격 제약 (반드시 준수)
- 로컬만. **커밋·push 안 함**(워킹트리 변경으로만). 단계별로 멈춰 검증.
- resolver 는 **공용 모듈로 추출**해 재사용(rcm.py 안에 둔 채 import 하면 순환 참조 위험 — 위치는 단계 1에서 판단, 추정 금지).
- 잘못된/없는 control_id → **404**(조용히 NULL 저장 금지). Deficiency 는 control_id Optional 이므로 **없으면 두 컬럼 NULL 허용**, 있으면 resolver·404 적용.
- DB 스키마 변경 금지(이미 fkless 적용됨). alembic 실행 금지.
- PowerShell 5.1: `&&`→`;`, heredoc·`2>&1`·`$()` 금지, `Set-Location`, 965B 이하.
- 실패·불확실하면 멈추고 보고. 한 번에 4곳 다 바꾸지 말고 순서대로.

## 준비 + 원격 확인
```
Set-Location E:\claudeprojects\ICFR
git fetch origin ; git log --oneline -2 origin/main ; docker compose up -d
```
origin 새 커밋 있으면(특히 test/assessment/alembic) 멈추고 보고.

## 단계 1 — resolver 공용화
`_resolve_assertion_target` 을 재사용 가능한 위치로 추출:
- 순환 참조 없는 서비스 모듈(예: services/control_resolver.py 또는 신규 services/test_target.py)로 이동/래핑.
- rcm.py:1038-1040 기존 호출부가 깨지지 않게(같은 함수 참조 유지). 함수 시그니처·반환 불변.
- import 경로 정리 후 `python -m py_compile` 통과.
**여기서 멈춰**: 추출 위치·기존 호출부 무영향을 보고.

## 단계 2 — 모델 4파일 새 컬럼 매핑
`models/test_module.py`(RAWC/test_runs/…), `models/remediation.py`(deficiencies 등) 에서
대상 4모델에 `baseline_control_id`, `instance_control_id` 컬럼 매핑 추가(FK 없이 Column(UUID)).
- legacy `control_id` 는 **유지 + deprecated 주석**(제거는 나중).
- relationship 은 당장 불필요하면 생략(과설계 금지).
- `py_compile` + 앱 기동(`docker compose up -d backend`) healthy 확인.
**멈춰 보고**: 모델 매핑만 반영, 동작 무변경 확인.

## 단계 3 — 라우트 4곳 전환 (공백 닫기 핵심)
각 생성 엔드포인트를 `Model(**body.model_dump())` 대신:
1. body.control_id 로 resolver 호출 → `(base, inst)`.
2. RAWC/test_runs/design_assessments: `if base is None and inst is None: raise HTTPException(404)`.
   deficiencies: control_id 있으면 동일 검증, 없으면 두 컬럼 NULL 로 통과.
3. 저장 시 `control_id` 는 그대로 두되 `baseline_control_id`/`instance_control_id` 를 resolver 결과로 채움.
- 한 라우트씩 고치고 `py_compile`·기동 확인 후 다음.
**멈춰 보고**: 4곳 변경 요지, 404 경로 추가 확인.

## 단계 4 — API 왕복 검증 (공백 닫힘 확인)
로컬에서 실제 호출로 확인(시드 계정/토큰 사용, dev 환경):
- 정상 control_id 로 각 대상 1건 생성 → 응답 200, DB 에서 그 행의 baseline/instance 채워졌는지 psql 로 확인.
- **잘못된 uuid 로 생성 시도 → 404** 나는지(조용히 NULL 저장 안 됨) 확인.
결과를 `_probe\tr_roundtrip.txt` 로.

## 단계 5 — 시드 409 해소 확인 (성공 지표)
```
docker compose exec -T backend python -m app.seeds.run_all > E:\claudeprojects\ICFR\_probe\tr_seed.txt
```
- **[3/5] test runs 가 409 없이 통과**하고 [4/5][5/5]까지 완주하는지 확인. 이게 원래 문제의 실제 해소.
- 실패면 어느 단계·어떤 오류인지 보고(강행 금지).

## 산출 (보고 형식)
1. 원격 확인 결과.
2. 단계 1: resolver 추출 위치, 기존 호출부(rcm.py:1038) 무영향 확인.
3. 단계 2: 모델 4곳 컬럼 매핑, 기동 healthy.
4. 단계 3: 라우트 4곳 변경 요지, 404 경로.
5. 단계 4: API 왕복 — 정상 생성 시 두 컬럼 채워짐 / 잘못된 id 404. 실제 값 인용.
6. 단계 5: **시드 5/5 완주(409 해소) 여부** — 성공/실패.
7. **로컬 한정·커밋 안 함·push 안 함** 명시. 제외 항목(control_assertions, 유니크 3곳) 재확인.
8. 다음: kind 필터(별도 커밋) → 전체 커밋 정리 → push 전 협업자 조율.
