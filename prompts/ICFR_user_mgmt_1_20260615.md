# ICFR 사용자 모듈 + 감사 일관화 통합 명세

- **작성일**: 2026-06-15
- **대상**: `api/user_mgmt.py`, `api/auth.py`, `api/remediation.py`, `schemas/user.py`, `schemas/remediation.py`, `seeds/bootstrap.py`
- **Tier**: Tier 2 (신규 기능 + 응답 계약 변경 + seed → 마스터 push)
- **원칙**: ADR-0020 제로 추상화 (서비스 클래스·패턴 금지, 직접 함수·명시적 if)
- **배경**: Regina 백엔드 요청 4건 — 본질 해결 기준 (땜질·프론트 우회 금지)

> **공통 주의**: `config.py`의 `admin_password`는 **절대 건드리지 말 것** (현재 `admin123`, 과거 무단 변경 사고 있었음). 이 명세는 그 줄과 무관하다.

---

## 섹션 1. deficiency 삭제 FK 가드 (409)

**문제**: `DELETE /deficiencies/{id}`가 soft delete라 FK 제약이 작동하지 않아, 연결된 활성 RemediationPlan이 있어도 삭제된다.

**해결**: delete 핸들러에서 삭제 전, 이 deficiency를 참조하는 **활성(`is_deleted == False`) RemediationPlan** 존재 여부를 확인하고 있으면 409 반환.

```python
active_plans = db.query(RemediationPlan).filter(
    RemediationPlan.deficiency_id == deficiency_id,   # 실제 FK 필드명 모델에서 확인
    RemediationPlan.is_deleted == False,
).count()
if active_plans > 0:
    raise HTTPException(status_code=409, detail="연결된 개선계획이 있어 삭제할 수 없습니다")
```

> RemediationPlan이 deficiency를 참조하는 FK 필드명은 `models/remediation.py`에서 확인 후 적용.

---

## 섹션 2. 사용자 CRUD (create / update / delete)

현재 `user_mgmt.py`에 User는 list/get만 있음. **같은 파일의 UserRole CRUD 패턴을 그대로 따라** create/update/delete 추가.

- **POST `/`** (create): body `email`, `display_name`(=실명), `password`, `role`
  - email 중복(활성) 시 409
  - `hash_password(password)`로 저장 (`app.core.security`)
  - 201 + UserRead
- **PATCH `/{user_id}`** (update): `display_name`, `role` 등 수정. **password·email은 이 엔드포인트에서 변경하지 않음** (password는 섹션 3, email은 식별자라 변경 정책 별도)
- **DELETE `/{user_id}`** (soft delete): `is_deleted = True`. 본인 계정·마지막 관리자 삭제 방지 가드 권장

**권한**: 사용자 CRUD는 관리자 전용. 기존 role 권한 체크 패턴을 `core/deps.py`에서 확인하고, 없으면 `user.role`이 관리자인지 검사하는 의존성 추가. (감사 대상 시스템이므로 권한 가드 필수)

---

## 섹션 3. 비밀번호 변경 API

현재 엔드포인트 없음 (info에만 존재). 두 경로로 분리:

- **본인 변경** — `POST /api/auth/change-password` (auth.py): body `old_password`, `new_password`
  - `verify_password(old, current_user.hashed_password)` 실패 시 400/401
  - 통과 시 `hash_password(new)` 저장
- **관리자 리셋** — `POST /{user_id}/reset-password` (user_mgmt.py, 관리자 전용): body `new_password`
  - old 검증 없이 재설정 (관리자 권한 가드 필수)

비밀번호 정책(최소 길이 등) 검증은 schema에서 처리.

---

## 섹션 4. 실명 감사 표시 — 본질 해결

**기준**: 감사로그에 사용자 실명이 정확히 표시되어야 함. 단, 이력에 실명을 **박제하지 않고** user_id(불변 FK) 저장 + 표시 시 join (이미 올바르게 구현됨 — `changed_by_id` 저장 방식 유지).

### 4-1. display_name = 실명 용도 확정
`display_name`(String(100), nullable=False)을 실명 필드로 용도 확정. 구조 변경 없음. 사용자 생성/수정(섹션 2)에서 실명을 입력받는다.

### 4-2. seed 직책성 값 교정
`seeds/bootstrap.py`의 관리자 `display_name`이 직책명("System Administrator")으로 차 있음. 실명 표기 목적에 맞게 교정.
- `config.py`의 `admin_display_name` 기본값을 실명 형식으로 변경 (운영 시 실제 관리자 실명으로 설정하는 값). **`admin_password`는 절대 건드리지 말 것.**
- 기존 DB의 admin display_name이 직책값이면, 운영자가 사용자 수정 API로 실명 갱신 가능 (마이그레이션 불필요).

### 4-3. remediation history 실명 join — test_module과 일관화 (핵심)
**불일치 발견**: `test_module`의 `TestStatusHistoryRead`는 `changed_by: UserBrief(id + display_name)`를 join해 실명을 내려주는데, `remediation`의 `RemediationStatusHistoryRead`는 `changed_by_id: UUID`만 있어 실명이 없다. → Regina가 이 때문에 프론트에서 UUID→이름을 우회 처리함.

**본질 해결**: remediation history를 test_module 패턴으로 통일.
- `UserBrief`(id + display_name)를 공통 위치(`schemas/user.py`)로 두고 양쪽에서 import (현재 test_module 로컬 정의 → 공통화). UserBrief는 단순 데이터 스키마이므로 공통화는 추상화 위반 아님.
- `RemediationStatusHistoryRead`에 `changed_by: UserBrief` 추가 (`changed_by_id`는 하위호환으로 유지 — test_module과 동일 형태).
- remediation history 핸들러에서 `changed_by_id` → User join하여 display_name 포함. **test_module의 history 핸들러 join 방식을 그대로 참고**할 것.
- 결과: 프론트의 UUID→이름 우회 제거 가능. Regina에 "remediation history도 changed_by 실명 내려가니 프론트 우회 제거" 전달.

---

## 완료 기준

- [ ] deficiency 삭제 시 활성 RemediationPlan 있으면 409
- [ ] 사용자 create/update/delete + 관리자 권한 가드
- [ ] 본인 비번 변경(old 검증) + 관리자 리셋 엔드포인트
- [ ] display_name 실명 용도 확정 + seed 직책값 교정 (admin_password 불변 확인)
- [ ] remediation history에 `changed_by: UserBrief` join (test_module과 동일 구조)
- [ ] UserBrief 공통화, 양쪽 import
- [ ] 테스트: 409 가드, 사용자 CRUD, 비번 변경, history 실명 응답
- [ ] 재빌드 후 Swagger 검증

완료 후 `docker compose up -d --build backend` 재빌드. **config 변경 시 `git diff backend/app/config.py`로 admin_password가 admin123 그대로인지 반드시 확인** (명세 외 변경 차단).

---

ICFR_user_mgmt_1_20260615.md 진행해줘
