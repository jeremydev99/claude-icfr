# ICFR 2-A-3 — RCM 조회 API resolver 전환 명세

- **작성일**: 2026-07-23
- **근거**: ADR-0027, 2-B 완료 + 2-A-2 이관 완료
- **Tier**: Tier 2 (**기존 API 변경 — 회귀 위험 있는 첫 단계**)
- **원칙**: ADR-0020 제로 추상화. 모든 회사 유연 적용, 고정 코딩 0.

---

## 0. 성격 — 지금까지와 다르다

2-A-1 ~ 2-A-2는 **병행 구축**(기존 미변경)이라 회귀 위험이 0이었다. 본 단계는 **기존 API의 동작을 바꾼다.** Regina 프론트가 실제로 영향받는 첫 지점이기도 하다.

전제는 갖춰졌다 — 2-A-2 이관으로 baseline 699행이 채워졌고, `resolve_controls`가 95건을 관계 필드(process_code/sub_process_code/risk_level/assertions) + source envelope와 함께 반환하는 것이 실데이터로 검증됐다.

---

## 1. 범위 — search + 상세 (최소 단위)

### 전환 대상 (이번 단계)
- **`GET /controls/search`** (rcm.py:249) — 목록·검색·필터·정렬·페이지네이션
- **`GET /controls/{control_id}`** (rcm.py:419) — 상세

**둘은 반드시 함께 전환한다.** search만 바꾸면 목록이 baseline id를 반환하는데 상세는 기존 `controls` 테이블을 조회해 **404가 난다**(id 체계 불일치). 프론트의 목록→상세 흐름이 전부 깨진다.

### 전환하지 않는 것 (후속)
- `GET /controls`(단순 목록, rcm.py:402), `/matrix`, `/info` 통계 — 2-A-3 후속 또는 별도
- processes/sub-processes/risks/risk-categories 조회 — 후속 (resolve_* 함수는 준비됨)
- 모든 POST/PATCH/DELETE, bulk-*, upload-excel — **2-A-4 CRUD 범위**
- 기존 `controls` 등 테이블 — 미변경 (제거는 2-A-4 이후 판단)

---

## 2. `/controls/search` 전환

기존은 SQL 쿼리(조인·WHERE·ORDER BY·LIMIT). 이를 **resolve_controls 결과 위의 메모리 처리**로 재구현한다.

```
rows = resolve_controls(db)        # 활성 tenant 자동 격리, 관계 필드·envelope 포함
→ 필터 적용 → 정렬 → total 계산 → 페이지네이션 → 응답
```

### 유지해야 할 파라미터 (전부 동일 동작)
기존 시그니처(rcm.py:249~)를 그대로 유지한다. 작업 전 실제 파라미터를 확인하고 **하나도 빠뜨리지 말 것**:
- `q` — code / name / description / owner_name 부분일치(대소문자 무시)
- `owner` — owner_name 부분일치
- `frequency`, `is_key_control`, `auto_manual`, `preventive_detective` — 일치
- `risk_level`, `sub_process_code`, `process_code` — **resolver가 이미 채운 필드로 비교**(조인 불필요)
- `assertion` — resolver의 assertions 배열에 해당 코드 포함 여부
- `sort_by`(code/name/frequency/created_at/owner_name) + `sort_order`(asc/desc)
- `skip` / `limit`, 응답의 `total`

정렬 시 None 값 처리에 주의(기존 SQL의 NULL 정렬과 완전히 동일할 필요는 없으나, 예외가 나지 않아야 함).

### 응답
`ControlSearchResponse` / `ControlSearchOut` 유지 + **source envelope 3필드 추가**:
- `source`(str) / `baseline_id`(UUID|None) / `is_overridden`(bool)
- **flat 유지** — 중첩 wrapper 금지. Regina FE가 flat 계약으로 이미 준비 완료(`sourceEnvelope.ts`). 이 형태를 바꾸면 프론트 계약 파괴.
- 스키마(`schemas/rcm.py:180-188` ControlSearchOut)에 3필드를 추가하되 기존 필드는 그대로 둔다.

---

## 3. `/controls/{control_id}` 전환

`resolve_controls(db)` 결과에서 `id == control_id`인 항목을 찾아 반환. 없으면 404.

- 응답 모델 `ControlRead`에도 **source envelope 3필드 추가**(목록과 일관).
- id는 정체성 id — baseline 유래면 baseline id, add면 instance id (프론트가 목록에서 받은 id를 그대로 쓴다).

> 단건 조회를 위해 전체를 resolve하는 것은 비효율이나, 95~수백 규모에서는 문제없다. **구조 정합성 우선, 최적화는 필요해질 때.** 조기 최적화로 로직을 분기시키지 말 것.

---

## 4. 회귀 방지 (필수)

기존 동작과 **결과가 같아야** 한다. 다음을 반드시 확인:

- 전환 후 `/controls/search`가 **95건** 반환 (필터 없을 때)
- 각 필터 파라미터가 기존과 동일하게 동작 (q, owner, frequency, risk_level, process_code, assertion 등 개별 확인)
- 정렬 동작 (code asc/desc, owner_name 등)
- 페이지네이션 (skip/limit, total 정확)
- 상세 조회 — 목록에서 받은 id로 200 반환, 없는 id는 404
- 관계 필드가 기존과 동일 값 (process_code/sub_process_code/risk_level/assertions)
- 기존 테스트(`tests/test_rcm.py`) 통과 — **깨지면 그 자체가 회귀 신호다. 테스트를 고쳐 통과시키지 말고 보고할 것.**

> 다만 응답에 envelope 3필드가 **추가**되므로, 필드 존재를 엄격 검증하는 테스트가 있다면 그건 정당한 수정 대상이다. 값·건수가 달라지는 것과 구분할 것.

---

## 5. 완료 기준

- [ ] `/controls/search`가 resolve_controls 기반으로 동작 (모든 파라미터 유지)
- [ ] `/controls/{control_id}` 동일 전환 (id 체계 일치)
- [ ] ControlSearchOut / ControlRead에 source·baseline_id·is_overridden **flat 추가**
- [ ] 필터·정렬·페이지네이션·total 기존과 동일 결과
- [ ] 95건 반환, 상세 200/404 정상
- [ ] 기존 test_rcm.py 통과 (envelope 필드 추가 외 수정 없이)
- [ ] pytest 전체 통과 (기존 112 기준, 회귀 없음)
- [ ] POST/PATCH/DELETE·bulk·excel·matrix 미변경 (2-A-4 범위)

완료 후 `docker compose up -d --build backend` 재빌드. **controls count=95 확인**. config.py admin_password 건드리지 말 것.

---

## 6. 작업 전 확인 (Claude Code 먼저 수행)

- `api/rcm.py:249-352` search 전체 — 파라미터·필터·정렬 로직 (하나도 빠뜨리지 않게)
- `api/rcm.py:419-425` 상세
- `schemas/rcm.py` ControlSearchOut / ControlSearchResponse / ControlRead
- `services/control_resolver.py` resolve_controls 반환 dict 키
- `tests/test_rcm.py` 기존 검증 항목

---

ICFR_rcm_search_2a3_20260723.md 진행해줘
