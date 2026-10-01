# ADR-0036: 감사 컬럼 자동 기록 — 행위자 컨텍스트와 fail-closed

- 상태: 채택
- 작성일: 2026-09-22
- 관련: ADR-0025(멀티테넌시 자동 격리), ADR-0031(역할·권한), `ClaudeICFR.md` 13.9-51
- 프롬프트: `prompts/ICFR_backend_13-9-51_20260922.md`
- ADR-0035 는 매뉴얼 패널 예약 번호라 건너뛴다.

---

## 1. 배경

`created_by`·`updated_by`·`deleted_by`(`TimestampMixin`·`SoftDeleteMixin`)는 매핑 52개 테이블
전부에 있었지만 **채우는 코드가 없었다**(로컬 실측 채워진 값 0건). `tenant_id` 는 ADR-0025 로
자동화했지만 "누가"는 자동화 대상이 아니었고, 필요한 곳은 도메인 컬럼(`uploaded_by_id` 등)이나
핸들러 수동 대입(13.9-48 `evidence_links`)으로 메워 왔다. 한 곳만 빠뜨려도 흔적이 비는
수동 대입은 ADR-0025 가 tenant 에서 금지한 방식과 같은 구조다.

## 2. 결정

### 2.1 값 형식
- 사용자: `str(user.id)`. 이메일·이름은 쓰지 않고 화면 표시는 조회 시 변환한다. users FK 없음.
- 시스템: `system:<출처>`, 형식 `^system:[a-z][a-z0-9-]*$`. **명시해야만** 기록된다.

| 출처 | 경로 |
|---|---|
| `system:bootstrap` | `app/seeds/bootstrap.py` `bootstrap_admin` (앱 기동 lifespan) |
| `system:seed-users` | `app/seeds/users.py` 직접 삽입 2곳 |
| `system:seed-baseline` | `seeds/seed_baseline.py` `seed` |
| `system:seed-euc-iuc` | `seeds/seed_euc_iuc.py` `seed` |
| `system:seed-scoping-template` | `seeds/seed_scoping_template.py` `main` |
| `system:migration-rcm-baseline` | `scripts/migrate_rcm_to_baseline.py` `migrate` (역할 종료, 저장소에 남아 있음) |
| `system:test` | 테스트 직접 삽입 세션 전용 (§2.4) |

HTTP API 로 도는 시드(`app/seeds/run_all.py` rcm·test·remediation·evidence)는 로그인한 admin 의 id 가 기록된다 — 사실과 같다.

### 2.2 구조 (`backend/app/core/audit_context.py`)
- 행위자 ContextVar `_current_actor`. `get_current_user`(async)가 tenant 와 같은 자리에서 설정한다 —
  이벤트 루프 컨텍스트라 동기 엔드포인트(threadpool)로 복사·전파된다(ADR-0025 와 같은 전제).
- `system_actor("system:<출처>")` 컨텍스트 매니저. 데코레이터로도 쓴다. 블록을 벗어나면 원래 값으로 돌아간다.
- tenant 리스너와 **별도 모듈·별도 리스너**. 두 리스너는 서로 다른 컬럼만 건드려 실행 순서가 결과에 영향을 주지 않는다.
- 대상 판별은 믹스인(`TimestampMixin`·`SoftDeleteMixin`) — 테이블명 매칭 금지. IdentityBase 7개(users·tenants·user_tenant_access·템플릿 3·baseline_risk_categories)도 포함한다.

### 2.3 기록 규칙 (before_flush)
| 시점 | 기록 |
|---|---|
| insert | `created_by`(이미 값이 있으면 유지)·`updated_by` = 행위자 |
| update(실제 변경된 dirty) | `updated_by` = 행위자, `created_by` 불변 |
| `is_deleted` false→true | `deleted_by` = 행위자, `deleted_at` = 현재 시각 |
| `is_deleted` true→false(복구) | `deleted_by`·`deleted_at` 비움 |

- **fail-closed**: 대상 객체의 insert·update·hard delete 가 있는데 행위자가 없으면 `MissingActorError` 가 나고 flush 는 실패한다. `unknown` 같은 기본값은 두지 않는다.
- 기존 NULL 행은 backfill 하지 않는다. 모르는 과거를 지어내지 않는다.
- `deleted_at` 수동 대입(`api/evidence.py` 링크 삭제)은 제거했다. `evidence_files.deleted_at_ts` 는 도메인 삭제 이력 컬럼(`deleted_by_id` FK·사유와 한 묶음)이라 유지한다.

### 2.4 session.info 행위자는 테스트 전용 경로
- `session.info["system_actor"]` 는 **테스트 직접 삽입 세션(`tests/conftest.py` `TestingSessionLocal`)에만** 붙인다.
- 이유: 테스트 스레드의 ContextVar 는 TestClient 요청 안으로 **전파된다**(실측). ContextVar 로 `system:test` 를 걸면 API 경로에서 행위자가 빠져도 테스트가 통과한다.
- API 요청 세션(`ApiSessionLocal`)과 운영 `SessionLocal` 에는 붙이지 않는다. 테스트로 고정했다(`test_production_and_api_sessions_carry_no_info_actor`).

### 2.5 bulk DML 차단과 한계
- `do_orm_execute` 에서 감사 대상 테이블의 bulk UPDATE/DELETE(`query.update()`·`update(Model)`·Session 으로 실행하는 Core `update(table)`)를 `AuditBypassError` 로 막는다. 도입 시점 사용처는 0건이었다.
- **한계**: `text()` raw SQL(예: `seed_baseline --reset` 의 `DELETE FROM`)과 alembic `op.*` 는 대상 테이블을 알 수 없어 막지 못하고 기록도 하지 않는다. 마이그레이션은 ORM Session 을 쓰지 않는다(도입 시점 0건). 이 경로로 쓴 행의 감사 컬럼은 NULL 로 남는다.

## 3. 결과
- 스키마 변경 없음(`String(255)` nullable 그대로).
- 도메인 "누가" 컬럼(`uploaded_by_id`·`confirmed_by_id`·`actor_id` 등)은 그대로 둔다. 감사 컬럼은 마지막 수정자를 덮어쓰므로 판단 기록을 대신하지 못한다.
- 테스트: `tests/test_audit_columns.py`.
