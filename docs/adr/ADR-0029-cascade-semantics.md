# ADR-0029: 계층 cascade 시맨틱 및 overlay 소유 경계

- 상태: **채택** (2026-08-24 — 제안(초안)에서 전환. 근거는 §7)
- 작성일: 2026-08-24
- 관련: ADR-0020(제로 추상화), ADR-0027(조회 resolver), 2-A-4-3
- 배경 실측: `process_instances` 스키마 (운영 서버 psql, 2026-08-24)

---

## 1. 배경

baseline/overlay 멀티테넌시에서 통제 계층은 2-A-3·2-A-4-2로 resolver 전환이 끝났으나
상위 3계층(process / sub_process / risk)은 미배선 상태다. 2-A-4-3에서 이를 배선하며
상위 계층 CRUD를 붙이려면, 그 전에 **계층 간 제외가 어떻게 전파되는지**를 확정해야 한다.

확정 없이 CRUD를 먼저 붙이면 다음이 발생한다.

- 상위를 제외했을 때 하위가 어떤 상태가 되는지 코드마다 다르게 구현됨
- 상위를 복원했을 때 하위의 개별 제외가 소실됨
- 통제가 제외됐는데 어서션 연결만 남는, 제도상 성립하지 않는 상태

## 2. 결정

### 2.1 cascade 판정은 resolver 내부 단일 조회로 처리한다

상위 계층이 제외된 경우, 하위 계층은 **물리적으로 변경하지 않는다.**
하위 레코드는 그대로 두고, 조회 시점에 effective 상태만 계산한다.

계산 방식은 다음으로 한정한다.

- resolver가 해당 테넌트의 상위 제외 목록을 **한 번** 읽는다
- 그 목록을 하위 계층 필터링에 사용한다
- 계층별로 부모를 거슬러 올라가는 재귀 조회를 하지 않는다

**기각한 대안** — 하위 조회 시 process → sub_process → risk → control 체인을 매번 타는 방식.
현재 통제 93건에서는 문제가 없으나, 고객사 규모(통제 수백 건)에서 매 조회마다 4중 조인이
발생한다. 판정 결과는 같고 비용만 다르므로 단일 조회를 택한다.

### 2.2 하위의 "상위로 인한 제외" 상태는 저장하지 않는다

하위 instance 레코드는 **자기 자신의 제외만** 기록한다.
상위로 인한 제외는 조회 시점에 얹는다. 저장하지 않는다.

이 결정의 귀결로 **복원이 자동으로 성립한다.**
상위 제외가 해제되면 하위는 별도 작업 없이 자기 원래 상태로 돌아간다.
하위의 개별 제외는 애초에 건드리지 않았으므로 보존된다.

**기각한 대안** — 하위에 "상위로 인한 제외" 플래그를 명시 저장하는 방식.
데이터가 진실을 담는다는 장점이 있으나, 상위 상태와 하위 플래그가 어긋날 수 있는
동기화 지점이 생긴다. 복원 시 플래그를 되돌리는 로직도 별도로 필요하다.
유도 가능한 값을 저장하지 않는 편이 어긋날 여지가 없다.

### 2.3 어서션 junction은 baseline이 소유하고, 변경은 통제 overlay가 기록한다

- 통제-어서션 연결 469건은 **baseline에 속한다** (표준 RCM의 일부)
- 고객사가 연결을 떼거나 붙이는 변경은 **통제 overlay가 기록한다**
- 어서션 계층에 별도 overlay 계층을 두지 않는다

**근거** — 어서션 자체(실재성·완전성·정확성·권리와 의무·표시와 공시)는 제도가 정하는
고정 집합이며 고객사가 바꿀 대상이 아니다. 고객사가 판단하는 것은 "이 통제가 어느 어서션을
커버하는가"이고, 그 판단의 주체는 통제다. 따라서 연결의 관리 지점도 통제여야 한다.

어서션에 overlay 계층을 두면 제외·수정 로직을 한 벌 더 만들어야 하고,
바뀔 일이 없는 대상에 대한 코드가 된다.

### 2.4 통제와 어서션 연결은 동시에 움직인다

통제가 제외되면 그 통제에 걸린 어서션 연결도 함께 제외된다.

**근거** — 내부회계관리제도상 통제 없는 어서션 연결은 성립하지 않는 개념이다.
연결이란 "이 통제가 이 어서션을 커버한다"는 진술이므로, 통제가 없으면 진술 자체가 없다.
제도에서 성립하지 않는 상태를 DB에서 표현 가능하게 두지 않는다.

구현상으로는 2.1·2.2와 동일하게 처리된다. 연결 레코드를 물리적으로 건드리지 않고,
통제가 effective 제외이면 그 연결도 effective 제외로 계산한다.

### 2.5 overlay-only 항목도 동일한 cascade 규칙을 적용한다

고객사가 baseline에 없는 프로세스를 신규 생성한 경우(`action='add'`),
그 아래 하위 계층도 overlay에만 존재한다. 이 항목들에도 2.1~2.4와 **동일한 규칙**을 적용한다.

- overlay-only 상위를 제외하면 그 아래도 effective 제외
- 복원하면 하위의 개별 제외 상태 그대로 돌아옴

규칙을 두 벌 만들지 않는다. baseline 유래 여부는 cascade 동작에 영향을 주지 않는다.

### 2.6 신규/기존 판정은 `action` 컬럼으로 한다

`baseline_*_id IS NULL` 로 신규 여부를 판정하지 않는다.
판정은 `action` 컬럼 값으로만 한다.

**실측 근거** (`process_instances`, 운영 서버 2026-08-24)

```
baseline_process_id  uuid     NULL 허용
action               varchar(10)  NOT NULL
tenant_id            uuid     NOT NULL
```

`action`이 이미 overlay의 의도를 담는 컬럼으로 존재한다.
`baseline_process_id`가 NULL인 것은 `action='add'`의 **결과**이며, 판정 근거가 아니다.

**별도 `origin` 컬럼을 추가하지 않는다.** 초안 검토 중 신규 컬럼 도입을 검토했으나
스키마 실측 결과 `action`이 동일 정보를 이미 보유함을 확인했다. 중복 저장은
두 값이 어긋날 때 무엇이 맞는지 판정할 수 없게 만든다.

회귀 방지 원칙(판별은 구조/타입으로) 부합 — `action`은 명시적 enum 성격의 값이며,
NULL 여부라는 암묵 규약에 의존하지 않는다.

**2026-08-24 실측 반영 (2-A-4-3 구현 중)** — 위 서술의 "명시적 enum 성격"은 **의미상 그렇다는 뜻이고,
코드에는 enum 도 CHECK 제약도 없었다.** 실제로는 `String(10)` 컬럼 + 모델 주석
(`# "adopt" | "exclude" | "override" | "add"`) + `control_resolver.py`·`api/rcm.py` 에 흩어진
문자열 리터럴로만 존재했다. 즉 판정 근거로 삼을 **참조 가능한 정의가 없는 상태**였다.

→ 본 작업에서 `app/models/rcm_baseline.py` 에 모듈 상수로 정의했다.

| 집합 | 상수 | 대상 |
|---|---|---|
| `INSTANCE_ACTIONS` | `ACTION_ADOPT` / `ACTION_EXCLUDE` / `ACTION_OVERRIDE` / `ACTION_ADD` | 계층 overlay 4테이블 |
| `ASSERTION_ACTIONS` | `ASSERTION_ACTION_ADD` / `ASSERTION_ACTION_REMOVE` | `control_assertion_instances` |

두 집합은 값이 다르고 `"add"` 만 겹치므로 **접두사로 분리**한다(섞어 쓰면 값만으로는 구분되지 않는다).
기존 리터럴도 전부 상수 참조로 교체했다 — 두 방식이 공존하면 무엇이 진실인지 판정할 수 없기 때문이다.
DB 레벨 CHECK 제약 도입은 하지 않았다(마이그레이션 범위 밖, 별건).

---

## 3. 스키마상 유의점

`process_instances`에 다음 유니크 제약이 존재한다.

| 제약 | 대상 |
|---|---|
| `uq_process_instances_tenant_baseline` | (tenant_id, baseline_process_id) |
| `uq_process_instances_tenant_code` | (tenant_id, code) |

**PostgreSQL에서 NULL은 유니크 제약에 걸리지 않는다.**
따라서 `action='add'` 레코드(baseline_process_id IS NULL)는 첫 번째 제약의 보호를 받지 않으며,
중복 방지는 `uq_process_instances_tenant_code`가 담당한다.

2-A-4-3 구현 시 신규 추가 경로에서 **code 중복 검증을 명시적으로 수행할 것.**
DB 제약에만 의존하면 에러 메시지가 사용자에게 의미 없는 형태로 노출된다.

**2026-08-24 실측 반영 (2-A-4-3 구현 중)** — 위 표는 `process_instances` 만 실측한 것이었다.
나머지 2개 계층도 **동일한 2개 제약을 보유**함을 확인했다. NULL 통과 문제는 3계층 공통이다.

| 테이블 | `(tenant_id, baseline_*_id)` | `(tenant_id, code)` | single_parent CHECK |
|---|---|---|---|
| `process_instances` | ✅ | ✅ | — (최상위) |
| `sub_process_instances` | ✅ | ✅ | ✅ |
| `risk_instances` | ✅ | ✅ | ✅ |

**추가로 확인된 사각지대**: `uq_*_tenant_code` 는 **instance 끼리의 충돌만** 막는다.
회사가 추가한 항목의 `code` 가 **baseline 테이블의 `code` 와 겹치는 경우는 어떤 DB 제약도 막지 못한다**
(서로 다른 테이블이라 제약이 걸치지 않는다). 이 경우 resolver 결과에 같은 code 가 둘 나온다.

→ 핸들러 검증은 **baseline·instance 양쪽을 모두 조회**해야 한다. 본 작업의 `_assert_code_available`
(`api/rcm.py`)이 두 곳을 모두 보고 409 를 반환한다. baseline 충돌과 instance 충돌의 메시지를 구분한다.

---

## 4. 영향 범위

| 대상 | 내용 |
|---|---|
| `control_resolver.py` | `resolve_processes` / `resolve_sub_processes` / `resolve_risks` 배선 (구현됨, 호출처 없음) |
| `api/rcm.py` | `/processes` `/sub-processes` `/risks` 조회·CRUD를 resolver 경유로 전환 |
| envelope | 상위 계층 응답에 source 필드 확장 (Regina 협의 A안) |
| 테스트 | cascade 복원 시 하위 개별 제외 보존을 검증하는 케이스 필수 |

## 5. 검증 조건

2-A-4-3 완료 판정에 다음을 포함한다.

1. 운영 서버에서 `/processes` 조회가 8건 반환 (현재 0건)
2. 상위 제외 → 하위 effective 제외 확인
3. 하위 개별 제외 후 상위 제외 → 상위 복원 → **하위 개별 제외가 보존됨** 확인
4. 통제 제외 시 어서션 연결도 effective 제외 확인
5. `action='add'` 항목에 대해 2·3이 동일하게 동작함 확인

3번이 이 ADR의 핵심 검증이다. 이것이 깨지면 2.2 결정이 구현되지 않은 것이다.

**2026-08-24 — 5개 전부 통과.** 검증 코드는 `backend/tests/test_rcm_cascade.py`.

| § | 테스트 함수 | 결과 |
|---|---|---|
| 5-1 | `test_processes_list_returns_all_baseline` | ✅ |
| 5-2 | `test_parent_exclusion_cascades_to_children` | ✅ |
| **5-3** | **`test_child_exclusion_survives_parent_restore`** | ✅ |
| 5-4 | `test_control_exclusion_drops_its_assertions` / `test_cascade_hides_assertions_of_cascaded_control` | ✅ |
| 5-5 | `test_added_hierarchy_follows_same_cascade_rules` | ✅ |
| §2.2 직접 | `test_cascade_does_not_write_to_children` | ✅ |

마지막 항목은 §5 목록에는 없지만 **§2.2(제외 상태 저장 금지)를 직접 고정**한다 —
상위 삭제 후 하위 instance 행 수가 불변인지 본다. 5-3 이 결과를 보는 검증이라면 이쪽은
저장 자체를 보는 검증이라, 둘이 함께 있어야 "계산으로 처리한다"가 코드로 잠긴다.

---

## 6. 미해결

- 상위 계층 "수정"(`action='override'`) 시 하위 표시 규칙 — 수정은 제외가 아니므로
  cascade 대상이 아니라고 판단하나, 코드 변경이 하위 코드 계층에 반영되는지는 별건
- MinIO 증빙이 붙은 통제가 제외될 때 증빙 파일 처리 — 별도 설계

---

## 7. 채택 근거 (2026-08-24)

제안(초안) → **채택**. 구현·검증이 모두 끝났고 운영에서 의도한 결과가 확인됐다.

**구현** — 커밋 5건 (2-A-4-3)

| 해시 | 내용 |
|---|---|
| `6ba94a4` | `action` 허용값 모듈 상수화 (§2.6 실측 반영분) |
| `9401dd8` | 상위 3계층 조회 API resolver 전환 + envelope 확장 |
| `cad62a9` | 상위 3계층 CRUD overlay 전환 (§3 code 중복 검증 포함) |
| `0f9a9b1` | cascade 시맨틱 검증 케이스 (§5) |
| `fc94ad4` | §2.6·§3 실측 반영 이력 |

**운영 확인** — 2026-08-24 배포, 이미지 `fc94ad46bda4de5c6f15cf966f8716b136e4fc8d`

- 통제 93건 정상 표시
- **프로세스 컬럼이 채워짐** — resolver 체인(control→risk→sub_process→process)이 연결됐다는 뜻.
  전환 전에는 상위 계층이 레거시 테이블(운영 0건)을 읽어 비어 있었다.
- 통제 검색의 프로세스 필터 드롭다운 정상 동작 — "EX — 경비관리" 선택 시 3건으로 필터링.
  이 드롭다운이 `GET /api/rcm/processes` 소비처이며, 0건이던 증상의 사용자 접점이었다.

**테스트** — 로컬 `pytest` 152 passed / 2 xfailed / 0 failed, `ruff check .` All checks passed.
§5 검증 조건 5개 + §2.2 직접 검증 1개 전부 통과(위 표).

잔여 xfail 2건은 이 ADR 범위 밖이다 — `upload-excel` 파서(13.6)와 어서션 junction CRUD 전환.
