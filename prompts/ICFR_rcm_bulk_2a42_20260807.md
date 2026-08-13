# ICFR 2-A-4-2 — Control 다건·목록 baseline/overlay 전환 + clear-all 제거 명세

- **작성일**: 2026-08-07
- **근거**: ADR-0027, 2-A-4-1(단건 전환) 후속
- **Tier**: Tier 2 (**쓰기 경로 변경** + 엔드포인트 1개 제거 — 파괴적 레거시 정리)
- **원칙**: ADR-0020 제로 추상화 — 명시적 if 분기, 서비스 클래스·패턴 금지. ADR-0023 데이터 보존.

---

## 0. 성격과 목표

2-A-4-1이 통제 **단건** 쓰기(POST/PATCH/DELETE)를 instance로 옮겼다. 그런데 **다건**(`bulk-delete`/`bulk-update`)과 **목록**(`GET /controls`)은 아직 legacy `controls`를 본다. 지금 상태는 경로별로 대상 테이블이 갈리는 중간 상태다:

| 경로 | 대상 | 상태 |
|---|---|---|
| `POST /controls` · `PATCH /controls/{id}` · `DELETE /controls/{id}` | instance | ✅ 2-A-4-1 |
| `GET /controls/search` · `GET /controls/{id}` | resolver | ✅ 2-A-3 |
| `POST /controls/bulk-delete` · `bulk-update` | **legacy `controls`** | ❌ 본 단계 |
| `GET /controls` | **legacy `controls`** | ❌ 본 단계 |
| `POST /controls/clear-all` | **legacy 하드 삭제** | ❌ 제거 |

본 단계로 **통제 계층의 모든 읽기·쓰기 경로가 baseline/overlay로 통일**된다.

> 상위 계층(processes/sub-processes/risks)과 어서션 junction CRUD는 **본 단계 범위 아님** — §6 참조.

---

## 1. 확정 결정 (마스터 승인)

1. 범위는 **bulk 2개 + `GET /controls` 1개 전환** (상위 계층은 2-A-4-3으로 분리)
2. **`clear-all`은 축소가 아니라 제거** — Phase 0 하드삭제 잔재이고 baseline/overlay에선 위험 기능이다. 재구축은 `seed_baseline.py --reset`이 안전하게 대체한다. "내 결정 되돌리기"는 지금 필요한 기능이 아니며, 필요해지면 그때 명확한 스펙으로 새로 만든다. 어정쩡하게 살려두지 않는다.

---

## 2. bulk-delete 전환

`delete_control`(api/rcm.py:490)과 **완전히 동일한 분기**를 id마다 적용한다.

- baseline 유래 → exclude instance 생성/전환 (원본 `baseline_controls` 절대 불변)
- 회사 add → instance soft delete
- 어느 쪽도 아닌 id → 건너뛴다 (404로 전체를 실패시키지 않는다)

응답은 기존 계약 유지 + 건너뛴 id를 드러낸다:

```json
{ "deleted_count": 2, "skipped_ids": ["..."] }
```

> `deleted_count` 키를 바꾸지 말 것 — 기존 테스트·계약 유지.

---

## 3. bulk-update 전환

`update_control`(api/rcm.py:445)과 **완전히 동일한 분기**를 id마다 적용한다.

- baseline 유래 → override instance 생성/갱신, **필드 diff**(baseline과 같으면 NULL, 다르면 값)
- 전 override 필드가 NULL이 되면 `action="adopt"` 전환 (instance는 남김 — 검토 흔적)
- 회사 add → instance 직접 수정
- 미해당 id는 건너뛰고 `skipped_ids`에 담는다

**주의**: `BulkUpdateRequest.updates`는 `ControlUpdate`다. 단건 PATCH가 `exclude_unset=True`로 "전송된 필드만" 판별하는 것과 달리, 현재 bulk 구현은 `exclude_none=True`를 쓴다(schemas/rcm.py:179, api/rcm.py:342). **`False`/`0`/`""`는 유효 값**이므로 단건과 같은 `exclude_unset` 기준으로 통일할 것. falsy 판정 금지.

---

## 4. `GET /controls` 전환

`resolve_controls` 경유로 바꾸고 envelope(`source`/`baseline_id`/`is_overridden`)를 포함한다. search·상세와 **id 체계가 일치**해야 한다(정체성 id).

- `skip`/`limit` 페이지네이션 계약 유지, `total`은 resolve 결과 전체 건수
- 응답 스키마는 search·상세와 동일 계열로 맞춘다(`ControlRead` 재사용 가능하면 재사용, 신설 금지)

---

## 5. clear-all 제거

제거 대상 (사전 확인 완료 — FE 참조 0건):

| 위치 | 내용 |
|---|---|
| `api/rcm.py:354-373` | `@router.post("/controls/clear-all")` + `clear_all_rcm` |
| `api/rcm.py:22` | import 목록의 `ClearAllRequest` |
| `schemas/rcm.py:183-184` | `class ClearAllRequest` |
| `tests/test_rcm.py:332-341` | `test_clear_all` |

**확인 사항**: `test_clear_all`은 `GET /controls`의 `total == 0`을 단언한다 — §4 전환 시 어차피 깨지는 테스트이므로 제거가 정합적이다. 제거 후 다른 테스트가 clear-all의 부작용(legacy 테이블 비우기)에 암묵 의존하고 있지 않은지 **전체 pytest로 확인**할 것.

> 삭제 커밋이므로 `git grep clear.all`로 잔여 참조 0건을 확인하고 보고할 것.

---

## 6. 분기 로직 공통화 (최소 추출)

단건과 다건이 **같은 코드를 타야** 규칙이 갈라지지 않는다. `update_control`/`delete_control`의 몸통을 내부 함수로 추출하고 단건·다건이 함께 호출한다.

- ADR-0020 범위 내 **함수 추출만**. 클래스·서비스·전략 패턴 금지.
- 추출 함수는 `db.commit()`을 하지 않는다 — 호출자가 트랜잭션 경계를 갖는다(다건은 한 번만 커밋).
- 위치는 `api/rcm.py` 내부 `_` 프리픽스 함수. services 이동은 하지 않는다.

---

## 7. 테스트

**xfail 마킹 제거 (strict라 복구되면 실패로 뜬다)**:
- `test_search_text` — 2-A-4-1이 이미 복구시킴(현재 XPASS(strict) 상태로 red). 마킹 제거
- `test_control_extended_crud` — §4 전환으로 복구 예정. 마킹 제거
- `test_bulk_delete` — xfail이 아닌 순수 실패(`assert 0 == 2`). §2로 복구

**남는 xfail 5건은 건드리지 말 것** (`_XFAIL_SRC_SPLIT` 유지):
`..._includes_process_code` / `..._includes_sub_process_code` / `..._includes_risk_level` / `..._includes_assertions` / `test_search_no_n_plus_one`
→ 원인은 bulk가 아니라 **상위 계층·어서션 CRUD 미전환**이다(§8). 본 단계로 풀리지 않는다.

**신규 테스트** (`tests/test_rcm_crud_overlay.py`에 추가):
- bulk-delete: baseline 유래 → exclude instance 생성 / add → soft delete / 미해당 id → `skipped_ids`
- bulk-update: baseline 유래 → override 필드 diff / 전 필드 동일 시 adopt 되돌림 / add → 직접 수정
- bulk-update falsy 값(`False`, `0`, `""`)이 정상 저장되는지 (`exclude_unset` 통일 검증)
- `GET /controls`가 resolver 기반이고 envelope를 포함하며 search와 id가 일치하는지
- **baseline 원본 불변** — bulk 실행 후 `baseline_controls` 행 수·내용 무변경

---

## 8. 범위 밖 (별도 단계)

- **2-A-4-3 상위 계층 + 어서션 CRUD 전환**: `processes`/`sub-processes`/`risks` POST·PATCH·DELETE → instance, `control-assertions` → `ControlAssertionInstance`. 남은 xfail 5건은 여기서 해소. `_resolve_risk_parent`가 legacy risk에 대해 `(None, None)`을 반환해 add instance가 상위를 잃는 문제가 근본 원인.
- **upload-excel 파서 코어 분리 + 다중 헤더행 대응**: 현재 최종 엑셀(헤더 6+7행)을 올리면 0건 파싱된다(ClaudeICFR.md 13.6). seed는 보정했으나 API는 미수정.
- **`test_post_creates_add_instance` 테스트 격리**: 전체 실행 시에만 실패(공용 세션 sqlite 오염). 인프라 이슈라 별건.

---

## 9. 완료 기준

- [ ] bulk-delete — 단건 delete와 동일 분기, `deleted_count` 계약 유지, `skipped_ids` 추가
- [ ] bulk-update — 단건 update와 동일 분기(필드 diff·adopt 되돌림), `exclude_unset` 통일
- [ ] `GET /controls` — resolver 경유 + envelope + search와 id 일치
- [ ] clear-all 라우트·스키마·테스트 제거, 잔여 참조 0건
- [ ] 분기 로직 함수 추출 — 단건·다건이 같은 코드 사용, 커밋은 호출자
- [ ] xfail 마킹 2건 제거(`test_search_text`, `test_control_extended_crud`), 5건은 유지
- [ ] bulk·목록 신규 테스트 추가, baseline 원본 불변 검증 포함
- [ ] pytest — 기존 실패 3건 중 2건 해소 목표(`test_bulk_delete` 복구 + XPASS 정리). `test_post_creates_add_instance`는 별건이므로 남아도 무방하나 **결과를 정확히 보고**할 것

---

## 10. 작업 전 확인 (Claude Code)

- `api/rcm.py:445-522` — 단건 update/delete 분기 (추출 대상 원본)
- `api/rcm.py:328-373` — bulk 2개 + clear-all 현행
- `api/rcm.py:385` `_OVERRIDE_FIELDS`, `:388` `_resolve_risk_parent`
- `schemas/rcm.py:179-184` — `BulkUpdateRequest`/`ClearAllRequest`
- `services/control_resolver.py` — `resolve_controls` 반환 키(envelope 포함)
- FE `features/rcm/api/controlsApi.ts` — bulk·목록 미사용 확인됨(전환해도 FE 영향 없음). 재확인만.

---

## 11. 주의

- **`baseline_controls`는 어떤 경우에도 수정·삭제하지 않는다.** tenant의 "삭제"는 exclude instance다(2-B-3.5 규약).
- 다건 작업은 **단일 트랜잭션** — 중간 실패 시 전체 롤백.
- `config.py` admin_password 건드리지 말 것.
- 커밋 전 마스터 보고. 커밋·push는 마스터 OK 후.
