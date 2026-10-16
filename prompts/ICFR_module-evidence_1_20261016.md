# 증빙 접근 권한 — 증빙관리 관리자 전용 + 열람 최소권한 (조사 4)

> **필요 모델: Opus (STEP 0 · 구현 모두)** — 권한·보안 작업(CLAUDE.md §10-5)
> 실행: `claude --model opus --dangerously-skip-permissions "prompts/ICFR_module-evidence_1_20261016.md 진행해줘"`
> 구현: `claude --continue --model opus --dangerously-skip-permissions`

작성일: 2026-10-16 (Regina)
근거: `docs/investigation_control4.md` §4·§5·§7 (조사 결과·결정 — 재설명하지 않는다), ADR-0031(역할), ADR-0038 §2.5(sys_admin 제외), ADR-0039(외부 사용자)
migration: **없음**

---

## 0. 결정 (확정 — 다시 묻지 않는다)

- "증빙 관리"를 쓸 수 있는 사람 = **`_FULL_VIEW_ROLES`** (`backend/app/api/assessment.py` 의 내 평가 전체 보기와 **같은 집합**)
  = TIER(`icfr_staff`·`icfr_lead`·`icfr_manager`) + READ_ONLY(`external_auditor`·`auditor`) + `external_advisor`
  - sys_admin 단독 계정은 제외한다. 통제책임자 등 일반 사용자도 제외한다
  - 집합을 두 곳에 두지 않는다 → `app/core/permissions.py` 로 올려 assessment·evidence 가 같이 쓴다
- **라우터 전체를 가드로 묶지 않는다.** 내 평가가 쓰는 3개 API가 깨진다(조사 4 회귀 위험)

## 1. 범위

### API (`backend/app/api/evidence.py`)
| API | 변경 후 |
|---|---|
| GET `/files` · GET `/files/{id}` · GET `/files/{id}/history` · GET `/links` | **증빙 열람 역할만**(위 집합) → 그 외 403 |
| GET `/files/{id}/download` | 위 집합 **또는** 그 파일 통제(`obj.control_id`)의 `control_owner`·`assessor`·`dept_approver`(`resolve_roles_for_control`). 레거시(control_id 없음)는 위 집합만 |
| POST `/files` · PATCH/DELETE `/files/{id}` · POST/DELETE `/links` | **변경 없음**(이미 통제 단위 판정) |
| GET `/info` | 변경 없음 |

- 가드는 의존성 하나(`require_evidence_viewer` 등)로 만든다. 다운로드 판정은 함수 하나로 두고, 조사 1(자기승인 차단)에서 같은 역할 해석을 재사용할 수 있게 한다
- 403 문구: "증빙 관리는 내부회계 관리자·감사인만 볼 수 있습니다" / 다운로드: "이 통제의 담당자·승인자 또는 내부회계 관리자만 내려받을 수 있습니다"
- 감사로그는 기존 미들웨어가 기록한다 — 추가 작업 없음

### 프론트
1. `config/navigation.ts` `/evidence` — 잠금 플래그를 추가한다. 기존 `requiresIcfrManager` 와 별도로 **판정 함수를 받는 형태**를 쓴다(예: `requires?: (user) => boolean`)
   - 판정 = `isIcfrStaffForUser(user) || READ_ONLY·external_advisor 보유` → `features/auth/permissions.pure.ts` 에 `canViewEvidenceAdmin(user)` 하나로 둔다. `MyAssessmentPage.tsx` 의 `canFullView`(같은 집합)도 이 함수로 바꾼다
   - 잠긴 메뉴 문구: "내부회계 관리자·감사인만 사용할 수 있습니다"(지금 `NavRow` 는 문구가 고정이다 → 항목별 문구 허용)
2. `routes/` — `RoleRoute`(판정 함수 + 거부 시 `/my-assessment` 로 이동)를 추가하고 `/evidence` 를 감싼다. 다른 라우트에는 이번에 적용하지 않는다(별건)
3. 내 평가(`features/my-assessment`)는 **수정하지 않는다** — 업로드·연결 해제·다운로드가 그대로 동작하는지 테스트로만 확인

## 2. 테스트 (pytest — `tests/test_evidence_guard.py` 에 추가, 기존 픽스처 재사용)
- 일반 사용자(통제책임자): GET `/files`·`/files/{id}`·`/history`·`/links` → 403
- 통제책임자: 자기 통제 샘플 업로드(POST `/files` + sample_id) 201 · 연결 해제 204 · **자기 통제 파일 다운로드 200**
- 같은 통제의 assessor·dept_approver: 다운로드 200 / **다른 통제** 담당자: 403
- icfr_staff·auditor(조회 전용)·external_advisor: 목록·다운로드 200
- sys_admin 단독: 목록 403
- 레거시(control_id 없음) 파일: 관리자 200, 일반 사용자 403
- 프론트 vitest: `canViewEvidenceAdmin` 순수 함수 표(역할별 참/거짓)

## 3. STEP 0 (Opus, 수정 금지 — 보고 후 멈춘다)
1. CLAUDE.md §9 계약 동기화 체크
2. 위 표의 엔드포인트·라인이 현재 코드와 맞는지, `_FULL_VIEW_ROLES` 를 옮길 때 영향받는 import 를 확인
3. 프론트에서 `/api/evidence/files`(목록)·`/links`·`/history` 를 **증빙 관리 화면 밖에서** 호출하는 곳이 있는지 다시 grep(조사 시점: `features/evidence/*` 와 `features/my-assessment/api.ts` 만)
4. 대시보드(`api/dashboard.py:40` 의 `/evidence` 건수)가 일반 사용자에게 증빙 건수를 노출하는지 확인하고 처리 방안을 1줄로 보고
5. 설계안 요약(변경 파일 목록·테스트 목록)을 표로 보고하고 **멈춘다**

## 4. 완료 조건
- `pytest -q` · `npx vitest run --reporter=dot` · 타입체크·lint 통과(실패만 출력, §10-9)
- `docs/api/evidence-contract.md` 권한 표 갱신(기준 커밋 표기)
- `ClaudeICFR.md` §12·§13·§14 갱신(13.9 새 번호, 조사 문서 링크)
- 커밋: `feat(evidence): 증빙관리 관리자 전용·열람 최소권한 (13.9-xxx)` — §8.3 절차. migration 없음
- 운영 배포 후 확인: 일반 사용자 계정으로 `/evidence` 진입 차단 · 내 평가 샘플 증빙 업로드·다운로드 정상
