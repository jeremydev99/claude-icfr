# ICFR_module-test_1_20261015 — 회차 기반 '내 평가' 화면 (테스트 + 증빙 한 화면, RCM 담당자 자동 배정)

**필요 모델**: STEP 0 = Opus / 구현 = Sonnet. 단, STEP 0 결과 **기존 데이터를 바꾸는 마이그레이션**(test_runs 이관 등)이 필요하면 구현도 Opus (CLAUDE.md §10-5).

---

## 배경

- 통제책임자가 테스트할 통제를 `/test` 에서 **하나씩 직접 생성**해야 한다(`TestRun`, 회계연도×통제, 회차와 무관).
- 증빙은 `/evidence` 에서 따로 올린다(회차×통제, `evidence_links.linked_entity_type` 은 `control` 만 허용).
- 반면 ADR-0032 회차 모델은 이미 원하는 구조를 갖고 있다.
  - `cycle_targets`: 회차 생성 시 RCM 대상 통제 스냅샷(현재 운영평가 회차 91건)
  - `ACTIVITY_RULES`: `test` 는 `control_owner`(role_assignments) 가 수행
  - `POST /api/assessment/cycles/{id}/activities`, `GET .../activities`, `.../targets`, 승인(`/activities/{id}/approvals`)
  - `export_cycle(mine=true)` 에 "내 담당 통제" 판정 규칙이 이미 있음(`services/assessment_export`)
  - **그러나 activities API 를 쓰는 프론트 화면이 없다.**

## 목표 (마스터 합의 2026-10-15)

1. **한 화면**에서 테스트 결과 입력과 증빙 업로드를 같이 한다.
2. 평가 대상은 **RCM 역할 배정(control_owner) 기준으로 자동** 표시된다. 사용자가 통제를 하나씩 등록하지 않는다.
3. 증빙이 **어느 테스트 결과의 근거인지** 연결된다(PBC 대응).
4. 테스트 기능을 회차 모델 하나로 통일한다. `TestRun` 과 회차 activity 두 체계를 병존시키지 않는다.

---

## STEP 0 — 조사·실측·설계안 (코드·DB·설정 수정 금지, 보고 후 멈춤)

CLAUDE.md §0, §9 절차(ClaudeICFR.md 확인, `git fetch` 동기화 점검) 먼저 수행.

### 0-1. 실측 (운영 DB, §8.4 위임 범위 내 조회만)
- `test_runs`, `test_steps`, `test_status_history`, `control_risk_assessments` 테넌트별 건수
- `assessment_activities` 종류별 건수, `cycle_targets` 회차별 건수
- `evidence_links` 의 `linked_entity_type` 분포, 회차 증빙 건수
- 운영평가 회차의 control_owner 배정 현황: 대상 통제 중 **담당자 미배정 건수**

### 0-2. 코드 조사 (필요한 부분만 발췌)
- `api/assessment.py` 의 targets/activities/approvals, `_role_holder`, 마감(`close`) 시 편집 제한 로직
- `services/assessment_export` 의 "내 담당" 판정 — 목록 API 에서 재사용 가능한지
- `TestRun` 이 가진 항목(평가방법 4종·모집단·빈도·샘플수·절차·WTT 요약)과 `AssessmentActivity`(result·note 뿐)의 차이
- `/test`, `TestRun` 을 참조하는 곳(대시보드 `api/dashboard.py` 포함), 프론트 라우트·네비게이션
- 증빙 API 의 마감·편집 토글·외부감사인 조회전용 규칙(13.9-74)

### 0-3. 설계안으로 보고할 것
| 항목 | 결정할 내용 |
|---|---|
| 화면 위치·이름 | 신규 '내 평가'(가칭) 페이지 vs 일정관리 회차 상세 탭 — 권장안 1개 |
| 목록 API | `GET /cycles/{id}/targets?mine=true` 형태로 담당자·진행상태·증빙수 포함 (관리자는 전체) |
| 테스트 상세 항목 저장 | `assessment_activities` 에 칸 추가(평가방법·모집단·샘플수·절차 등) vs 별도 상세 테이블 — **추가형 마이그레이션** 권장 여부 |
| 증빙 연결 | `LINK_TARGET_TYPES` 에 `activity` 추가, 회차×통제 연결과의 관계(둘 다 남기는지) |
| 진행 상태 | 미착수/작성중/완료/승인 판정 규칙(activity·approval 기준) |
| 재수행 | 같은 통제에 activity 여러 건(ADR-0032 §2.8) — 화면에서 최신 표시 + 이력 |
| `/test` 처리 | 0-1 결과로 결정: 데이터 0건이면 메뉴 제거·코드 정리 / 있으면 이관안(**마스터 승인 대상**) |
| `/evidence` 처리 | 관리자용 회차 전체 증빙 조회로 유지 |
| 담당자 미배정 통제 | 화면 표시 방식(관리자에게 '미배정' 경고) |

- **운영 결정**(결재 단계·누가 무엇을 보는지·미배정 처리 정책)은 별도 표시해 마스터 확인 항목으로 분리한다(CLAUDE.md §8.4).
- ADR-0032 보완 필요 여부(10줄 이내 초안) 함께 제시.
- 예상 변경 파일 목록, 마이그레이션 유무, 테스트 계획.

**보고 후 멈춘다.**

---

## 구현 (STEP 0 확인 답을 받은 뒤)

1. 백엔드: 목록 API(내 담당/전체), activity 상세 항목, 증빙 `activity` 연결, 권한(control_owner 만 기록, 외부감사인 조회전용, 마감 회차 편집 제한) — 서버에서 최종 강제.
2. 프론트: 회차 선택 → 내 담당 통제 목록(상태·증빙 수) → 상세 패널(테스트 입력 + 증빙 업로드·목록 + 이력·승인).
3. `/test` 처리는 STEP 0 확인안대로. 네비게이션·대시보드 참조 정리.
4. 테스트: 백엔드 pytest(권한·마감·내 담당 필터·증빙 연결), 프론트 vitest(pure 로직). 실패만 출력(§10-9). 마이그레이션 있으면 순차 2회(§10-10).
5. 문서: ClaudeICFR.md §12·13·14, ADR-0032 보완, `docs/api/evidence-contract.md` 갱신.
6. 커밋 메시지(안) 제시 → OK 후 §8.3 / 마이그레이션 포함 시 §8.4(백업 확인 후 push, 배포·리비전·건수 확인).

**다음에 할 일**을 한 줄로 끝맺는다.
