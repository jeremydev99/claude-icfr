# ICFR-PROMPT-resolver-route-read

## 목적
무결성 공백을 닫는 전환(모델→resolver→라우트) **전에**, resolver 의 정확한
시그니처·반환·에러 처리와 Test 생성 라우트 4개의 실제 경로를 **정독**한다.
"재사용 가능"까지만 본 census 를 넘어, 실제 동작을 확인해 추정 없이 수정 범위를 확정한다.
**읽기 전용** — 코드·DB·git 변경 금지. 만드는 것은 `_probe\rr_*.txt` 뿐.

## 핵심 질문 (이 프롬프트가 답할 것)
1. resolver 가 **잘못된/없는 control_id** 를 받으면 어떻게 되나 — None 반환? 예외? 빈 결과?
   (조용히 None 이면, 그대로 쓰면 baseline/instance 가 빈 채 저장되는 새 구멍이 생김.)
2. resolver 반환이 baseline vs instance 를 **어떻게 구분**해 주나 — 두 컬럼 중 어디를 채울지 판정 가능한가.
3. Test 생성 라우트 4개가 지금 control_id 를 **어디서 받아 어떻게 저장**하나(`Model(**body.model_dump())` 패턴 실제).
4. body 스키마가 control_id 를 필수로 받나, 그리고 새 컬럼을 노출할지 말지.

## 엄격 제약
- 읽기 전용. 편집·alembic·DB 쓰기·git 변경 금지.
- 결과는 파일로 저장 후 읽어 보고. PowerShell 5.1: `&&`→`;`, `2>&1`·`$()` 금지, `Set-Location`, 965B 이하.
- `_probe\` 외 산출물 금지.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 단계 1 — resolver 전문 정독
`backend\app\services\control_resolver.py` 전체를 읽는다. 특히:
- `_resolve_assertion_target(db, control_id)`(및 `resolve_controls`) 의 **시그니처·반환 타입**.
- 입력이 baseline_controls.id 인지 control_instances.id 인지 **판정하는 로직**과, 반환이 그 구분을 담는지.
- **없는 id / 다른 tenant id** 를 받을 때 경로: 예외 raise 인지 None/빈값인지. 관련 라인 인용.
정독 요약을 `_probe\rr1_resolver.txt` 로.

## 단계 2 — resolver 호출처 (기존 사용 관례)
```
Select-String -Path backend\* -Include *.py -Recurse -Pattern "_resolve_assertion_target|resolve_controls" | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" } > E:\claudeprojects\ICFR\_probe\rr2_callers.txt
```
- evidence/assessment 등 기존 호출부가 **어떻게 검증·사용**하는지(예외 처리 관례) 확인 — 우리 전환도 같은 관례를 따르기 위함.

## 단계 3 — Test 생성 라우트 4개 정독
`backend\app\api\test_module.py` 와 `backend\app\api\remediation.py` 에서
control_risk_assessments / test_runs / control_assertions / deficiencies / design_assessments 생성 엔드포인트를 읽는다:
- control_id 를 body 어디서 받는지, `Model(**body.model_dump())` 로 그대로 저장하는지.
- tenant_id 를 어디서 채우는지(현재 행의 tenant 출처).
- 생성 전 검증이 있는지(없으면 여기가 공백 닫을 지점).
요약을 `_probe\rr3_routes.txt` 로(엔드포인트·라인·저장 방식).

## 단계 4 — body 스키마 정독
해당 pydantic 스키마(schemas/test_module.py, remediation.py 등)에서 control_id 필드 정의,
새 컬럼 노출 여부 판단 근거 확인. `_probe\rr4_schemas.txt` 로.

## 산출 (보고 형식)
1. **핵심 질문 1**: resolver 가 잘못된 id 에 하는 것(예외/None/빈값) — 라인 인용. 그대로 쓰면 생길 위험.
2. **핵심 질문 2**: baseline vs instance 구분을 resolver 가 주는지, 두 컬럼 채우기에 충분한지.
3. **핵심 질문 3**: 라우트 4개의 현재 control_id 저장 방식·tenant 출처·기존 검증 유무.
4. **핵심 질문 4**: body 스키마의 control_id 필드, 새 컬럼 노출 권고(노출/내부처리).
5. 기존 호출부(evidence/assessment)의 예외 처리 관례 — 우리가 따라야 할 형태.
6. 이 사실들로 본 **전환 상세안**: 모델 4파일 무엇을 / resolver 를 공용화할지 그대로 쓸지 / 라우트 4곳 어디에 검증을 넣을지 / 시드 손볼 게 있는지. (실제 수정은 다음 프롬프트.)
7. 코드·DB·git 무변경 명시.
