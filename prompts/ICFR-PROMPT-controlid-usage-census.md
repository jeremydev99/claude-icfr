# ICFR-PROMPT-controlid-usage-census

## 목적
두 가지를 **읽기 전용**으로 조사한다.
(A) Test 계열 앱 코드를 새 컬럼(baseline_control_id / instance_control_id)로 전환하기 위한
    `control_id`(및 옛 `controls`) 사용처 전수 조사 — 특히 Test 모듈 **밖** 참조.
(B) 협업자 5-2(평가 회차 kind 에 EUC 추가) 대비 — 회차 목록 조회의 **kind 필터 여부**와
    **kind 하드코딩 분기** 위치. 이 결과로 협업자 질문 ①②에 정확히 답한다.
**읽기 전용** — 코드·DB·git 변경 금지. 만드는 것은 `_probe\cu_*.txt` 뿐.

## 배경
- 스키마 마이그레이션(6b6d7fd94f0d) 적용 완료: Test 5테이블에 새 두 컬럼 존재·백필됨.
- 앱 코드(모델/시드/라우트/스키마/서비스)는 아직 옛 `control_id` 기준 → 시드 409 미해소.
- 협업자가 평가 회차 kind 에 EUC 추가 예정. 현재 design/operation 2종 → 3종. Test 가 같은 회차 사용.
  질문 ① 회차를 kind 로 거르나 전부 가져오나 ② `if kind==='design' … else` 하드코딩 분기가 있나.

## 엄격 제약 (반드시 준수)
- 읽기 전용. 파일 편집·`alembic`·DB 쓰기·git 변경 금지.
- 결과는 파일로 저장 후 읽어 보고(터미널 잘림 방지).
- 정적 코드 검색 위주(컨테이너 불필요). psql 필요 시 컨테이너 안에서 읽기만.
- PowerShell 5.1: `&&` 금지(`;`), `2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.
- `_probe\` 외 산출물 생성 금지.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

# ── A파트: control_id 전환 조사 ──

## A1 — control_id 전수 검색 (backend)
```
Select-String -Path backend\* -Include *.py -Recurse -Pattern "control_id" | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" } > E:\claudeprojects\ICFR\_probe\cu1_control_id.txt
```
히트를 분류: 모델 / 시드 / 라우트 / 스키마(pydantic) / 서비스·쿼리 / 테스트코드.

## A2 — 옛 controls 테이블·모델 참조
```
Select-String -Path backend\* -Include *.py -Recurse -Pattern "ForeignKey\(.controls\.|\bcontrols\b" | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" } > E:\claudeprojects\ICFR\_probe\cu2_controls_ref.txt
```

## A3 — Test 5모델 현재 컬럼 상태 (파일 읽기)
`backend\app\models\test_module.py` 등에서 control_id / baseline_control_id / instance_control_id
컬럼·relationship 정의 유무 확인(새 두 컬럼이 모델에 있는지 없는지).

## A4 — 시드의 control_id 사용 (409 지점)
```
Select-String -Path backend\app\seeds\* -Include *.py -Recurse -Pattern "control_id|rawc|RiskAssessment|assertion|test.*run" | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" } > E:\claudeprojects\ICFR\_probe\cu4_seed.txt
```
어느 시드가 어떤 id(옛 controls.id vs 정체성 id)를 넣어 FK 위반이 나는지 특정.

## A5 — Test 모듈 밖 참조 (회귀 위험)
control_id 히트 중 Test 5테이블과 무관한 파일(대시보드/analytics, RCM, resolver, 리포트)을 가려
`_probe\cu5_outside.txt` 로 "파일·라인·Test밖 여부·무엇을 읽음" 정리.

## A6 — resolver 확인 (읽기)
`backend\app\services\control_resolver.py` 를 읽어 정체성 id 규칙과 Test 전환 재사용 가능성 기록.

# ── B파트: 평가 회차 kind 조사 (협업자 5-2 답변용) ──

## B1 — kind 값 정의처
```
Select-String -Path backend\*,frontend\src\* -Include *.py,*.ts,*.tsx -Recurse -Pattern "kind|run_kind|assessment_type" | Select-String -Pattern "design|operation" | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" } > E:\claudeprojects\ICFR\_probe\cu_b1_kind_def.txt
```
kind enum/상수/리터럴이 정의된 곳(백엔드 모델·스키마, 프론트 타입·상수) 특정.

## B2 — 회차 목록 조회의 kind 필터 여부 (질문 ①)
회차(test_run/평가회차) 목록을 가져오는 라우트·서비스·프론트 API 호출에서
**kind 로 WHERE/filter 를 거는지, 무필터로 전부 가져오는지** 확인.
```
Select-String -Path backend\*,frontend\src\* -Include *.py,*.ts,*.tsx -Recurse -Pattern "test_run|test-run|list.*run|evaluation.*run" | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" } > E:\claudeprojects\ICFR\_probe\cu_b2_runlist.txt
```
- 백엔드 목록 쿼리에 `kind ==` / `.filter(kind=...)` 가 있는지.
- 프론트 목록 fetch 에 kind 파라미터가 붙는지.
- **결론: kind 필터 있음(EUC 안 섞임) / 무필터(EUC 섞여 나옴).**

## B3 — kind 하드코딩 분기 (질문 ②)
```
Select-String -Path backend\*,frontend\src\* -Include *.py,*.ts,*.tsx -Recurse -Pattern "kind ===|kind ==|kind !=|'design'|'operation'" | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" } > E:\claudeprojects\ICFR\_probe\cu_b3_kindbranch.txt
```
각 분기에서 **else 가 EUC 를 어떻게 취급할지** 판정: else→operation 취급이면 EUC 회차가 운영평가로 샘.
분기 목록(파일·라인)과 각 else 처리 결과 정리.

## 산출 (보고 형식)
### A파트
1. control_id 히트 분류표(모델/시드/라우트/스키마/서비스/테스트 건수·대표 위치).
2. Test 5모델의 새 두 컬럼 유무·relationship.
3. 시드 409 지점 한 줄 결론.
4. **Test 밖 참조 목록**(대시보드·RCM 등) — 전환 회귀 위험 지점.
5. resolver 재사용 가능 여부.
6. 전환 범위·순서 제안 초안(모델/시드/라우트/스키마 몇 파일).
### B파트 (협업자 답변 근거)
7. **질문 ① 답**: 회차 목록이 kind 필터를 거는가? (백엔드/프론트 각각) — EUC 섞임 여부 결론.
8. **질문 ② 답**: kind 하드코딩 분기 목록과 각 else 의 EUC 취급 — 운영평가로 샐 지점 유무.
9. kind 값 정의처(EUC 추가 시 손봐야 할 상수/enum 위치).
### 공통
10. 코드·DB·git 무변경, `_probe\cu*` 만 생성 명시.
