# ICFR-EVAL-01 — 평가 3모듈 갭 맵 (테스트·개선계획·증빙)

> 기준 커밋: `dfe28e8` (origin/main 동일) · 조사일 2026-10-02 · 작성 Regina + Claude
> 근거: 로컬 코드 + 로컬 DB(`icfr_db`, alembic `6b6d7fd94f0d`) 읽기 전용 조회. 운영 DB 미조회.
> 프롬프트: `prompts/ICFR-PROMPT-EVAL-01-recon.md`

## 1. 갭 맵

표기: **있음** / **초안만**(동작하나 계약·권한·흐름 미정합) / **없음** / **미확인**

| 모듈 | FE 화면 | FE API 연동 | BE API | DB |
|---|---|---|---|---|
| **테스트 (TestRun)** | 있음 — `features/test` 목록·생성·상세·전이·이력·TestStep CRUD·편집 | 있음 — `testRunsApi.ts` (runs·steps·history·transition). **RAWC는 RCM 화면에서 연동** | 초안만 — `api/test_module.py` CRUD·전이 있음. **쓰기 가드 없음**(`CurrentUser`만), 승인자=수행자 허용, **회차 미연결** | 있음 — `test_runs`·`test_steps`·`test_status_history`·`control_risk_assessments`. `tenant_id` 전부. 로컬 1건 |
| **미비점 (Deficiency)** | 있음 — `RemediationPage` 통합 화면 | 있음 — `deficiencyApi.ts` CRUD | 초안만 — CRUD 있음. **쓰기 가드 없음**. 심각도 `low/medium/high`(ICFR 3단계 아님) | 있음 — `deficiencies`(4건, 삭제 2) |
| **개선계획 (RemediationPlan)** | 있음 — 목록·생성·상세·전이·이력 | 있음 — `remediationPlanApi.ts` | 초안만 — CRUD·4단계 전이 있음. **쓰기 가드 없음**, 승인자 분리 없음, 재테스트 연결 없음 | 있음 — `remediation_plans`(3건)·`remediation_status_history` |
| **설계평가 (DesignAssessment)** | 없음 — 소비 화면 0 | 없음 | 있음 — `/api/remediation/design-assessments` CRUD (가드 없음) | 있음 — `design_assessments` 0건 |
| **평가 회차 (ADR-0032)** | 초안만 — `schedule` 화면이 `cycles`·`incomplete` 조회만 | 초안만 — 조회 2개뿐. 활동·승인·마감 FE 없음 | 있음 — cycles·targets·activities·approvals·close·approve (`require_write`/`require_icfr_manager`) | 있음 — 4테이블, 로컬 0건 |
| **증빙 (Evidence)** | 초안만 — 업로드·목록·다운로드·삭제 화면 | **깨짐** — 업로드가 `file`만 전송. BE는 `cycle_id`·`control_id` Form 필수 → **422**. `fetchEvidenceLinks` 정의만 있고 사용처 0 | 있음 — 통제×회차 업로드, 마감·정책·통제 역할 판정, soft delete(사유), 이력, links(통제 한정). 스트리밍 다운로드(presigned 아님) | 있음 — `evidence_files`(4건, 삭제 2, 레거시 NULL 회차)·`evidence_links` 0건. `cycle_id` FK 없음(설계) |

### 테스트 커버리지
| 영역 | BE | FE |
|---|---|---|
| 테스트 | `test_test_module.py` | 0 |
| 개선계획·미비점 | `test_remediation.py` | 0 |
| 증빙 | 29건 (`test_evidence_cycle` 15·`guard` 7·`retention` 7) — **§12.2 "—" 표기는 낡음** | 0 |
| 회차 | `test_assessment_cycle.py` 16건 | 0 |

## 2. FE 화면 목록 (작성자: 전부 Regina)

| 라우트 | 페이지 | 상태 | 최근 커밋 |
|---|---|---|---|
| `/test` | `features/test/pages/TestPage.tsx` | 실데이터 연동 | `0ef114e` 2026-08-13 (ControlOption 분리) |
| `/remediation` | `features/remediation/pages/RemediationPage.tsx` | 실데이터 연동 | `4b2f66a` 2026-06-29 |
| `/evidence` | `features/evidence/pages/EvidencePage.tsx` | 목록·다운로드 연동. **업로드 422 예상**(BE 계약 변경 미반영) | `8f79f2d` 2026-06-30 |
| `/schedule` | `features/schedule` | 회차 조회만 | — |

- 목업·하드코딩: 3모듈 모두 없음.
- 권한 반영: 3모듈 FE 모두 `can_write`/`tenant_roles` **미사용** — external_auditor에게도 쓰기 버튼 노출.

## 3. 계약 충돌·리스크

| # | 내용 | 심각도 | 근거 |
|---|---|---|---|
| R1 | **증빙 업로드 FE↔BE 계약 불일치** — BE `POST /api/evidence/files`가 `cycle_id`·`control_id` 필수(ADR-0032 §2.7), FE `uploadEvidenceFile(file)`은 파일만 전송 | 높음 (기능 정지) | `api/evidence.py:173`, `evidenceApi.ts` |
| R2 | **테스트·미비점·개선계획 쓰기에 `require_write` 없음** — external_auditor가 생성·전이·승인 가능 (ADR-0031 §2.1 위반) | 높음 (독립성) | `api/test_module.py`, `api/remediation.py` 전 엔드포인트 `CurrentUser` |
| R3 | **승인 직무분리 없음** — 수행자가 자기 TestRun·개선계획을 `approved`로 전이 가능, 승인 역할 검사 없음 | 높음 | `transition_test_run`, `transition_plan` |
| R4 | **평가 모델 이원화** — 레거시 `test_runs`·`design_assessments`(회차 없음, 자체 상태) vs ADR-0032 `assessment_activities`(회차·단계 승인). 어느 쪽이 정본인지 미결 | 높음 (설계) | `models/test_module.py`, `models/assessment.py` |
| R5 | 미비점 심각도 `low/medium/high` — 국내 ICFR 기준(단순 미비점/유의한 미비점/중요한 취약점)과 불일치 | 중 | `schemas/remediation.py:13` |
| R6 | `test_runs`·`deficiencies`·`design_assessments`·`control_risk_assessments`의 `control_id` FK가 **레거시 `controls.id`** 잔존 (13.9-72에서 앱은 baseline/instance 컬럼으로 전환) | 중 | DB FK 조회 |
| R7 | 재테스트 개념 없음 — 개선계획 `approved` 후 TestRun 재수행 연결 필드·흐름 없음 | 중 | 모델 전수 |
| R8 | 증빙 버전 관리 없음 (교체 = 삭제+재업로드). 해시는 있음 | 낮음 | `evidence_files` |
| R9 | 증빙 links 대상이 `control`만 허용 — 테스트·미비점·개선계획에 증빙 첨부 불가 | 중 | `models/evidence.py` `LINK_TARGET_TYPES` |

## 4. §13 반영 후보

1. **[즉시] 증빙 업로드 FE 수정** — 회차·통제 선택 후 업로드(R1). FE 단독.
2. **[즉시] 평가 쓰기 가드** — test/remediation 쓰기 엔드포인트 `require_write` 적용 + FE `can_write` 버튼 숨김(R2). BE·FE.
3. **[결정 필요] 평가 정본 모델 ADR** — TestRun을 assessment_activities로 흡수할지, TestRun에 `cycle_id`를 붙여 병존할지(R4). TrustBuilder 합의 필요.
4. 승인 직무분리 규칙(R3) — 3번 결정에 따라 활동 승인(`activity_approvals`) 재사용 검토.
5. 미비점 심각도 3단계 전환(R5) — 기존 4건 매핑 필요(데이터 변경 → Opus·승인).
6. 레거시 `controls` FK 제거(R6) — 마이그레이션.
7. 재테스트 흐름(R7)·증빙 첨부 대상 확장(R9).
8. FE 평가 3모듈 단위 테스트 신설(현재 0).
9. §12.2 증빙 "테스트 —" → BE 29건으로 정정.
