# 통제 4건 사전 조사 (읽기 전용)

- 조사일: 2026-10-16 (Regina 세션) · 기준 커밋 `b287978` · 프롬프트 `prompts/PROMPT_control4_investigate.md`
- 코드·DB·설정 변경 0건. 산출물은 이 문서 1개다.

## 0. 조사 환경 — DB 기준

| DB | alembic | 용도 |
|---|---|---|
| 로컬 `icfr-postgres` | `e3a5c7b9d1f4` — **head 보다 4개 뒤**(`f4b6…`·`a7c9…`·`b8d0…`·`c3e5…` 미적용) | 참고만. `assessment_activities.status`·`activity_samples` 등이 아직 없다 |
| 운영 `icfr-prod` | `c3e5a7b9d1f2` = head | **스키마·데이터 판단 기준**(SELECT 와 읽기 전용 resolver 계산만, §8.4 조회 위임) |

- **로컬 DB 와 migration 이 맞지 않는다.** 로컬에서 구현·테스트하기 전에 `alembic upgrade head` 가 필요하다. DDL 이라 이번 조사에서는 실행하지 않았다.
- 운영 데이터 규모: 통제 93 · 회차 1(대상 91) · 평가 기록 1(draft) · 승인 0 · 증빙 0 · 사용자 8.

---

## 1. 승인할 통제 건수 (자기승인 제외 · 직무분리 경고)

### 현황
- 프론트
  - `frontend/src/features/my-assessment/myAssessment.pure.ts:104-108` `matchesRole('approve')` 는 `my_roles` 에 `assessor`·`dept_approver` 가 있으면 참이다. **상태(state)를 보지 않는다.**
  - `frontend/src/features/my-assessment/pages/MyAssessmentPage.tsx:60-66` 버튼의 "승인할 통제 N" 은 위 함수로 센 값이다. 미착수·작성 중·승인 완료 건이 모두 들어간다.
- API
  - `backend/app/api/assessment.py:858-944` `GET /cycles/{id}/worklist` 는 `my_roles`(933행)와 함께 `pending_stages`·`can_approve` 를 준다. `can_approve` 는 "제출됨 + 남은 단계 + 내가 그 단계 역할 + 회차 진행 중"이다. **프론트 건수는 이 값을 쓰지 않는다.**
  - `backend/app/api/assessment.py:422-488` `POST /activities/{id}/approvals` 는 현재 역할 보유자인지(463행)와 제출 상태(467행)만 확인한다. **`activity.performed_by_id == user.id` 를 막는 검사가 없다** → 서버에서 자기승인을 차단하지 않는다.
  - SoD 판정 함수: `backend/app/services/role_resolver.py:163` `detect_conflicts`. 조합은 `CONFLICT_PAIRS=(control_owner, assessor)`, `CROSS_LAYER=(assessor, icfr_manager)`(`models/role_assignment.py:125,169`). **역할을 배정할 때만** 쓰이고(`api/role_assignment.py:159`) 승인 시점에는 쓰이지 않는다.
- DB (운영 실조회)
  - `assessment_activities`: `performed_by_id`(작성자)·`status`(draft/submitted)·`submitted_at` 있음. 분포: `draft/test 1건`.
  - `activity_approvals`: `stage`·`approved_by_id`·`approved_at`·`note`, 유니크 `(tenant_id, activity_id, stage)`. 0건.
  - `role_assignments`(통제 단위 역할): control/control_owner 93(6명), control/assessor 16(1명), process/assessor 8(1명).
  - resolver 로 계산한 통제 93건: owner 93 · assessor 93(process 유래 77 + control 16) · dept_approver 89(**전부 `derived`**, 부서장 유도)
    - **owner == assessor: 0건**
    - **owner == dept_approver(부서승인 단계 없음): 16건**
  - `tenant_policies`: `conflict_assessor_control_owner_blocked=true`, `dept_approval_enabled=true`
  - `conflict_acknowledgements`: 16건, 전부 `assessor=icfr_manager`(사유를 적고 허용한 겸직)
  - 감사로그: `audit_logs` 가 미들웨어로 모든 POST 를 기록한다. `POST …/approvals` 는 "평가 수행 승인"으로 매핑돼 있다(`services/audit_routes.py:167`). 승인 이력 자체는 `activity_approvals` 에 남는다.

### 영향 범위 / 리스크
- **자기 작성 건이 건수에 들어간다(실재 16건).** owner == 유도 dept_approver 인 통제에서는 `my_roles=[control_owner, dept_approver]` 가 되어 그 통제책임자에게 "작성할"과 "승인할" 양쪽에 같은 통제가 뜬다. 실제로는 부서승인 단계가 스킵되므로 승인할 것이 없다.
- **건수의 의미가 틀렸다.** "승인할 통제"가 승인 대기 건수가 아니라 역할을 가진 통제 수다. 승인할 것이 0건이어도 숫자가 크게 나온다.
- **서버측 자기승인 차단이 없다.** 지금은 배정 정책(`…_blocked=true`) 덕분에 owner==assessor 가 0건이라 실제로 터지지는 않는다. 하지만 ① 제출 후 역할 배정이 바뀌어 작성자가 평가자가 된 경우 ② 정책 토글을 끈 회사에서는 작성자가 자기 기록을 승인할 수 있다. 판매 수준 기준(서버측 SoD 강제)에 못 미친다.

### 추천안 (1개)
- 변경 계층: 프론트 + API. **DB migration 없음**
- 핵심 로직
  1. **API(승인 차단)**: `approve_activity` 에서 역할 확인 다음에 `activity.performed_by_id == user.id` 이면 403("본인이 작성한 테스트는 승인할 수 없습니다")을 낸다. 같은 기록의 다른 단계 승인자와 같은 사람인지도 막는다(부서승인자 == 평가자 승인자 방지).
  2. **API(목록)**: worklist 의 `can_approve` 계산에 같은 조건(`a.performed_by_id != user.id`)을 넣는다. 화면 판정과 서버 판정을 하나로 맞춘다.
  3. **프론트(건수)**: "승인할 통제" = `can_approve.length > 0` 인 행(=지금 내가 승인할 수 있는 제출 건)으로 바꾼다. 역할 기준 목록은 "전체"에서 그대로 본다. owner==dept 스킵 통제는 `pending_stages` 에 dept 가 없으므로 자연히 빠진다.
  4. **SoD 경고**: 화면에서 작성자 == 승인 역할 보유자인 행(드물다)에 "직무분리: 본인 작성 건 — 다른 승인자 필요" 배지를 붙인다. 판정은 서버 `WorklistRow` 에 `sod_blocked: bool` 로 내려준다.
- 폴백: 없음(차단 조건이 좁고 현재 데이터 영향 0건).

### 확인 필요(사용자 판단)
- 자기승인 시 **승인 대체 경로**: 막기만 할지, 아니면 상위자(`icfr_lead`/`icfr_manager`)가 대신 승인하는 경로를 열지. 추천은 **막기만**이다. 겸직은 역할 배정에서 해소하는 것이 현행 원칙(ADR-0031 §2.4)과 맞다. **운영 결정 → 마스터.**
- "승인할 통제" 버튼을 **승인 대기만** 셀지(추천), 역할 기준 전체를 셀지.

---

## 2. 증빙 Ctrl+V 붙여넣기

### 현황
- 프론트
  - 실제 사용처: `frontend/src/features/my-assessment/components/ActivitySheet.tsx:254-261` 샘플 줄마다 숨긴 `<input type="file">` + "증빙" 버튼이 있다. **드래그앤드롭 없음, 라이브러리 없음(네이티브)**, 클라이언트 검증 없음.
  - 증빙 관리 화면: `frontend/src/features/evidence/components/EvidenceUploadDialog.tsx:177` 파일 선택(`accept=ALLOWED_EXTENSIONS`) + `evidence.pure.ts:7-18` `validateFile`(50MB, MIME **또는** 확장자).
  - 프로젝트 전체에 `onPaste` 처리가 없다(clipboard 는 복사 쓰기 3곳뿐).
  - 업로드 호출: `frontend/src/features/my-assessment/api.ts:84-93` `POST /api/evidence/files`(multipart: cycle_id·control_id·sample_id·file).
- API `backend/app/api/evidence.py:229-290` `create_file`
  - multipart. 권한 `_assert_can_edit_evidence`(회차 진행 중 + 그 통제의 통제책임자, 또는 icfr_manager) + `sample_id` 가 있으면 `_assert_sample_linkable`(작성 중 기록의 작성자 본인).
  - 용량: 정책 `evidence_max_bytes`(운영 미설정) → 기본 50MB(`config.py:57`). nginx `client_max_body_size 51m`.
  - 형식: **클라이언트가 보낸 `content_type` 만 검사**(264-266행, `ALLOWED_MIME` 7종: pdf·png·jpeg·xlsx·docx·hwp 2종). 매직바이트 검사 없음.
  - 저장: MinIO, 키는 `build_evidence_key(cycle_id, control_id, file.id)`. 원본 파일명은 키에 쓰지 않고 `filename` 컬럼에만 둔다. sha256 저장(중복 판정 없음).
- DB (운영 실조회) `evidence_files`
  - `filename varchar(255) NOT NULL` · `mime_type varchar(100) NOT NULL` · `size_bytes` · `sha256` · `minio_key` · `uploaded_by_id NOT NULL` · `created_at` · `cycle_id`/`control_id`(nullable, 핸들러가 필수 처리) · `title` · `note` · 삭제 메타(`deleted_by_id`·`deleted_at_ts`·`delete_reason`)
  - `evidence_links`: `file_id`·`linked_entity_type`·`linked_entity_id` (샘플 연결 = `sample`)
  - 운영 0건, 로컬 5건(pdf, 4건은 회차 없는 레거시)

### 클립보드 이미지가 기존 경로를 통과하는가
| 지점 | 판정 |
|---|---|
| 파일명 필수(`filename NOT NULL`) | 통과. 브라우저가 클립보드 이미지에 `image.png` 이름을 붙인다. 다만 **모든 붙여넣기가 같은 이름**이 되어 식별이 안 된다 |
| MIME | `image/png` 는 허용 목록에 있다 → 통과 |
| 확장자 검증 | 서버에 없음. 프론트 `validateFile` 은 MIME 또는 확장자라 통과 |
| 탐색기에서 파일 복사 → 붙여넣기 | `clipboardData.files` 에 실제 파일명·MIME 이 담긴다 → 버튼 업로드와 같다 |
| **막히는 지점** | 없음. **API·DB 변경이 필요 없다** |

### 영향 범위 / 리스크
- 붙여넣기 범위가 넓으면(시트 전체) 어느 샘플에 붙을지가 모호하다. 샘플 식별 `<Input>` 에 텍스트를 붙여넣는 동작과도 충돌한다.
- 같은 캡처를 두 번 붙여넣으면 중복 증빙이 생긴다(sha256 은 있으나 판정 없음).
- (판매 수준 지적, 이번 범위 밖) MIME 을 클라이언트 신고값으로만 판정한다. 매직바이트 검증이 없다.

### 추천안 (1개)
- 변경 계층: **프론트만**. API·DB 변경 없음
- 핵심 로직
  1. `SampleRow` 를 붙여넣기 대상으로 만든다. 줄에 `tabIndex=0` + 포커스 테두리를 주고 "클릭 후 Ctrl+V" 안내를 붙인다. `onPaste` 는 그 줄에만 건다.
  2. `onPaste` 에서 `e.clipboardData.files` 가 비어 있으면 **아무것도 하지 않는다**(텍스트 붙여넣기는 기본 동작). 파일이 있을 때만 `preventDefault` 하고 업로드한다. 포커스가 `<input>`·`<textarea>` 이면 무시해 식별 칸과 충돌하지 않게 한다.
  3. 이름 없는 캡처(`image.png`)는 `{통제코드}_S{seq}_{yyyyMMdd-HHmmss}.png` 로 바꿔 `new File([...], name, {type})` 로 올린다.
  4. 업로드 전에 기존 `validateFile` 을 재사용한다(지금 샘플 업로드에는 클라이언트 검증이 없다 — 함께 붙인다).
  5. 여러 파일을 붙여넣으면 순차 업로드한다. 기존 `upload` 뮤테이션을 그대로 쓴다.
- 폴백: 없음.

### 확인 필요(사용자 판단)
- 증빙 관리 화면의 업로드 다이얼로그에도 붙일지. 추천은 **내 평가 샘플 줄만**이다. 조사 4에서 증빙 관리를 관리자 전용으로 바꾸면 일반 사용자 경로는 샘플 줄뿐이다.
- 같은 sha256 중복 업로드를 경고할지(별건 추천).

---

## 3. RCM AW열 통제현황 → 테스트절차 영역 표시

### 현황
- 샘플 파일 `backend/seeds/2026 설계평가_RCM 리스트_FV_20261013.xlsx`(미추적) Sheet1
  - 6행 AV=`RAWC`, **AW=`통제현황(WTT의 summary 수준)`**, AX=`테스트절차`(묶음 머리글). 7행 AX~BE 에 `테스트방법`·`모집단`·`평가주기`·`표본수`·`테스트절차`.
  - 데이터 93행 중 **AW 93행 모두 값 있음**(긴 서술형 다줄 텍스트, 2건은 "해당사항 없음").
  - R열 `통제활동설명`(→ `description`)과 **AW 는 93건 모두 다르다** → 별개 정보다.
- import 코드 `backend/app/api/rcm.py`
  - 핵심 열은 **고정 위치**(예: 1302행 `description=row[17]`). 테스트 방법 영역은 **헤더 이름 기반**(1143-1205행 `_TEST_TEXT_HEADERS`·`_test_columns`, "2026-10-13 판은 한 칸 왼쪽"이라 이름으로 찾도록 바꿨다).
  - **AW(`통제현황…`)는 매핑에 없다 → 무시된다.**
  - 갱신 업로드 `services/rcm_excel_sync.py:17-25` `CONTROL_FIELDS` 에도 없다.
- DB (운영 실조회)
  - `baseline_controls`·`control_instances` 컬럼에 통제현황 칸이 **없다**(test_methods·population·sample_size·test_procedure 까지만).
  - 현재 값 채움(resolver 기준 93건): description 93 · test_procedure 93 · population 92 · sample_size 93 · test_methods 93. `control_instances` 는 93건 모두 `override`.
- 화면·API
  - `frontend/src/features/my-assessment/components/ActivitySheet.tsx:72-77` "RCM 테스트 방법" 박스(방법·모집단·절차). 데이터는 worklist 의 `rcm_test_*`(`backend/app/api/assessment.py:937-939`, 스키마 `schemas/assessment.py:156-173`).
  - RCM 상세 `frontend/src/features/rcm/components/ControlDetailSheet.tsx:182` 테스트 절차 표시.
  - 참고: 운영평가 엑셀 내보내기 `services/assessment_export.py:39,158` 은 "통제현황(WTT…)" 칸에 지금 **`description` 을 대신 넣고 있다**(Regina STEP 0 결정, AW 데이터가 없어서).

### 영향 범위 / 리스크
- 새 컬럼이 필요하다 → **migration 필요**(컬럼 추가만, 기존 데이터 변경 없음).
- 운영 RCM 93건은 이미 올라가 있어서 **새 컬럼이 비어 있게 된다.** 같은 엑셀로 **갱신 업로드**(`rcm_excel_sync`)를 하면 diff 로 채워진다. 회계연도 RCM 승인 흐름(13.9-127)을 다시 타게 된다.
- 필드 목록이 여러 곳에 흩어져 있다(resolver `CONTROL_FIELDS`·merge, `rcm_excel_sync.CONTROL_FIELDS`, `rcm_diff` 라벨, 스냅샷, 스키마, 폼). 하나라도 빠지면 diff·스냅샷에서 값이 사라진다.
- AW 를 고정 위치로 읽으면 양식이 한 칸 밀릴 때(이미 2026-10-13 판에서 있었던 일) 깨진다.

### 추천안 (1개)
- 변경 계층: DB(**migration: `baseline_controls`·`control_instances` 에 `control_status text NULL` 추가**) + API + 프론트
- 핵심 로직
  1. **import**: `_TEST_TEXT_HEADERS` 에 `"통제현황(WTT의summary수준)"` → `control_status` 를 추가한다(공백 제거 후 비교). **헤더 이름 기반**이라 열 위치에 의존하지 않는다. "통제현황"으로 시작하는 헤더를 접두 매칭하고 `(기존프로세스)` 변형은 제외한다.
  2. 필드 목록 4곳(resolver·excel_sync·rcm_diff 라벨 "통제현황"·schemas/rcm)에 추가해 스냅샷·diff·갱신 업로드가 같이 움직이게 한다.
  3. **API**: `WorklistRow.rcm_control_status` 를 추가한다.
  4. **프론트**: ActivitySheet "RCM 테스트 방법" 박스 **맨 위**에 "통제현황"(`whitespace-pre-wrap`, 길면 접기)을 표시한다. RCM 상세·폼에도 같은 칸을 둔다.
  5. 내보내기의 "통제현황(WTT)" 칸을 `control_status` 로 바꾸고, 비어 있으면 `description` 으로 폴백한다(기존 동작 유지).
  6. **운영 값 채우기 — 재승인 없이 1회 보강 적재**(2026-10-16 Regina 결정, 아래 "결정" 참조).
  7. **`rcm_diff`**: 비교하는 두 스냅샷 중 한쪽에 키가 **없으면**(필드 도입 전 스냅샷) 그 칸은 비교하지 않는다. 키 없음과 빈 값을 구분한다. 그러지 않으면 다음 판(v5) 비교에 93건이 "통제현황 추가"로 뜬다.
- 폴백: 없음.

### 결정 (2026-10-16 Regina) — 재승인하지 않는다
- 근거: v4 확정본은 **이 엑셀 파일 그 자체**다. AW 는 승인된 원본에 있었는데 import 가 버린 칸이다. 채우는 것은 **내용 변경이 아니라 누락된 적재를 완성하는 것**이다 → 새 판·재승인 대상이 아니다.
- 방식: 1회 보강 스크립트(`scripts/` 또는 `app/seeds/`), dry-run 먼저 실행
  1. 파일 sha256 = `7a36ee5a…f5ad` 확인(v4 원본과 같은 파일)
  2. 통제 코드 93건이 현재 RCM 과 1:1, **기존 칸(설명·테스트 절차·표본수 등)이 현재 값과 모두 일치**해야 진행. 하나라도 다르면 중단(다른 판 파일 방지)
  3. `control_status` 가 NULL 인 칸만 채운다. 다른 칸은 건드리지 않는다
  4. `rcm_snapshots` v4(확정본 JSON)는 **수정하지 않는다**. 확정 기록은 손대지 않고, 7번의 diff 규칙으로 다음 판 비교의 오탐을 막는다
- 실행은 §8.4 "운영 시드 실행 = 승인 필요" — dry-run 결과(건수·불일치 0)를 보고하고 승인을 받은 뒤 실행한다. 결과(건수·백업 키)는 `ClaudeICFR.md` 에 남긴다.
- 컬럼명: `control_status`(화면 라벨 "통제현황").

---

## 4. 증빙관리 메뉴 관리자 전용

### 현황
- 메뉴: **하드코딩** `frontend/src/config/navigation.ts:142-148`(`/evidence`). 플래그 `requiresIcfrManager` 가 **없다** → 모든 내부 사용자에게 노출된다. 잠금 표시 로직은 `layouts/AppLayout.tsx:128`(잠금 = 회색 + 자물쇠, 클릭 불가), 외부 사용자 필터는 `isPathAllowed`.
- 라우트 가드: `frontend/src/routes/PrivateRoute.tsx` 는 **로그인 여부만** 본다. `routes/index.tsx:69` `/evidence` 에 역할 가드가 없다. 메뉴를 잠가도 **URL 직접 접근으로 들어갈 수 있다**(역할 배정·정책 화면도 같은 구조다. 화면 내부와 서버가 막는다).
- 백엔드 `/api/evidence/*` (`backend/app/api/evidence.py`)
  | API | 가드 | 비고 |
  |---|---|---|
  | GET `/info` | 인증 | |
  | GET `/files` (214) | **인증만** | 테넌트 전체 증빙 목록 |
  | POST `/files` (229) | write + 통제책임자/icfr_manager | **내 평가 샘플 업로드가 사용** |
  | GET `/files/{id}` (293) | 인증만 | |
  | GET `/files/{id}/download` (301) | **인증만** | **내 평가가 사용**(작성자·승인자). id 만 알면 누구나 받는다 |
  | PATCH `/files/{id}` (323) · DELETE (344) | write + `_assert_can_edit_file` | |
  | GET `/files/{id}/history` (370) | 인증만 | |
  | GET `/links` (399) | 인증만 | |
  | POST `/links` (409) | 샘플=작성자 본인 / 그 외 icfr_manager | |
  | DELETE `/links/{id}` (456) | 샘플=작성자 본인 / 그 외 icfr_manager | **내 평가가 사용** |
- 역할 체계(운영 실조회) `user_roles(user_id, role_name, scope)`: icfr_lead 1 · icfr_manager 1 · sys_admin 2 · auditor 1. 일반 사용자(통제책임자 6명)는 테넌트 역할이 없다. 관리자 판정 상수: `TIER_ROLES={icfr_staff, icfr_lead, icfr_manager}`, `READ_ONLY_ROLES={external_auditor, auditor}`(`models/role_assignment.py:148,153`). 가드 `require_icfr_staff`·`require_icfr_manager`(`core/permissions.py:94,104`).
- 프론트의 `/api/evidence` 사용처: `features/evidence/*`(증빙 관리 화면) + **`features/my-assessment/api.ts`(업로드·연결 해제·다운로드 3개)**.

### 영향 범위 / 리스크
- **회귀 위험(4번 핵심)**: 일반 사용자는 내 평가에서 `POST /files`·`DELETE /links/{id}`·`GET /files/{id}/download` 를 쓴다. `/api/evidence` 라우터 전체를 관리자 가드로 묶으면 **통제책임자의 샘플 증빙 업로드와 승인자의 증빙 열람이 모두 깨진다.**
- 지금은 메뉴만 숨기면 의미가 없다. `GET /files`·`/download` 가 인증만 확인하므로 일반 사용자도 API 로 회사 전체 증빙을 받을 수 있다(판매 수준 기준 미달 — 최소권한 위반).

### 추천안 (1개)
- 변경 계층: 프론트 + API. **DB migration 없음**
- 핵심 로직
  1. **메뉴**: `navigation.ts` `/evidence` 에 관리자 플래그를 붙인다. 기준은 `icfr_manager` 단독이 아니라 **TIER_ROLES + READ_ONLY_ROLES**(감사인 열람 필요). `requiresIcfrStaffOrAuditor` 같은 플래그 하나와 `isLocked` 판정 하나만 확장한다.
  2. **라우트 가드**: `RoleRoute`(판정 함수 주입) 컴포넌트를 추가하고 `/evidence` 를 감싼다. 권한이 없으면 `/my-assessment` 로 보낸다. 같은 가드를 `admin/role-assignments`·`admin/policies` 에도 쓸 수 있다(별건).
  3. **API — 엔드포인트별로 나눈다(라우터 일괄 가드 금지)**
     - 관리자 전용(TIER + READ_ONLY): `GET /files`·`GET /files/{id}`·`GET /files/{id}/history`·`GET /links`
     - 유지(이미 통제 단위 판정): `POST /files`·`PATCH`·`DELETE /files/{id}`·`POST/DELETE /links`
     - `GET /files/{id}/download`: **관리자(TIER+READ_ONLY) 또는 그 파일 통제의 owner·assessor·dept_approver** 로 좁힌다(`resolve_roles_for_control` 재사용).
  4. 테스트: 일반 사용자 — 샘플 업로드·연결 해제·자기 통제 다운로드 성공 / 남의 통제 다운로드 403 / `GET /files` 403.
- 폴백(회귀 위험): download 권한 축소가 기존 화면을 깨면 **1단계로 메뉴·라우트·목록 API 만 잠그고** download 축소는 다음 PR 로 미룬다.

### 확인 필요(사용자 판단)
- "관리자"의 범위: **TIER 3단계 + 감사인(열람)** (추천) vs `icfr_manager`(마스터)만. **운영 결정 → 마스터.**
- `sys_admin` 단독 계정(운영 2명)은 제외(현행 원칙 ADR-0038 §2.5: 시스템관리자는 제도 업무를 하지 않는다) — 추천대로면 증빙 관리에 접근하지 못한다.

---

## 5. 4건 간 의존관계

| 관계 | 내용 |
|---|---|
| 1 ↔ 4 | 같은 역할 체계(`user_roles` TIER/READ_ONLY + 통제 단위 `resolve_roles_for_control`)를 쓴다. 4의 다운로드 판정에 "그 통제의 승인 역할 보유자"가 들어가므로 1과 판정 함수를 공유한다(서비스 함수 하나로) |
| 2 ↔ 4 | 4로 증빙 관리 화면이 관리자 전용이 되면 일반 사용자의 업로드 경로는 내 평가 샘플 줄뿐이다 → 2의 붙여넣기 위치가 확정된다. 2는 `POST /files` 만 쓰고 4는 그것을 바꾸지 않으므로 충돌 없음 |
| 3 ↔ 1·2 | 같은 화면(ActivitySheet·worklist 스키마)을 건드린다 — 같은 PR 에 묶지 않는다(머지 충돌만 주의) |
| 3 단독 | migration 포함 → §8.4 백업·push 절차. 다른 3건은 migration 없음 |

## 6. 권장 구현 순서

1. **조사 4 — 증빙 접근 권한**: 현재 열려 있는 정보 노출(목록·다운로드 인증만)을 먼저 닫는다. 프론트 + API, migration 없음
2. **조사 1 — 자기승인 서버 차단 + 승인 대기 건수**: 서버측 SoD. 4와 같은 역할 판정 함수를 쓴다
3. **조사 2 — Ctrl+V 붙여넣기**: 프론트만. 4 이후라 대상 화면이 확정된 상태
4. **조사 3 — AW 통제현황**: migration + 1회 보강 적재(재승인 없음)가 있어 마지막. 독립 PR

## 7. 결정 (2026-10-16 Regina — 추천안 채택)
- 1: 자기승인은 **막기만** 한다(대체 승인 경로 없음). "승인할 통제" = 승인 대기 건만 센다
- 3: 재승인하지 않고 **v4 원본 파일에서 1회 보강 적재**한다(§3 "결정")
- 4: "관리자" = **TIER 3단계 + 감사인(열람)**. sys_admin 단독 계정은 제외
- 1·4는 운영 결정(CLAUDE.md §8.4)이다 — 마스터에게 사후 공유한다.
