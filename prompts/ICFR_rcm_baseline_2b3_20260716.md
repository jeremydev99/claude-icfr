# ICFR 2-B-3 — 어서션 Junction baseline/overlay 명세

- **작성일**: 2026-07-16
- **근거**: ADR-0027, 2-B-1(baseline 계층) / 2-B-2(instance 계층) 후속
- **Tier**: Tier 2 (신규 테이블 + 마이그레이션 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화. 모든 회사 유연 적용, 고정 코딩 0.

---

## 0. 배경

`ControlAssertion`(기존)은 통제↔어서션의 **N:M junction**이다 (`control_id` + `risk_category_id`). baseline/overlay 구조에서 이 연결도 회사별로 달라질 수 있어야 한다.

**실재하는 case**: 회사가 baseline 통제 자체는 그대로 채택(adopt)하면서, **어서션 연결만 하나 빼거나 더하는 것**. 예 — 표준은 이 통제에 실재성(E)·완전성(C)을 걸었는데, 우리 회사는 완전성만 본다.

즉 통제의 adopt/override와 **독립적으로** 어서션 연결의 diff가 필요하다.

---

## 1. 핵심 설계

### junction은 4 action이 아니라 2 action
연결은 **있거나 없거나**다. 필드가 없으므로 override할 것도, adopt를 명시할 것도 없다:
- **add**: baseline에 없던 연결을 추가
- **remove**: baseline 연결을 이 회사가 끊음

baseline에 있고 remove도 없으면 → 암묵 채택 (resolver가 그대로 포함). ControlInstance의 "instance 없으면 암묵 adopt"와 같은 원리.

### 어서션 쪽은 단일 FK
RiskCategory는 **baseline-only**(2-B-1 결정 — 제도 고정 개념, instance 미도입)이므로, 어서션 참조는 `baseline_risk_categories` **단일 FK**면 충분하다. 이중 FK 불필요.

### 통제 쪽은 이중 FK
연결 대상 통제는 baseline 통제일 수도, 회사가 add한 통제일 수도 있다 → **이중 nullable FK + check**(2-B-2와 동일 규칙).
**정합 규칙**: override된 통제는 정체성이 여전히 baseline이므로 `control_baseline_id`를 가리킨다. `control_instance_id`는 **add한 통제**에만 쓴다.

---

## 2. 테이블 정의

### baseline_control_assertions (전역, IdentityBase)
표준 통제의 표준 어서션 연결.
- `baseline_control_id`: FK → baseline_controls, NOT NULL, index
- `baseline_risk_category_id`: FK → baseline_risk_categories, NOT NULL, index
- `__table_args__`: `UniqueConstraint(baseline_control_id, baseline_risk_category_id)` — 중복 연결 차단
- relationship: BaselineControl ↔ (기존 `BaselineControl.instances` 패턴 참고하여 back_populates 구성)

### control_assertion_instances (tenant, AuditedBase)
회사별 어서션 연결 결정.
- `action`: String(10) — "add" | "remove"
- **대상 통제 (이중 FK)**: `control_baseline_id`(FK→baseline_controls, nullable, index) / `control_instance_id`(FK→control_instances, nullable, index)
- `baseline_risk_category_id`: FK → baseline_risk_categories, NOT NULL, index
- `__table_args__`:
  - **CheckConstraint** — 이중 FK 동시 non-NULL 금지 (2-B-2의 `ck_*_single_parent` 패턴, 이름 일관되게)
  - `UniqueConstraint(tenant_id, control_baseline_id, baseline_risk_category_id)` — 같은 연결에 두 결정 차단
  - `UniqueConstraint(tenant_id, control_instance_id, baseline_risk_category_id)` — 위와 동일(add 통제 쪽)

> Postgres에서 NULL이 포함된 복합 unique는 중복을 막지 못한다(NULL != NULL). 위 두 unique는 각각 한쪽이 NULL인 행에는 무력하므로, **실질 중복 차단은 애플리케이션 레벨 검증**도 함께 둘 것. 스키마 제약은 최선의 방어로 유지.

---

## 3. 병합 규칙 (2-B-4 resolver가 사용)

한 통제의 어서션 목록 =
```
baseline_control_assertions(그 통제)
  − control_assertion_instances(action=remove)
  + control_assertion_instances(action=add)
```
- add 통제(baseline 없음)의 어서션은 **전부 add 행**으로 표현된다 (baseline 연결이 없으므로).
- 응답 형태는 기존 `ControlSearchOut.assertions`(`["E", "C", "V"]` 코드 배열)와 동일해야 한다 — 2-A-3 전환 시 프론트 호환.

**본 명세는 모델·마이그레이션까지만.** resolver 실제 연결은 2-B-4.

---

## 4. 기존 ControlAssertion 처리

기존 `control_assertions` 테이블·API는 **미변경**(병행 구축). 기존 데이터의 baseline/instance 이관은 **2-A-2 범위**다. 본 단계에서 건드리지 말 것.

---

## 5. 마이그레이션

- 2테이블 신규 생성 + check/unique 제약
- 기존 `control_assertions` 및 기타 테이블 **미변경**
- downgrade 왕복 검증
- 마이그레이션 후 기존 `controls` count = 95 확인 (ADR-0023)

---

## 6. 완료 기준

- [ ] baseline_control_assertions (IdentityBase, 전역, 중복 연결 unique 차단)
- [ ] control_assertion_instances (AuditedBase, action add/remove, 통제 이중 FK + check, 어서션 단일 FK)
- [ ] 기존 control_assertions 미변경 확인
- [ ] 마이그레이션 + controls 95 불변
- [ ] downgrade 왕복
- [ ] 테스트: add/remove 각각, 이중 FK check 위반 차단, baseline 통제 연결 / add 통제 연결 각각, tenant 격리
- [ ] pytest 전체 통과 (기존 98 회귀 없음)

완료 후 `docker compose up -d --build backend` 재빌드. **controls count=95 확인**. config.py admin_password 건드리지 말 것.

---

## 작업 전 확인 (Claude Code 먼저 수행)

- `models/rcm.py` ControlAssertion — 기존 junction 구조
- `models/rcm_baseline.py` — 2-B-2의 이중 FK + CheckConstraint 패턴 (동일 적용, 제약명 일관성)
- `services/control_resolver.py` — 2-B-2에서 최소 수정된 상태 (본 단계에서 건드리지 말 것, 2-B-4 범위)

---

ICFR_rcm_baseline_2b3_20260716.md 진행해줘
