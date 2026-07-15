# ICFR — ADR-0027 프론트엔드 영향 사전 분석

> 성격: **선점 분석 메모** (코드 착수 아님, 읽기 분석 결과 문서화)
> 작성 시점: 2-A-1 완료 직후, 2-A-3 착수 전
> 목적: TrustBuilder가 2-A-3 스펙을 주는 즉시 프론트가 바로 착수할 수 있도록 영향 지점을 미리 매핑
> 회귀 위험: 0 (읽기 분석만 수행)

---

## 1. 현재 상태 요약 (검증 완료)

- **2-A-1 완료 (2026-07-13):** `baseline_controls` / `control_instances` 신규 구조가 백엔드에 **병행 신설**됨. 기존 단일 `controls` 테이블·API·응답 계약은 **그대로 유지**.
- **병합 로직 단일 지점:** `backend/app/services/control_resolver.py` → `resolve_controls()`
  - BaselineControl + ControlInstance 조회 (활성 tenant 자동 격리, tenant 인자 없음)
  - overlay action 병합: `exclude` → 스킵, `override` → non-null 필드만 baseline 위에 덮어씀 (필드 단위 diff, ADR-0027 §4 구현), `add` → 별도 결과 추가
  - `CONTROL_FIELDS` 리스트가 `rcm.py`의 `ControlBase` 필드와 **1:1 대응** (주석 명시)
  - **출력 dict 구조가 `ControlRead`와 호환되도록 설계됨**
- **resolver는 아직 API 라우터에 미연결.** `backend/app/api/` 어디서도 `resolve_controls` 호출 없음. → 실제 조회 API 전환은 **2-A-3에서** 발생.

**결론: 현 시점 프론트 영향 없음. 대기 상태 유효.**

---

## 2. 2-A-3 전환 시 프론트 영향 매핑

조회 API가 `resolve_controls()` 경유로 전환될 때:

### 영향 없음 (정상 케이스 응답 shape 동일)
- resolver 출력이 `ControlRead` 호환 설계 → **목록/상세 조회 훅의 응답 파싱 로직 변경 불필요**
- `ControlSearchOut` (목록 전용: ControlRead + process_code/sub_process_code/risk_level/assertions 4개 관계 필드) — resolver가 이 관계 필드까지 채워주는지가 유일한 확인 포인트 (§4 질문 참조)
- 쿼리키 구조 변경 불필요 (tenant prefix는 이미 header-axis에서 적용 완료)

### 영향 가능 (id 정체성 문제 — 핵심 리스크)
- resolver의 **id 정체성이 행마다 다름**:
  - baseline 유래 행 → **baseline id**
  - add instance 행 → **instance id**
  - override 시 편집 진입점 id를 무엇으로 할지 → **2-A-4에서 결정 예정** (resolver 주석에 명시)
- → **편집/삭제 훅이 id를 어떻게 다루느냐**에서 영향 발생 가능
- 프론트는 현재 단일 `controls.id` 기준으로 mutation(수정/삭제) 대상 식별 → 2-A-3/2-A-4 이후 id 의미가 이원화되면 **mutation 대상 지정 로직 재검토 필요**

---

## 3. 핵심 리스크: id 정체성 이원화

**보류 지점 (2-A-4 확정 전까지 프론트 착수 금지):**
- override된 통제를 편집할 때 프론트가 어떤 id로 PATCH/PUT를 쏘는가? (baseline id? instance id? 새 override id?)
- add 통제 삭제 시 instance id로 DELETE — 기존 삭제 훅과 엔드포인트가 동일한가 별도인가?
- baseline 유래 통제의 "삭제"는 실제 삭제가 아니라 `exclude` overlay 생성일 가능성 → 삭제 UX·mutation 의미가 바뀔 수 있음

→ 이 부분은 **2-A-4 CRUD 전환 스펙이 확정되기 전엔 프론트 mutation 코드에 손대지 않는다.** 조회(2-A-3)와 CRUD(2-A-4)를 분리 착수.

---

## 4. TrustBuilder에게 2-A-3 스펙 요청 시 확정 질문

1. 2-A-3 전환 후 **목록 조회 API 응답이 `ControlSearchOut`(관계 필드 4개 포함)을 유지**하는가? resolver가 process_code/sub_process_code/risk_level/assertions까지 채워주는가?
2. 조회 응답의 **`id` 필드 의미** — baseline 유래 행과 add 행의 id를 프론트가 구분해야 하는가? 응답에 `source`(baseline/instance) 같은 **판별 필드가 추가**되는가?
3. 2-A-3는 **조회만** 전환인가? (CRUD는 2-A-4로 완전 분리되는지 확정)
4. override diff 저장 방식(nullable 컬럼 vs JSON) 최종 결정 — 프론트 편집 폼이 "변경된 필드만" 전송해야 하는지에 영향
5. baseline 개정 시 프론트에 **버전/개정 알림 UX**가 필요한가? (ADR 미결정 항목)

---

## 5. 착수 트리거

- **2-A-3 조회 전환 스펙 수령** → 위 §4 질문 답변 확보 후 프론트 조회 훅 검토 착수
- **2-A-4 CRUD 스펙 수령** → mutation(편집/삭제) 훅 착수 (그 전까지 보류)
- 관련 파일: `src/lib/queryKeys.ts`, RCM 조회/mutation 훅, RCM Control 타입 정의
