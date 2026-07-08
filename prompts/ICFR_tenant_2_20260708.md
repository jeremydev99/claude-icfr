# PROMPT: (tenant_id, code) 복합 unique 전환

## 목표
멀티테넌시 1단계 후속. 6개 테이블의 글로벌 unique(code)를 `(tenant_id, code)` 복합 unique로 전환한다.
2번째 tenant 진입 전 필수 작업(ADR-0026). **users.email은 대상 아님** — ADR-0025에 따라 전역 계정(1 user = 여러 tenant)이므로 email 글로벌 unique 유지.

## 전제 (실측 완료)
- 대상 6개 테이블 전부 tenant_id NULL 없음 (백필 불필요).
- 현재 글로벌 unique 인덱스: `ix_controls_code`, `ix_deficiencies_code`, `ix_processes_code`, `ix_risk_categories_code`, `ix_risks_code`, `ix_sub_processes_code`
- 스택: FastAPI + SQLAlchemy + Alembic.

## 대상 테이블 (6개)
controls, deficiencies, processes, risk_categories, risks, sub_processes

---

## 작업 1 — 모델 수정 (`backend/app/models/`)
각 대상 모델 파일에서:
1. `code` 컬럼의 `unique=True` 제거 (index는 아래에서 재정의하니 컬럼 레벨 unique만 제거).
2. `__table_args__`에 복합 unique 제약 추가:
   ```python
   __table_args__ = (
       UniqueConstraint("tenant_id", "code", name="uq_<table>_tenant_code"),
       Index("ix_<table>_code", "code"),  # code 단독 non-unique (조회 성능 유지)
   )
   ```
   - 기존에 `__table_args__`가 있으면 병합. `UniqueConstraint`, `Index` import 확인.
   - `<table>`은 실제 테이블명으로 치환.

**주의:** 모델과 마이그레이션이 어긋나면 다음 autogenerate 때 diff가 터진다. 모델 6개 전부 반드시 수정.

## 작업 2 — Alembic 마이그레이션 1개 작성
`alembic revision -m "tenant_code composite unique"` 로 생성 후 수동 작성 (autogenerate 신뢰하지 말고 직접 작성).

**upgrade()** — 6개 테이블 각각:
1. `op.drop_index("ix_<table>_code", table_name="<table>")`  # 기존 글로벌 unique 제거
2. `op.create_unique_constraint("uq_<table>_tenant_code", "<table>", ["tenant_id", "code"])`
3. `op.create_index("ix_<table>_code", "<table>", ["code"], unique=False)`  # code 단독 non-unique 재생성

**downgrade()** — 정확히 역순:
1. `op.drop_index("ix_<table>_code", table_name="<table>")`
2. `op.drop_constraint("uq_<table>_tenant_code", "<table>", type_="unique")`
3. `op.create_index("ix_<table>_code", "<table>", ["code"], unique=True)`

**down 위험 명시(주석으로):** 2번째 tenant 데이터가 이미 들어와 code가 tenant 간 중복된 상태에서는 downgrade의 글로벌 unique 재생성이 실패한다. 이는 의도된 동작(정직한 down). 롤백이 필요하면 중복 데이터 정리가 선행돼야 함.

## 작업 3 — 로컬 반영 & 검증
```bash
docker compose exec -T backend alembic upgrade head
```
반영 후 인덱스 재조회로 6개 테이블이 `(tenant_id, code)` 복합 unique로 바뀌었는지 확인:
```bash
docker compose exec -T postgres psql -U postgres -d postgres -c "SELECT t.relname AS table, i.relname AS index, ix.indisunique FROM pg_index ix JOIN pg_class t ON t.oid=ix.indrelid JOIN pg_class i ON i.oid=ix.indexrelid WHERE t.relname IN ('controls','deficiencies','processes','risk_categories','risks','sub_processes') ORDER BY t.relname, i.relname;"
```
기대: 각 테이블에 `uq_<table>_tenant_code`(unique=t) + `ix_<table>_code`(unique=f) 존재.

## 작업 4 — 회귀 확인
- `curl -s http://localhost:8000/api/health/` OK
- FE(localhost:5173) 목록 화면(RCM/Test/증빙) 데이터 정상 노출 재확인.

## 작업 5 — ADR-0026 기록
- 6개 테이블 (tenant_id, code) 복합 unique 전환 완료 기록.
- users.email 제외 사유 명시: ADR-0025(전역 계정, 1 user = 여러 tenant).

---

## 제약
- **DB 스키마 변경이므로 push는 자동 금지.** 커밋까지만 하고 사용자 push 대기.
- 추정 금지 — 모델 파일 실제 구조 확인 후 수정.
- 6개 테이블 외 다른 테이블 건드리지 말 것.
