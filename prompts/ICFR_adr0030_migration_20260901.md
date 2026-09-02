# ADR-0030 구현: baseline 테넌트 소유권 전환 + 격리 복합 FK

작성일: 2026-09-01
근거 ADR: ADR-0030(baseline 테넌트 소유권), ADR-0029, ADR-0020
관련: ClaudeICFR.md 13.9-16(차단 항목)

---

## 0. 이 작업의 위험도

**지금까지 한 작업 중 가장 위험하다.** 스키마 변경과 실데이터 이관이 함께 간다.

- 되돌리기가 어렵다. alembic downgrade가 있어도 데이터 손실 없이 되돌아간다는 보장은 별도 검증이 필요하다
- 실패 시 운영 서비스가 멈출 수 있다
- **로컬은 sqlite, 운영은 postgres다.** 복합 FK 동작이 다를 수 있으므로 로컬 통과를 검증으로 인정하지 않는다

**진행 순서를 반드시 지킬 것: 로컬 전체 검증 → 운영 백업 수동 실행 → 운영 적용 → 검증.**
중간 단계를 건너뛰지 않는다.

## 1. 범위

**포함**
- `baseline_*` 5테이블에 `tenant_id` 추가 (ADR-0030 §2.1)
- code 유니크 4개를 `(tenant_id, code)`로 전환 (§2.2)
- instance→baseline FK 8개를 복합 FK로 전환 (§2.3)
- `baseline_control_assertions` 유니크에 `tenant_id` 포함
- 기존 93건을 사이냅소프트 테넌트에 귀속 (§2.5)
- `control_resolver.py` baseline 조회에 tenant 필터
- `seed_baseline.py` 대상 테넌트 지정

**제외**
- 산업별 템플릿 계층 (§2.4) — 별도 ADR
- `baseline_risk_categories` 및 이를 참조하는 FK — **전역 유지, 변경 금지**
- 13.9-10-b (upload-excel 쓰기 전환) — 본 작업 완료 후 별건

## 2. 사전 실측 (STEP 0)

**스키마를 추정해 마이그레이션을 쓰지 않는다.**

```bash
# 2-1. 로컬 DB 종류와 alembic 현재 리비전
cd backend && alembic current
grep -n "sqlalchemy.url\|DATABASE_URL" alembic.ini app/core/config.py | head

# 2-2. baseline 5테이블 모델 정의 위치와 Base 클래스
grep -n "class Baseline" app/models/rcm_baseline.py

# 2-3. IdentityBase / AuditedBase 정의 — tenant_id가 어디서 오는지
grep -n -A15 "class IdentityBase\|class AuditedBase" app/models/*.py

# 2-4. resolver의 baseline 조회 지점
grep -n "Baseline" app/services/control_resolver.py | head -30
```

**보고할 것**
- `AuditedBase`가 `tenant_id`를 어떻게 주입/필터하는지 (자동 stamp인지 수동인지)
- baseline 5테이블을 `IdentityBase` → `AuditedBase`로 바꾸면 되는지,
  아니면 `tenant_id`만 별도 추가해야 하는지 — **근거와 함께 판단**
- resolver에서 tenant 필터가 필요한 지점 목록

**주의** — `AuditedBase`에는 `is_deleted`, `row_version`, 감사 컬럼이 딸려 있다.
baseline에 이것들이 필요한지는 별개 판단이다. 자동으로 따라붙는 것을 확인 없이 수용하지 말 것.

## 3. 마이그레이션 설계

### 3.1 순서

alembic 단일 리비전으로 작성하되, 내부 순서를 지킬 것.

1. `tenant_id` 컬럼 추가 (nullable로 먼저)
2. 기존 행에 사이냅소프트 테넌트 id 채우기
3. `NOT NULL` 제약 적용
4. 기존 code 유니크 인덱스 4개 삭제
5. `(tenant_id, code)` 유니크 인덱스 4개 생성
6. baseline 5테이블에 `(id, tenant_id)` 유니크 추가
7. instance→baseline FK 8개 삭제
8. 복합 FK 8개 생성
9. `baseline_control_assertions` 유니크 재생성 (tenant_id 포함)

**2번에서 테넌트 id를 하드코딩하지 말 것.** `tenants` 테이블에서 조회한다.
테넌트가 정확히 1건이 아니면 마이그레이션을 중단시킬 것 — 그 경우 수동 판단이 필요하다.

### 3.2 downgrade

작성할 것. **다만 downgrade가 데이터 손실 없이 동작하는지 로컬에서 실제로 검증할 것.**
검증 안 된 downgrade는 없는 것과 같다. 동작하지 않으면 그 사실을 보고할 것.

### 3.3 복합 FK 대상 8개

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

**주의** — 이 컬럼들은 NULL 허용이다(`action='add'`인 경우 NULL).
복합 FK에서 한쪽이 NULL이면 제약이 적용되지 않는다(MATCH SIMPLE 기본 동작).
`tenant_id`는 NOT NULL이고 `baseline_*_id`가 NULL인 조합이 발생하므로,
**이 동작이 의도한 것인지 확인하고 ADR에 기록할 것.**

## 4. 코드 변경

- `control_resolver.py` — baseline 조회 전부에 tenant 필터. **누락 시 다른 회사 데이터가 보인다**
- `seed_baseline.py` — 대상 테넌트를 인자로 받도록. 하드코딩 금지
- ADR-0020 준수. 클래스·패턴 금지

## 5. 로컬 검증 (ADR-0030 §4)

**운영에 올리기 전 전부 통과해야 한다.**

1. 마이그레이션 후 baseline 건수 8/29/85/93/469 불변
2. 모든 baseline 행의 `tenant_id`가 단일 테넌트를 가리킴
3. **두 번째 테넌트 생성 후 동일 code로 baseline 삽입 → 성공**
   (현재 구조에서는 실패하는 케이스. §2.2 검증)
4. **A테넌트 instance가 B테넌트 baseline을 참조하도록 삽입 → DB가 거부**
   (§2.3 검증. 이것이 없으면 단순 FK로도 통과한다)
5. 기존 resolver 조회가 자기 테넌트 데이터만 반환
6. 전체 pytest 통과, xfail 1건 유지
7. downgrade 실행 → 데이터 손실 없이 복원되는지 확인

**3번과 4번을 테스트로 작성할 것.** 수동 확인으로 끝내지 않는다.

**4번 주의** — sqlite는 기본적으로 FK를 강제하지 않는다(`PRAGMA foreign_keys`).
로컬에서 4번이 통과해도 그것이 postgres 동작을 보장하지 않는다.
로컬 테스트 환경의 FK 강제 여부를 확인하고 보고할 것. 강제되지 않으면 그 사실을 명시할 것 —
**그 경우 4번의 실질 검증은 운영에서만 가능하다.**

## 6. 운영 적용 절차

**로컬 검증 §5가 전부 통과한 뒤에만 진행한다. 마스터가 직접 실행한다.**

### 6.1 백업 (필수)

```bash
/opt/icfr/scripts/backup_db.sh; echo "exit=$?"
cat /data/backup/LAST_RESULT
```

`exit=0`과 `OK`를 확인하기 전에는 다음 단계로 넘어가지 않는다.
자동 백업은 03:00이므로 지금 실행하지 않으면 최대 하루치를 잃는다.

### 6.2 적용 전 상태 기록

```bash
docker exec icfr-postgres psql -U icfr -d icfr_db -t -A -F'|' -c "
SELECT 'processes', count(*) FROM baseline_processes
UNION ALL SELECT 'sub_processes', count(*) FROM baseline_sub_processes
UNION ALL SELECT 'risks', count(*) FROM baseline_risks
UNION ALL SELECT 'controls', count(*) FROM baseline_controls
UNION ALL SELECT 'assertions', count(*) FROM baseline_control_assertions
UNION ALL SELECT 'tenants', count(*) FROM tenants;"
```

**tenants가 1이 아니면 중단하고 보고할 것.**

### 6.3 마이그레이션 실행

배포로 코드가 올라간 뒤, 컨테이너 안에서 alembic 실행.
정확한 명령은 Claude Code가 `docs/DEPLOY.md`와 기존 배포 절차를 확인해 제시할 것.
**추정한 명령을 운영에 실행하지 않는다.**

### 6.4 적용 후 검증

- §6.2와 동일 쿼리로 건수 불변 확인
- 모든 baseline 행의 tenant_id 채워짐 확인
- **§5-4번(교차 테넌트 참조 거부)을 postgres에서 실제 확인** —
  임시 테넌트를 만들어 잘못된 참조를 시도하고 거부되는지 본다. 확인 후 임시 데이터 정리
- 브라우저에서 RCM 화면 정상 표시 (통제 93, 프로세스 필터 동작)

### 6.5 실패 시

- alembic downgrade 시도
- downgrade가 실패하면 **백업에서 복구**. `/opt/icfr/scripts/restore_db.sh`
  (비밀키는 마스터 보관분 사용, 사용 후 `shred -u`)
- 복구는 임시 DB가 아니라 운영 DB 대상이 되므로, 이 경우 마스터 판단 후 실행

## 7. 커밋 분리

1. `feat(db): baseline 5테이블 tenant_id 추가 + 격리 복합 FK (ADR-0030)`
   — 모델 + alembic 리비전
2. `feat(rcm): baseline 조회 tenant 필터 적용`
   — resolver + seed_baseline
3. `test(rcm): 테넌트 격리 검증 케이스 추가`
   — §5-3, §5-4

## 8. 완료 보고

1. STEP 0 실측 결과 (AuditedBase 판단 근거 포함)
2. 커밋 3건 해시와 변경 파일
3. §5 검증 7개 결과 — **4번은 로컬 FK 강제 여부와 함께 보고**
4. downgrade 검증 결과
5. `ruff` / `pytest` 결과
6. 복합 FK와 NULL 조합에 대한 판단 (§3.3)
7. 운영 적용 명령 (§6.3) — 확인한 근거와 함께

## 9. push 정책

**로컬 커밋까지. push 대기.**
push 전 `git log origin/main..HEAD`로 대기 커밋을 확인하고 보고할 것 (CLAUDE.md §8.3).
운영 적용은 마스터가 백업 후 직접 진행한다.
