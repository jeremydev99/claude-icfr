# ADR-0030: baseline 테넌트 소유권 및 격리 보장

- 상태: 제안 (초안)
- 작성일: 2026-09-01
- 관련: ADR-0029(cascade 시맨틱), ADR-0020(제로 추상화), 13.9 코드마스터 테이블화
- 배경 실측: `baseline_*` 6테이블 제약 (운영 서버 psql, 2026-09-01)

---

## 1. 배경

### 1.1 개념 혼동이 있었다

현재 운영 중인 baseline 93건은 **사이냅소프트 한 회사의 RCM**이다.
그런데 `baseline_*` 테이블은 `IdentityBase`(테넌트 비종속)로 정의되어 **전역 공유** 상태다.

테넌트가 1개뿐이라 이 불일치가 드러나지 않았다. 두 번째 고객사가 온보딩되는 순간
그 회사도 사이냅소프트의 93건을 자기 baseline으로 받게 된다.

> 2026-08-24에 겪은 것과 같은 종류의 은폐다. 당시에는 로컬 레거시 잔존 데이터가
> 상위 계층 미배선을 가렸다(13.7 정정). 이번에는 테넌트가 하나뿐이라 소유권 문제가 가려졌다.

### 1.2 code 유니크가 전역이다

실측 결과 4개 테이블의 code 유니크가 단일 컬럼이다.

```
ix_baseline_processes_code       UNIQUE btree (code)
ix_baseline_sub_processes_code   UNIQUE btree (code)
ix_baseline_risks_code           UNIQUE btree (code)
ix_baseline_controls_code        UNIQUE btree (code)
```

회사마다 유사한 코드 체계(`EL-010-10-10` 등)를 쓰는 것이 실무상 흔하므로,
**이대로는 두 번째 테넌트가 온보딩되지 않는다.**

### 1.3 이 결정이 선행되어야 하는 작업

- 13.9-10-b(upload-excel 쓰기 경로 전환) — 고객사 엑셀을 어디에 쓸지가 정해지지 않는다
- 코드마스터 테이블화 — 두 번째 테넌트 온보딩 전 필수 항목
- 산업별 템플릿 설계

## 2. 결정

### 2.1 baseline 5테이블은 테넌트 소유로 전환한다

| 테이블 | 소유 | 근거 |
|---|---|---|
| `baseline_processes` | 테넌트별 | 회사마다 프로세스 구조가 다름 |
| `baseline_sub_processes` | 테넌트별 | 〃 |
| `baseline_risks` | 테넌트별 | 〃 |
| `baseline_controls` | 테넌트별 | 〃 |
| `baseline_control_assertions` | 테넌트별 | 연결의 한쪽 끝인 통제가 테넌트 소유 |
| `baseline_risk_categories` | **전역 유지** | 제도가 정하는 고정 집합 |

`baseline_risk_categories` 7건(실재성·완전성·정확성·권리와 의무·표시와 공시 등)은
내부회계관리제도가 규정하는 어서션이며 회사가 바꿀 대상이 아니다.
ADR-0029 §2.3의 판단과 동일하다.

`baseline_control_assertions`에도 `tenant_id`를 둔다. 통제 id가 이미 회사를 특정하므로
논리적으로는 중복이지만, §2.3의 복합 FK를 적용하려면 컬럼이 필요하고,
이 테이블만 격리 보장 방식이 달라지면 유지 비용이 늘어난다.

### 2.2 code 유니크를 `(tenant_id, code)`로 전환한다

4개 테이블 전부. 회사 A와 회사 B가 같은 코드를 쓸 수 있어야 한다.

### 2.3 테넌트 격리는 복합 FK로 DB가 보장한다

**핵심 결정이다.**

instance → baseline FK가 **8개** 존재한다(실측). 계층별 자기 baseline뿐 아니라
상위 baseline도 직접 참조한다.

```
process_instances.baseline_process_id          → baseline_processes
sub_process_instances.baseline_sub_process_id  → baseline_sub_processes
sub_process_instances.process_baseline_id      → baseline_processes
risk_instances.baseline_risk_id                → baseline_risks
risk_instances.sub_process_baseline_id         → baseline_sub_processes
control_instances.baseline_control_id          → baseline_controls
control_instances.risk_baseline_id             → baseline_risks
control_assertion_instances.control_baseline_id → baseline_controls
```

단순 FK로는 **다른 테넌트의 baseline을 참조해도 DB가 통과시킨다.**
A사 overlay가 B사 baseline을 가리키는 상태가 구조적으로 가능하며,
그 결과는 A사 화면에 B사 통제가 표시되는 것이다. ICFR 시스템에서 이는 사고다.

**채택** — baseline 테이블에 `(id, tenant_id)` 유니크를 두고,
instance가 `(baseline_*_id, tenant_id)`로 참조하는 복합 FK.
같은 테넌트가 아니면 DB 레벨에서 삽입이 거부된다.

**기각한 대안 — 애플리케이션 검증**
resolver와 CRUD에서 `tenant_id`를 대조하는 방식. 마이그레이션은 가볍다.
그러나 새 쿼리를 추가할 때마다 사람이 기억해야 하고, 누락되면 조용히 뚫린다.
2026-08-24 하루에만 읽기/쓰기 분리 누락을 세 곳에서 발견했다(상위 3계층·어서션 junction·
risk-categories 읽기). 사람의 기억에 의존하는 격리는 이 프로젝트의 실적상 신뢰할 수 없다.

회귀 방지 원칙 1번(판별은 구조/타입으로) 부합.

### 2.4 산업별 템플릿은 별도 계층으로 두되 이번 범위에서 제외한다

산업별 표준 RCM은 **템플릿**으로 제공하고, 온보딩 시점에 고객사 baseline으로 **복사**한다.
복사 이후 각 회사가 독립적으로 관리하므로 다른 회사에 영향이 없다.

이번에 구현하지 않는다. 두 번째 고객사가 없는 상태에서는 검증할 대상이 없고,
`tenant_id` 전환과 템플릿 설계를 한 커밋에 섞으면 원인 분리가 되지 않는다.
별도 ADR로 다룬다.

### 2.5 기존 93건은 사이냅소프트 테넌트에 귀속시킨다

현재 `tenants` 1건, `user_tenant_access` 2건. 귀속 대상이 명확하다.

**실데이터 이관이므로 마스터가 직접 실행한다.** Claude Code는 마이그레이션 스크립트를
작성하되 운영 실행은 하지 않는다.

## 3. 영향 범위

| 대상 | 변경 |
|---|---|
| 스키마 | `baseline_*` 5테이블에 `tenant_id` 추가(NOT NULL) |
| 인덱스 | code 유니크 4개를 `(tenant_id, code)`로 전환 |
| 제약 | baseline 5테이블에 `(id, tenant_id)` 유니크 추가 |
| 제약 | instance→baseline FK 8개를 복합 FK로 전환 |
| 제약 | `baseline_control_assertions` 유니크에 `tenant_id` 포함 |
| `control_resolver.py` | baseline 조회에 tenant 필터 추가 |
| `seed_baseline.py` | 대상 테넌트 지정 필요 |
| 마이그레이션 | alembic. 기존 93건 tenant 귀속 포함 |

`baseline_risk_categories`와 이를 참조하는 FK는 변경하지 않는다.

## 4. 검증 조건

1. 마이그레이션 후 운영 baseline 건수가 8/29/85/93/469로 불변
2. 모든 baseline 행의 `tenant_id`가 사이냅소프트 테넌트를 가리킴
3. 두 번째 테넌트를 생성하고 동일 code(`EL-010-10-10` 등)로 baseline 삽입 → **성공**
   (현재 구조에서는 실패하는 케이스)
4. A테넌트 instance가 B테넌트 baseline을 참조하도록 삽입 시도 → **DB가 거부**
5. 기존 resolver 조회가 자기 테넌트 데이터만 반환
6. 전체 pytest 통과

**3번과 4번이 이 ADR의 핵심 검증이다.**
3번은 §2.2가, 4번은 §2.3이 실제로 구현됐는지 본다.
4번이 없으면 복합 FK 없이 단순 FK로도 통과해버린다.

## 5. 위험과 대응

**되돌리기 어려운 작업이다.** 스키마 변경 + 실데이터 이관이 함께 간다.

- 마이그레이션 실행 전 백업 필수 — `/opt/icfr/scripts/backup_db.sh` 수동 1회
- 복구 경로가 검증되어 있음(2026-08-19 리허설 통과)
- 로컬 검증 후 운영 적용. **"로컬 통과는 검증이 아니다"** — 로컬은 sqlite,
  운영은 postgres이며 복합 FK 동작이 다를 수 있다. 운영 적용 후 §4 재확인

## 6. 미해결

- 산업별 템플릿 계층 설계 (§2.4)
- 템플릿 → 고객사 baseline 복사 시점의 버전 관리
  (템플릿이 개정되면 이미 복사된 고객사는 어떻게 되는가)
- 코드마스터 테이블화와의 관계 — 코드 체계가 테넌트별이면 마스터도 테넌트별인가
