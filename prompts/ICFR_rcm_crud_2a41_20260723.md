# ICFR 2-A-4-1 — Control CRUD 단건 baseline/overlay 전환 명세

- **작성일**: 2026-07-23
- **근거**: ADR-0027, 2-A-3(조회 전환) 후속
- **Tier**: Tier 2 (**쓰기 경로 변경 — 회사의 결정이 처음 데이터로 기록되는 단계**)
- **원칙**: ADR-0020 제로 추상화 — 명시적 if 분기, 서비스 클래스·패턴 금지. 모든 회사 유연 적용, 고정 코딩 0.

---

## 0. 성격과 목표

2-A-3로 **읽기**는 baseline/overlay를 보는데 **쓰기**는 여전히 legacy `controls` 테이블로 간다. 이 분리 때문에 지금 통제를 추가하면 목록에 나타나지 않는다(테스트 7건 xfail의 원인).

본 단계는 쓰기를 baseline/overlay로 전환해 **회사의 결정(adopt/exclude/override/add)이 처음으로 데이터에 기록**되게 한다. 완료 시 write→read 왕복이 복구되어 **xfail 7건이 자동으로 xpass** 된다(strict 마킹이므로 실패로 떠서 마킹 제거 신호가 됨 — 반드시 제거할 것).

---

## 1. 범위

### 전환 대상 (이번 단계)
- `POST /controls` (rcm.py:382 create_control)
- `PATCH /controls/{control_id}` (rcm.py:404 update_control)
- `DELETE /controls/{control_id}` (rcm.py:416 delete_control)

### 전환하지 않는 것 (후속)
- `bulk-delete` / `bulk-update` — 2-A-4-2
- `clear-all` — 2-A-4-2. **현재 하드 삭제(`.delete()`)라 baseline/overlay에서 의미 재정의 필요**
- `upload-excel` — 2-A-4-3 (별도 규모)
- control-assertions CRUD — 후속 (junction overlay 별도)
- processes/sub-processes/risks CRUD — 후속

---

## 2. 핵심 — source에 따른 분기

**같은 조작이 대상에 따라 다른 일을 한다.** 대상의 정체성 id로 baseline 유래인지 회사 add인지 판별하고 분기한다.

| 조작 | baseline 유래 대상 | 회사 add 대상 |
|---|---|---|
| POST | — | **add instance 생성** |
| PATCH | **override instance 생성/갱신** (바뀐 필드만) | instance 직접 수정 |
| DELETE | **exclude instance 생성** (원본 보존) | instance soft delete |

판별: `control_id`가 `baseline_controls`에 있으면 baseline 유래, `control_instances`에 있으면 add. (2-A-3 `get_control`의 정체성 id 매칭 방식 참고)

### 2-1. POST /controls → add instance
- `ControlInstance(action="add", baseline_control_id=None, ...자체 필드)` 생성
- tenant_id는 자동 stamp(ADR-0026), 수동 지정 금지
- 상위 참조는 이중 FK 규칙 — 요청의 risk_id가 baseline risk면 `risk_baseline_id`, instance risk면 `risk_instance_id` (2-B-2 규칙)
- 응답은 2-A-3와 동일 형태(envelope 포함, source="tenant")

### 2-2. PATCH — baseline 대상 → override instance

**필드 diff가 핵심이다.** 요청 값을 baseline과 **비교해 다른 필드만** instance에 저장한다.

```
1. baseline_control 조회
2. 기존 instance 있는지 확인 (없으면 새로 생성, action="override")
3. 요청의 각 필드에 대해:
     - baseline 값과 같으면  → instance 필드 = NULL   (baseline 따름)
     - baseline 값과 다르면  → instance 필드 = 요청 값 (override)
4. 모든 필드가 baseline과 같아지면 → action을 "override" → "adopt"로 전환
   (instance는 삭제하지 않고 남긴다 — 회사가 검토했다는 흔적 유지, resolver 결과는 동일)
```

**이 처리를 반드시 지킬 것.** 요청 값을 그대로 저장하면(baseline과 같아도 override로 기록) **되돌린 필드가 baseline 개정을 따라가지 않는다.** ADR-0027의 "필드 diff = 법령 개정 시 미변경분 자동 갱신"이 무력화되며, 사용자는 되돌렸다고 생각하는데 실제로는 고정되는 조용한 버그가 된다.

주의: `False`/`0`/빈 문자열은 유효한 값이다. `if not value` 같은 falsy 판정 금지, `is None`으로 판별할 것.

### 2-3. PATCH — add 대상 → instance 직접 수정
해당 `ControlInstance`(action="add")의 필드를 직접 갱신. diff 비교 불필요(baseline이 없음).

### 2-4. DELETE — baseline 대상 → exclude instance
- 기존 instance 없으면 `action="exclude"` instance 생성
- 기존 instance 있으면(adopt/override) `action="exclude"`로 전환하고 override 필드는 NULL로 정리
- **baseline_controls는 절대 건드리지 않는다** (전역 표준, 물리·soft 삭제 모두 금지)
- 삭제 의미론(2-B-3.5 규약): baseline → exclude(hide), 원본 보존

### 2-5. DELETE — add 대상 → instance soft delete
해당 instance의 `is_deleted = True`.

---

## 3. 제약 준수

- `(tenant_id, baseline_control_id)` 복합 unique — 한 baseline에 instance는 하나. 새로 만들기 전 기존 instance 조회 필수(중복 생성 시 위반).
- `(tenant_id, code)` 복합 unique — add/override에서 code 충돌 주의.
- 이중 FK check(`ck_*_single_parent`) — 상위 참조는 하나만.
- tenant 격리는 자동(ADR-0026). **수동 tenant 필터 금지.**

---

## 4. 완료 기준

- [ ] POST → add instance 생성, 목록에 즉시 반영(write→read 왕복)
- [ ] PATCH(baseline) → override instance, **바뀐 필드만 저장**(같은 값은 NULL)
- [ ] PATCH로 모든 필드를 baseline과 같게 되돌리면 → action이 adopt로 전환
- [ ] PATCH(add) → instance 직접 수정
- [ ] DELETE(baseline) → exclude instance, **baseline_controls 불변**
- [ ] DELETE(add) → instance soft delete
- [ ] False/0/"" 가 유효 값으로 처리됨 (falsy 판정 버그 없음)
- [ ] 복합 unique·check 제약 위반 없음
- [ ] **xfail 7건 xpass → strict라 실패로 뜸 → 마킹 제거**하고 정상 통과 확인
- [ ] pytest 전체 통과 (기존 105 passed 기준, 회귀 없음)
- [ ] 신규 테스트: 위 6가지 분기 각각 + 되돌리기(adopt 전환) + baseline 불변 확인
- [ ] bulk·clear-all·excel·assertions CRUD 미변경 (후속 범위)

완료 후 `docker compose up -d --build backend` 재빌드. **baseline_controls count=95 불변 확인**(쓰기가 baseline을 건드리지 않았는지). config.py admin_password 건드리지 말 것.

---

## 5. 작업 전 확인 (Claude Code 먼저 수행)

- `api/rcm.py` create/update/delete_control 현재 구현
- `api/rcm.py` get_control (2-A-3) — 정체성 id 매칭 방식 재사용
- `models/rcm_baseline.py` ControlInstance — action 규칙·제약·이중 FK 필드명
- `schemas/rcm.py` ControlCreate / ControlUpdate
- `tests/test_rcm.py` xfail 7건 — 어떤 왕복을 검증하는지

---

ICFR_rcm_crud_2a41_20260723.md 진행해줘
