# ICFR 2-A-1 — Control baseline/instance 구조 신규 구축 명세

- **작성일**: 2026-06-15
- **근거**: ADR-0027 (RCM baseline/overlay 2단계 근간)
- **Tier**: Tier 2 (신규 테이블 + 마이그레이션 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화. 단, 병합 로직은 명시적 공통 함수(데이터 정합 우선).
- **설계 원칙(최우선)**: 이 시스템은 **모든 회사에 유연하게 적용 가능**해야 한다. baseline은 표준 그릇, instance는 회사별 무한 변형(adopt/exclude/override/add). 어떤 회사의 어떤 커스터마이징 case도 담을 수 있는 구조로 짓는다.

---

## 0. 범위 — 안전한 첫 삽

**기존 `controls` 테이블·API는 그대로 두고**, baseline/instance 구조를 **병행 신규 구축**한다. 기존 기능이 도는 채로 새 뼈대를 옆에 짓고, 후속 단계(2-A-2 이관 → 2-A-3 조회 전환 → 2-A-4 CRUD 전환)에서 검증하며 갈아끼운다. 이 단계는 신규 추가만 하므로 기존 기능 회귀 위험이 없다.

2-A-1이 만드는 것: baseline_controls 테이블, control_instances 테이블, 병합 함수, 기본 테스트. **기존 controls 미변경.**

---

## 1. baseline_controls 모델 (표준, tenant 무관)

Basic-perfect 통제의 그릇. 현 `Control`의 전 필드를 그대로 갖되 **tenant 비종속**(baseline은 전역 표준).

- base: `IdentityBase`(tenant_id 없음 — Tenant/User처럼 tenant 비종속). TenantMixin 적용 대상 아님.
- 필드: 현 Control 전 필드 미러링 — code, name, description, objective, owner_name, is_key_control, preventive_detective, auto_manual, activity_approval/verification/physical/master_data/reconciliation/supervision, related_accounts, frequency, ipe_relevant, related_systems, euc_description
- `risk_id`: 2-A-1에서는 기존 risks 테이블 참조 유지(계층 baseline은 2-B). **본 단계는 Control 계층에 집중**, 상위 계층 baseline화는 2-B로 미룸. → risk_id nullable로 두거나 기존 risks 참조(2-B에서 baseline_risks로 전환). 구현 시 결정 후 보고.
- `code`: **전역 unique** (표준은 하나뿐)

## 2. control_instances 모델 (회사별 결정 — 유연성의 핵심)

회사별 무한 변형을 담는다.

- base: `AuditedBase` (TenantMixin 포함 → tenant_id 자동)
- `baseline_control_id`: FK→baseline_controls, **nullable** (add는 baseline 없음)
- `action`: `String` — "adopt" | "exclude" | "override" | "add"
- **override 필드 (nullable 미러링)**: baseline_controls의 전 필드를 **전부 nullable로** 미러링. NULL=baseline 따름, 값 있으면 override. (ADR-0027 필드 diff — JSON 아님, 정렬·검색·타입안전 유지)
- `code`: instance 자체 code (add·override 시). `(tenant_id, code)` **복합 unique**

**action별 데이터 규칙**:
- adopt: baseline_control_id 채움, override 필드 전부 NULL
- exclude: baseline_control_id 채움, override 필드 NULL (제외 표시)
- override: baseline_control_id 채움, 변경 필드만 값 채움
- add: baseline_control_id NULL, 자체 필드 전부 채움

## 3. 병합 함수 (공통·명시적)

`resolve_controls(tenant_id)` — RCM 조회의 유일한 진입점(후속 단계에서 API가 이걸 거침).

```
resolve_controls(tenant_id) -> list[결과 통제]:
  1. baseline_controls 전체 로드 (전역)
  2. control_instances(tenant_id) 로드  # tenant 자동격리로 이미 필터됨
  3. exclude된 baseline_control_id 집합 → baseline에서 제거
  4. baseline 각 항목에 대해:
       - override instance 있으면: baseline 필드 + instance의 non-NULL 필드 병합
       - adopt면: baseline 그대로
  5. add instance(baseline_control_id NULL) → 자체 값으로 추가
  6. 최종 목록 반환
```

- 병합 결과는 기존 Control 응답과 **동일한 형태**여야 함 (후속 API 전환 시 프론트 호환).
- 이 함수 하나가 "모든 회사의 통제 = 표준 ± 회사결정"을 계산하는 단일 지점. 모든 조회가 여기를 거치도록 후속 설계.

## 4. 마이그레이션

- baseline_controls, control_instances 테이블 **신규 생성만**.
- 기존 controls 테이블·데이터 **미변경** (이관은 2-A-2).
- downgrade로 두 테이블 drop 왕복 검증.
- 기존 controls 95건 그대로 유지 확인.

## 5. 완료 기준

- [ ] baseline_controls 모델 (tenant 비종속, code 전역 unique)
- [ ] control_instances 모델 (tenant_id, action, nullable override 미러링, 복합 unique)
- [ ] resolve_controls 병합 함수 (adopt/exclude/override/add 4 case 처리)
- [ ] 마이그레이션 — 신규 테이블만, 기존 controls 95 미변경 확인
- [ ] downgrade 왕복
- [ ] 병합 단위 테스트: 4 action 각각 + 혼합 case (baseline 3개 중 1 exclude·1 override·1 adopt + add 1 → 결과 검증)
- [ ] pytest 전체 통과 (기존 기능 회귀 없음)

완료 후 `docker compose up -d --build backend` 재빌드. **기존 controls count=95 유지 확인**. config.py admin_password 건드리지 말 것.

---

## 작업 전 확인 (Claude Code 먼저 수행)

- `models/rcm.py` Control 전 필드 (미러링 정확히)
- `models/tenant.py` IdentityBase / AuditedBase 차이 (baseline은 IdentityBase, instance는 AuditedBase)
- `models/base.py` TenantMixin 적용 방식 (instance에 tenant_id 자동 확인)

---

ICFR_rcm_baseline_2a1_20260615.md 진행해줘
