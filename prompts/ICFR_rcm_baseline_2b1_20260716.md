# ICFR 2-B-1 — Baseline 상위 계층 구축 + FK 체인 복원 명세

- **작성일**: 2026-07-16
- **근거**: ADR-0027 (RCM baseline/overlay 근간), 2-A-1 후속
- **Tier**: Tier 2 (신규 테이블 + 마이그레이션 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화. 병합만 명시적 공통 함수(데이터 정합 우선).
- **설계 원칙(최우선)**: 모든 회사에 유연 적용 가능. baseline은 표준 그릇, 회사별 무한 변형은 instance가 담당. 고정 코딩 0 — 모든 표준 내용은 코드가 아니라 데이터.

---

## 0. 배경 — 왜 2-B가 2-A-3보다 먼저인가

2-A-1에서 `BaselineControl.risk_id`를 **FK 없는 bare UUID**로 둘 수밖에 없었다. 전역 baseline이 tenant 종속 `risks`를 FK로 물면 자동 격리(ContextVar)에 걸려 참조가 깨지기 때문이다.

그 결과 **조회 전환(2-A-3)이 불가능**하다:
- `ControlSearchOut`의 관계 필드(`process_code`·`sub_process_code`·`risk_level`)는 전부 `Control→Risk→SubProcess→Process` **FK 체인 조인**으로 채워진다 (`api/rcm.py:331-340`).
- 검색 필터(`process_code`/`sub_process_code`/`risk_level`)도 같은 조인으로 WHERE를 건다 (`api/rcm.py:291-301`).
- baseline은 이 체인이 끊겨 있어 관계 필드도 검색도 만들 수 없다.

**2-B-1이 이를 해결한다**: 상위 계층을 전역 baseline으로 올리면 `baseline_controls → baseline_risks → baseline_sub_processes → baseline_processes` 체인이 **전부 전역**이라 FK로 깨끗이 묶인다. tenant 필터에 걸릴 일이 없다.

---

## 1. 범위 — 병행 구축 (2-A-1과 동일 전략)

**기존 `processes`/`sub_processes`/`risks`/`risk_categories` 테이블·API는 그대로 둔다.** baseline 계층만 신규 추가. 기존 기능 회귀 위험 없음.

2-B-1이 만드는 것: baseline 계층 4테이블 + FK 체인 + `baseline_controls.risk_id` FK 전환.
2-B-1이 하지 않는 것: instance 테이블(2-B-2), 어서션 junction overlay(2-B-3), resolver 확장(2-B-4), 데이터 이관(2-A-2).

---

## 2. Baseline 계층 4테이블 (전역, tenant 비종속)

전부 `IdentityBase` 상속 (`BaselineControl`과 동일 — TenantMixin 적용 대상 아님).
각 테이블의 필드는 대응하는 기존 모델(`models/rcm.py`)을 **그대로 미러링**한다. 작업 전 실제 필드를 확인할 것.

### baseline_processes
- 기존 `Process` 필드 미러링: `code`(String(20)), `name`(String(100)), `description`(Text nullable)
- `code` **전역 unique**

### baseline_sub_processes
- 기존 `SubProcess` 필드 미러링: `code`(String(20)), `name`(String(200))
- `process_id`: **FK → baseline_processes.id**, NOT NULL, index
- `code` 전역 unique

### baseline_risks
- 기존 `Risk` 필드 미러링: `code`(String(30)), `description`(Text NOT NULL), `assessment_level`(String(5), default "LR")
- `sub_process_id`: **FK → baseline_sub_processes.id**, NOT NULL, index
- `code` 전역 unique

### baseline_risk_categories (어서션)
- 기존 `RiskCategory` 필드 미러링: `code`(String(10)), `name`(String(50)), `description`(Text nullable)
- `code` 전역 unique

> **설계 결정 — RiskCategory는 baseline만, instance 미도입.**
> 어서션(E·C·V·R·P·O·M)은 회계감사기준이 규정하는 제도 고정 개념으로, 회사별로 목록이 갈리는 실무 case가 희박하다. ADR-0025의 "골격은 제도가 강제, 내용만 가변"에서 골격 쪽에 해당한다.
> 이는 "고정 코딩 0" 원칙에 위배되지 않는다 — 어서션 목록은 코드가 아니라 `baseline_risk_categories` **테이블 데이터**이므로, 감사기준 개정 시 데이터 변경으로 대응한다.
> **필요 시 후속에서 instance 테이블만 추가하면 되며 다른 계층 구조에 영향이 없다**(되돌리기 쉬운 결정). 반대로 지금 instance를 열면 resolver·병합·junction overlay에 계층이 영구히 하나 더 붙어 빼기 어렵다. 비대칭이 baseline-only를 가리킨다.

### 관계(relationship)
기존 rcm.py의 관계 구조를 미러링: baseline_processes.sub_processes ↔ baseline_sub_processes.process, baseline_sub_processes.risks ↔ baseline_risks.sub_process, baseline_risks.controls ↔ baseline_controls.risk

---

## 3. BaselineControl.risk_id — FK 전환 (핵심)

현재 `models/rcm_baseline.py:33`:
```python
risk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)  # FK 없음
```

이를 **FK로 전환**:
```python
risk_id: Mapped[UUID | None] = mapped_column(
    PG_UUID(as_uuid=True), ForeignKey("baseline_risks.id"), nullable=True, index=True
)
```

- 2-A-1의 위임 결정("2-B에서 baseline_risks 신설 시 FK 전환")을 이행하는 것.
- nullable 유지 (아직 이관 전이라 기존 baseline_controls 행이 없거나 risk_id가 비어 있을 수 있음. 이관(2-A-2) 후 NOT NULL 검토).
- **`ControlInstance.risk_id`는 건드리지 말 것** — instance는 tenant 종속이므로 기존 `risks` FK 유지가 맞다. 이중 참조(baseline risk vs instance risk) 설계는 2-B-2에서 다룬다.

---

## 4. 마이그레이션

- baseline_processes, baseline_sub_processes, baseline_risks, baseline_risk_categories **신규 생성**
- baseline_controls.risk_id에 **FK 제약 추가** (기존 컬럼은 그대로, 제약만)
- 기존 테이블(processes/sub_processes/risks/risk_categories/controls) **미변경**
- downgrade: FK 제약 제거 + 4테이블 drop 왕복 검증
- 마이그레이션 후 기존 `controls` count = 95 확인 (데이터 보존, ADR-0023)

> baseline_controls에 기존 행이 있고 risk_id가 baseline_risks에 없는 값이면 FK 추가가 실패한다. 현재 baseline_controls는 비어 있을 것으로 예상되나, **실제 count를 확인 후 진행**할 것. 데이터가 있으면 보고.

---

## 5. 완료 기준

- [ ] baseline 계층 4테이블 (IdentityBase, 전역, code 전역 unique)
- [ ] FK 체인: baseline_sub_processes→baseline_processes, baseline_risks→baseline_sub_processes
- [ ] baseline_controls.risk_id → baseline_risks FK 전환
- [ ] ControlInstance.risk_id 미변경 확인 (tenant 종속, 기존 risks FK 유지)
- [ ] 마이그레이션 신규 테이블만 + 기존 controls 95 불변
- [ ] downgrade 왕복
- [ ] 테스트: baseline 계층 FK 체인 조인 동작(baseline_control → risk → sub_process → process 경로로 code 조회), 전역성(tenant 컨텍스트 무관하게 조회됨)
- [ ] pytest 전체 통과 (기존 90 회귀 없음)

완료 후 `docker compose up -d --build backend` 재빌드. **기존 controls count=95 확인**. config.py admin_password 건드리지 말 것.

---

## 작업 전 확인 (Claude Code 먼저 수행)

- `models/rcm.py` — Process/SubProcess/Risk/RiskCategory 실제 필드 (미러링 정확히)
- `models/rcm_baseline.py` — BaselineControl의 IdentityBase 패턴 (동일하게 적용)
- baseline_controls 현재 행 수 (FK 추가 전 데이터 유무 확인)

---

ICFR_rcm_baseline_2b1_20260716.md 진행해줘
