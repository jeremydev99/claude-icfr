# ICFR 2-A-2 — 기존 RCM 데이터 → baseline 이관 명세

- **작성일**: 2026-07-21
- **근거**: ADR-0027 §7 하이브리드(C) — 95통제를 baseline 초안으로 이관
- **Tier**: Tier 2 (실데이터 이관 → 마스터 push, **가장 신중해야 할 단계**)
- **원칙**: ADR-0020 제로 추상화. ADR-0023 데이터 보존 — **원본 절대 손실 금지**.

---

## 0. 목표와 성격

2-B로 구조(baseline 5 + instance 4 + junction 2)와 resolver가 다 섰다. 이제 **기존 실데이터를 baseline으로 복사**해 resolver가 실제 데이터로 동작하게 한다. 완료되면 2-A-3(조회 API 전환)이 가능해진다.

**이 단계는 이번 작업 전체에서 유일하게 실데이터를 다룬다.** 최우선은 원본 보존이다.

### 이관 대상 (실측 확인됨)

| 기존 테이블 | 행 수 | → baseline 테이블 |
|---|---|---|
| processes | 9 | baseline_processes |
| sub_processes | 30 | baseline_sub_processes |
| risks | 86 | baseline_risks |
| risk_categories | 7 | baseline_risk_categories |
| controls | 95 | baseline_controls |
| control_assertions | 472 | baseline_control_assertions |
| **합계** | **699** | |

---

## 1. 확정 설계

### ① 별도 스크립트 (마이그레이션 아님)
alembic 마이그레이션에 넣지 않는다. 1회성 이관이며 데이터 위험이 최고조이므로, **마스터가 결과를 보며 단계적으로 실행**하고 실패 시 재실행할 수 있어야 한다. 마이그레이션에 넣으면 다른 환경에서 `upgrade head` 시 예측 불가하게 자동 실행된다.

위치: `backend/scripts/migrate_rcm_to_baseline.py` (또는 프로젝트의 기존 스크립트 관례를 따를 것 — 작업 전 확인).

### ② instance 생성 안 함 (암묵 adopt)
resolver는 "instance 없으면 암묵 adopt"로 동작하므로, **baseline만 채우면 사이냅소프트는 699행을 그대로 본다.** instance는 0건으로 둔다.

근거: instance는 **회사의 결정**을 담는 테이블이다. 아직 아무 결정(exclude/override/add)도 하지 않은 상태에서 adopt 행을 만드는 것은 없는 결정을 지어내는 것이다. 실제 결정이 생길 때 그 행이 만들어지는 것이 데이터의 진실에 부합한다. 감사 추적은 워크플로 완성 후 운영 시점부터 유효하며, 현 개발 데이터는 구조 검증용이다.

### ③ 기존 테이블 보존 (복사, 이동 아님)
기존 6테이블은 **건드리지 않는다.** API가 아직 이들을 사용한다(2-A-3 전환 전). 제거는 2-A-4 이후 별도 판단.

---

## 2. 핵심 난제 — id 매핑

기존 테이블의 FK 관계를 baseline 쪽 **새 id**로 다시 이어야 한다. 계층 순서대로 진행하며 `기존 id → baseline id` 매핑 dict를 들고 간다:

```
1. processes       → baseline_processes        : map_process[old_id] = new_id
2. sub_processes   → baseline_sub_processes    : process_id = map_process[old.process_id]
                                                  map_sub[old_id] = new_id
3. risks           → baseline_risks            : sub_process_id = map_sub[old.sub_process_id]
                                                  map_risk[old_id] = new_id
4. risk_categories → baseline_risk_categories  : map_rc[old_id] = new_id
5. controls        → baseline_controls         : risk_id = map_risk[old.risk_id]
                                                  map_control[old_id] = new_id
6. control_assertions → baseline_control_assertions
                        baseline_control_id = map_control[old.control_id]
                        baseline_risk_category_id = map_rc[old.risk_category_id]
```

**순서 엄수** — 상위가 먼저 이관돼야 하위가 FK를 이을 수 있다.

### 필드 복사
각 계층의 필드를 baseline 모델에 **1:1 복사**한다. 실제 필드는 작업 전 `models/rcm.py`와 `models/rcm_baseline.py`를 대조 확인할 것.
- `baseline_version`은 **1**(default)로 둔다 — 현 baseline이 v1.
- `id`는 **새로 생성**(복사하지 않음). baseline은 별도 엔티티다.
- `is_deleted=True`인 기존 행은 **이관하지 않는다** (soft delete된 것). 이관 전 활성 행 수를 세어 보고할 것.
- baseline은 tenant 비종속이므로 tenant_id 없음(IdentityBase).

---

## 3. 안전 장치 (필수)

### 재실행 안전 (idempotent)
스크립트를 두 번 돌려도 중복이 생기지 않아야 한다. 시작 시 baseline 테이블에 이미 데이터가 있으면:
- **중단하고 보고** (기본) — 사용자가 상황을 판단하게 한다
- `--force` 같은 옵션으로 덮어쓰기를 만들지 말 것. 실수로 지우는 경로를 아예 만들지 않는다.

### 트랜잭션
전체 이관을 **단일 트랜잭션**으로 처리한다. 중간 실패 시 전부 롤백되어 부분 이관 상태가 남지 않게 한다.

### 검증 출력
스크립트가 이관 후 다음을 **출력**해야 한다:
```
processes:          9 → baseline_processes 9
sub_processes:     30 → baseline_sub_processes 30
risks:             86 → baseline_risks 86
risk_categories:    7 → baseline_risk_categories 7
controls:          95 → baseline_controls 95
control_assertions:472 → baseline_control_assertions 472
기존 테이블 행 수 (불변 확인): controls 95, control_assertions 472
```
원본과 대상 수가 다르면 **에러로 중단**.

---

## 4. 이관 후 검증 (마스터 수행)

스크립트 실행 후 다음을 확인한다:

1. **원본 보존**: `SELECT count(*) FROM controls` = 95, `control_assertions` = 472
2. **baseline 채워짐**: baseline 6테이블 각각 위 표의 수와 일치
3. **FK 체인 정상**: baseline_control → baseline_risk → baseline_sub_process → baseline_process 조인이 끊김 없이 연결되는지 (샘플 몇 건)
4. **resolver 동작**: `resolve_controls`가 95건을 반환하고, 관계 필드(process_code/sub_process_code/risk_level/assertions)가 채워지는지. **이게 2-A-3 가능 여부를 가르는 핵심 검증이다.**
5. **instance 0건**: control_instances 등이 비어 있는지 (암묵 adopt)

---

## 5. 완료 기준

- [ ] 이관 스크립트 (`backend/scripts/`, 마이그레이션 아님)
- [ ] 계층 순서대로 id 매핑하며 이관 (process→sub_process→risk→risk_category→control→assertion)
- [ ] is_deleted 행 제외, baseline_version=1, id 신규 생성
- [ ] 재실행 안전 — baseline에 데이터 있으면 중단·보고 (덮어쓰기 옵션 만들지 말 것)
- [ ] 단일 트랜잭션 (중간 실패 시 전부 롤백)
- [ ] 검증 출력 (원본 대비 대상 수, 불일치 시 에러)
- [ ] instance 생성 안 함
- [ ] 기존 6테이블 미변경
- [ ] 실행 후: 원본 보존 + baseline 699행 + FK 체인 정상 + **resolve_controls가 95건 관계필드 포함 반환**
- [ ] pytest 전체 통과 (기존 112 회귀 없음)

**주의**: 스크립트 작성 후 **실행 전에 마스터에게 보고**할 것. 실데이터 이관이므로 마스터가 내용을 확인한 뒤 실행 여부를 결정한다. config.py admin_password 건드리지 말 것.

---

## 작업 전 확인 (Claude Code 먼저 수행)

- `models/rcm.py` / `models/rcm_baseline.py` 필드 대조 (1:1 복사 정확히)
- 기존 스크립트 관례 (`backend/scripts/` 존재 여부, seed 실행 방식 참고)
- 각 테이블 `is_deleted=False` 활성 행 수 (이관 대상 확정)
- `services/control_resolver.py` — 이관 후 검증에 사용

---

ICFR_rcm_migrate_2a2_20260721.md 진행해줘
