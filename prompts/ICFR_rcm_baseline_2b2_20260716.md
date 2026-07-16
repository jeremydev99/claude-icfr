# ICFR 2-B-2 — Instance 상위 계층 구축 + 이중 FK 참조 명세

- **작성일**: 2026-07-16
- **근거**: ADR-0027, 2-A-1(ControlInstance 패턴) / 2-B-1(baseline 계층) 후속
- **Tier**: Tier 2 (신규 테이블 + 기존 instance 컬럼 변경 + 마이그레이션 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화. 설계 원칙 최우선 — 모든 회사 유연 적용, 고정 코딩 0.

---

## 0. 배경

2-B-1로 baseline 계층(Process/SubProcess/Risk/RiskCategory)이 전역으로 섰고 FK 체인이 복원됐다. 이제 **회사별 결정(instance)**을 상위 계층에도 도입해, 회사가 프로세스·하위프로세스·위험을 adopt/exclude/override/add 할 수 있게 한다.

**ControlInstance(2-A-1)의 패턴을 그대로 따른다** — `__table_args__`의 UniqueConstraint 2개 + Index, action, nullable 미러링, relationship. 일관성이 resolver(2-B-4) 설계를 단순하게 만든다.

---

## 1. 범위

**만드는 것**: `process_instances`, `sub_process_instances`, `risk_instances` 3테이블 + 이중 FK 참조 + `ControlInstance` 상위 참조 전환.
**하지 않는 것**: 어서션 junction overlay(2-B-3), resolver 확장(2-B-4), 데이터 이관(2-A-2), API 전환(2-A-3/4).

기존 `processes`/`sub_processes`/`risks`/`controls` 테이블·API는 **미변경**(병행 구축).

---

## 2. 핵심 설계 — 이중 nullable FK (상위 참조)

instance가 상위 계층을 참조할 때 두 경우가 있다:
- **baseline 상위 밑** → `<상위>_baseline_id` → baseline 테이블
- **회사가 add한 상위 밑** → `<상위>_instance_id` → instance 테이블

**정합 규칙 (반드시 지킬 것)**:
1. **override된 상위는 정체성이 여전히 baseline이다** (필드만 덮은 것). 따라서 override된 process 밑의 sub_process는 `process_baseline_id`를 가리킨다. `process_instance_id`는 **add한 상위 밑에서만** 쓴다.
2. **둘 다 NULL = baseline의 상위를 그대로 따름**. 이는 nullable 미러링 규칙("NULL=baseline 따름")과 동일한 의미로, adopt/override에서 상위를 바꾸지 않은 경우다.
3. **둘 다 non-NULL은 금지** — check 제약으로 차단.

UUID + discriminator 방식은 FK 무결성을 잃으므로 채택하지 않는다. 이중 nullable FK가 타입 안전하고 명시적이다.

---

## 3. 테이블 정의

전부 `AuditedBase` 상속(TenantMixin → tenant_id 자동). ControlInstance와 동일 패턴.

### process_instances
- `baseline_process_id`: FK → baseline_processes, nullable, index
- `action`: String(10) — "adopt" | "exclude" | "override" | "add"
- nullable 미러링: `code`(String(20)), `name`(String(100)), `description`(Text)
- 상위 없음 (최상위 계층)
- `__table_args__`: `UniqueConstraint(tenant_id, code)`, `UniqueConstraint(tenant_id, baseline_process_id)`, `Index(code)`

### sub_process_instances
- `baseline_sub_process_id`: FK → baseline_sub_processes, nullable, index
- `action`: String(10)
- nullable 미러링: `code`(String(20)), `name`(String(200))
- **상위 참조 (이중 FK)**: `process_baseline_id`(FK→baseline_processes, nullable) / `process_instance_id`(FK→process_instances, nullable)
- `__table_args__`: UniqueConstraint 2개 + Index + **CheckConstraint** — 이중 FK 동시 non-NULL 금지

### risk_instances
- `baseline_risk_id`: FK → baseline_risks, nullable, index
- `action`: String(10)
- nullable 미러링: `code`(String(30)), `description`(Text), `assessment_level`(String(5))
- **상위 참조 (이중 FK)**: `sub_process_baseline_id`(FK→baseline_sub_processes, nullable) / `sub_process_instance_id`(FK→sub_process_instances, nullable)
- `__table_args__`: UniqueConstraint 2개 + Index + CheckConstraint

> 각 계층의 미러링 필드는 대응 baseline 모델(`models/rcm_baseline.py`)과 정확히 일치시킬 것. 작업 전 확인.

---

## 4. ControlInstance 상위 참조 전환 (중요)

현재 `ControlInstance.risk_id`는 `FK → risks.id`(tenant 종속 기존 테이블)다. 2-B-2에서 **이중 FK로 전환**해 계층 참조 방식을 통일한다:

```python
# 제거: risk_id → risks.id
# 추가:
risk_baseline_id: Mapped[UUID | None] = mapped_column(
    PG_UUID(as_uuid=True), ForeignKey("baseline_risks.id"), nullable=True, index=True
)
risk_instance_id: Mapped[UUID | None] = mapped_column(
    PG_UUID(as_uuid=True), ForeignKey("risk_instances.id"), nullable=True, index=True
)
```
+ CheckConstraint(동시 non-NULL 금지)

**이유**: 상위 참조 방식을 한 번에 통일해야 resolver(2-B-4)가 일관된 규칙으로 짜인다. 나눠서 하면 두 방식이 공존하는 어정쩡한 기간이 생긴다.

**주의**: `control_instances`는 현재 데이터가 없을 것으로 예상되나 **실제 count 확인 후 진행**. 데이터가 있으면 보고 후 결정.

`BaselineControl.risk_id`(→baseline_risks FK)는 **미변경**.

---

## 5. action 데이터 규칙 (전 계층 공통)

ControlInstance docstring과 동일:
- **adopt**: baseline_*_id 채움, 미러링 필드 전부 NULL, 상위 참조 NULL
- **exclude**: baseline_*_id 채움, 나머지 NULL (제외 표시)
- **override**: baseline_*_id 채움, 변경 필드만 값. 상위를 바꿨으면 상위 참조 하나 채움
- **add**: baseline_*_id NULL, 자체 필드 채움, 상위 참조 하나 필수(최상위 process 제외)

각 모델 docstring에 이 규칙을 명시할 것.

> add 시 "상위 참조 하나는 필수"는 action에 따라 달라지므로 DB check로 표현하기 어렵다. 애플리케이션 레벨 검증으로 두고, 명세에 남긴다.

---

## 6. 마이그레이션

- 3테이블 신규 생성 + check 제약
- `control_instances`: `risk_id` 컬럼 제거, `risk_baseline_id`/`risk_instance_id` 추가 + check
- 기존 processes/sub_processes/risks/controls **미변경**
- downgrade 왕복 검증 (역순: control_instances 복원 → 3테이블 drop)
- 마이그레이션 후 기존 `controls` count = 95 확인 (ADR-0023)

## 7. 완료 기준

- [ ] process_instances / sub_process_instances / risk_instances (AuditedBase, ControlInstance 패턴)
- [ ] 이중 nullable FK + CheckConstraint(동시 non-NULL 금지) — sub_process/risk/control
- [ ] ControlInstance.risk_id → risk_baseline_id/risk_instance_id 전환
- [ ] BaselineControl.risk_id 미변경 확인
- [ ] 마이그레이션 + 기존 controls 95 불변
- [ ] downgrade 왕복
- [ ] 테스트: 계층별 4 action 데이터 규칙, 이중 FK check 위반 차단(둘 다 채우면 실패), baseline 상위 참조 / instance 상위 참조 각각 정상, tenant 격리
- [ ] pytest 전체 통과 (기존 92 회귀 없음)

완료 후 `docker compose up -d --build backend` 재빌드. **controls count=95 확인**. config.py admin_password 건드리지 말 것.

---

## 작업 전 확인 (Claude Code 먼저 수행)

- `models/rcm_baseline.py` — ControlInstance의 `__table_args__` 패턴 (동일하게 적용)
- baseline 계층 4모델의 실제 필드 (미러링 정확히)
- `control_instances` 현재 행 수 (risk_id 전환 전 데이터 유무)

---

ICFR_rcm_baseline_2b2_20260716.md 진행해줘
