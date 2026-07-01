# ICFR 멀티테넌시 1단계 — tenant_id 전면 도입 + 자동 격리 명세

- **작성일**: 2026-06-15
- **근거**: ADR-0025 (baseline+overlay+멀티테넌시)
- **Tier**: Tier 2 (전 테이블 스키마 변경 + 마이그레이션 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화 — 단, **자동 tenant 격리는 명시적 예외**(데이터 누출 방지가 우선)
- **데이터 주의**: 현재 controls 95건 + evidence_files 3건 실존. **절대 손실 금지** (ADR-0023). 마이그레이션 전후 count 검증 필수.

---

## 0. 목표

모든 데이터에 회사(tenant) 맥락을 도입한다. SaaS(공유 DB 다중 tenant)와 온프레(전용 DB 단일 tenant)를 **단일 코드베이스**로 대응 — 온프레는 "tenant 1개짜리 SaaS"다. 회사 간 데이터 누출은 자동 격리로 원천 차단한다.

**확정 설계**:
- TenantMixin → AuditedBase에 추가 → 전 테이블 tenant_id 일괄
- Tenant(회사) 모델 + UserTenantAccess(user↔tenant 다대다) 신규
- User는 tenant 독립 — 접근은 UserTenantAccess가 유일한 진실 원천 (한 계정 다중 회사)
- 자동 격리: `X-Tenant-Id` 헤더 + 접근권한 검증 + 쿼리 자동 필터

---

## 1. 모델 계층

### 1-1. Tenant 모델 (신규)
회사 = tenant. `AuditedBase`가 아니라 **TenantMixin을 제외한 base**를 상속(자기 자신에 tenant_id 금지 — 순환). 필드: `id`, `name`(회사명), `code`(고유 식별), `is_active`. 필요한 감사 컬럼(created_at 등)은 mixin으로 조합.

### 1-2. TenantMixin (신규) → AuditedBase에 추가
```python
class TenantMixin:
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
```
`AuditedBase`에 TenantMixin 추가 → RCM·Test·Remediation·Evidence 전 모델에 tenant_id 자동 적용.

**예외 처리 (중요)**: `Tenant`, `User`, `UserTenantAccess`는 이 일괄 적용 대상에서 제외하거나 다르게 처리한다. **작업 전 `models/user.py`의 User base 구조를 확인**하고, User가 AuditedBase를 상속한다면 TenantMixin이 강제되지 않도록 조정할 것.

### 1-3. UserTenantAccess (신규)
user ↔ tenant 다대다 매핑 + 역할. 필드: `user_id`(FK users), `tenant_id`(FK tenants), `role`(해당 tenant에서의 역할). 한 user가 여러 tenant 접근 = 매핑 다수. 온프레는 모든 user가 단일 tenant에 매핑.

### 1-4. User 모델
User는 tenant 독립(전역 계정). **User에 tenant_id를 넣지 않는다.** 접근 권한은 UserTenantAccess로만 판단. (UserRole이 tenant별이어야 하는지는 확인 후 결정 — tenant별 역할이면 UserTenantAccess.role로 흡수)

---

## 2. 마이그레이션 (단계적, 데이터 보존)

**controls 95 + evidence 3 보존이 최우선.** 순서 엄수:

1. `tenants` 테이블 생성
2. `user_tenant_access` 테이블 생성
3. **기본 tenant 1행 삽입** — 고정 UUID, name="사이냅소프트"(또는 적절값), code 지정. 기존 데이터 귀속 대상.
4. 전 데이터 테이블에 `tenant_id` 컬럼 **nullable로 먼저** 추가
5. **기존 행 UPDATE** — 모든 기존 데이터(controls 95, evidence 3, 기타)의 tenant_id를 기본 tenant로 채움
6. `tenant_id` **NOT NULL + FK + index 확정**
7. 기존 users를 기본 tenant에 UserTenantAccess로 매핑 (각 user의 기존 role 이관)

**검증**: 마이그레이션 후 `SELECT count(*) FROM controls` = 95, `evidence_files` = 3 확인. 단계 4→6을 한 번에 NOT NULL로 넣으면 기존 행 때문에 실패하므로 반드시 분리.

`alembic upgrade head` → `alembic downgrade` 왕복으로 롤백 안전성도 확인.

---

## 3. 자동 격리 (핵심 안전장치 — ADR-0020 예외)

### 3-1. 활성 tenant 확보
요청 헤더 `X-Tenant-Id`로 현재 작업 대상 tenant 지정. 인증된 user가 그 tenant에 UserTenantAccess가 있는지 검증, 없으면 403.

### 3-2. CurrentContext 의존성 (신규)
기존 `CurrentUser`를 확장한 `CurrentContext`(user + 검증된 tenant_id)를 만들어 **전 엔드포인트가 사용**. `get_current_user` 흐름에 tenant 검증을 더한다.

### 3-3. 쿼리 자동 필터 (수동 필터 금지)
**각 쿼리에 `.filter(tenant_id == ...)`를 수동으로 거는 방식은 금지** — 한 곳만 빠뜨려도 데이터 누출. SQLAlchemy `with_loader_criteria` 또는 세션 레벨 필터로 tenant_id를 **자동 주입**한다. 현재 `get_db` 세션 관리 구조를 확인하고, 세션에 활성 tenant_id를 바인딩해 전역 자동 필터를 건다.

JWT에는 tenant를 담지 않는다(헤더 방식). 회사 전환은 헤더 변경만으로 가능, 온프레는 단일 tenant라 항상 같은 값으로 수렴.

---

## 4. 엑셀 업로드·seed tenant-aware

- **엑셀 업로드** (93통제 실제 입력 경로): 업로드된 통제가 **현재 활성 tenant로** 들어가도록 수정.
- **seed** (`seeds/rcm.py` 등): 샘플 데이터도 기본 tenant 귀속. seed의 login 흐름에 tenant 헤더 추가.

---

## 5. 완료 기준

- [ ] Tenant·UserTenantAccess 모델 + TenantMixin
- [ ] AuditedBase 일괄 적용, User/Tenant/매핑 예외 처리 정확
- [ ] 마이그레이션 후 controls=95, evidence=3 보존 확인
- [ ] downgrade 왕복 안전
- [ ] CurrentContext 의존성 + X-Tenant-Id 검증(권한 없으면 403)
- [ ] 쿼리 자동 tenant 필터 (수동 필터 없음)
- [ ] **격리 테스트**: tenant A로 B 데이터 조회 시 안 보임
- [ ] 회귀 테스트: 기존 기능(RCM·Test·Remediation·Evidence) 정상
- [ ] 엑셀 업로드·seed가 활성 tenant로 적재

완료 후 `docker compose up -d --build backend` 재빌드. **마이그레이션 직후 controls count=95 직접 확인**(데이터 손실 차단). config.py admin_password는 건드리지 말 것.

---

## 작업 전 확인 (Claude Code가 먼저 수행)

- `models/user.py` — User base 구조 (AuditedBase 상속 여부 → TenantMixin 예외 처리 방식 결정)
- `core/database.py` `get_db` — 세션 관리 구조 (자동 필터 주입 지점)
- `core/deps.py` — get_current_user 흐름 (CurrentContext 확장 지점)

---

ICFR_tenant_1_20260615.md 진행해줘
