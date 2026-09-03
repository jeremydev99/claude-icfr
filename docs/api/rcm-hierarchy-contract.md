# 상위 3계층 CRUD API 계약 (Process / SubProcess / Risk)

> **스냅샷 문서 — 기준 커밋 `af4c247` / 2026-09-02 시점. API 변경 시 갱신 필요.**
>
> 자동 생성 문서(FastAPI `/docs`)가 API 스펙의 단일 진실 공급원이다(ADR-0017 §19).
> 이 문서는 그것이 드러내지 못하는 것 — **계층마다 다른 검증 동작, 계약에 없는 것** — 을
> 코드에서 읽어 정리한 것이다. 스펙을 대체하지 않는다.
>
> 근거 파일: `backend/app/schemas/rcm.py`, `backend/app/api/rcm.py`,
> `backend/app/services/control_resolver.py`
>
> **⚠ 이 문서에는 미해결 결함이 하나 반영돼 있다(§6-①). 그것이 고쳐지면 이 문서는 틀리게 된다.**
> 해당 절에 표시해 두었으니 수정 시 함께 갱신할 것.

작성 배경: 프론트 배선 전 계약 확인 요청(Regina). 추정 없이 맞추기 위한 것이므로
**코드에서 실제로 읽은 것만** 적었다. "동일할 것" 같은 추정 서술은 넣지 않았다.

---

## 1. 엔드포인트 경로

| 동작 | Process | SubProcess | Risk | Control |
|---|---|---|---|---|
| 목록 | `GET /api/rcm/processes` | `GET /api/rcm/sub-processes` | `GET /api/rcm/risks` | `GET /api/rcm/controls` |
| 상세 | `GET /processes/{process_id}` | `GET /sub-processes/{sp_id}` | `GET /risks/{risk_id}` | `GET /controls/{control_id}` |
| 생성 | `POST /processes` → 201 | `POST /sub-processes` → 201 | `POST /risks` → 201 | `POST /controls` → 201 |
| 수정 | `PATCH /processes/{id}` → 200 | `PATCH /sub-processes/{id}` → 200 | `PATCH /risks/{id}` → 200 | `PATCH /controls/{id}` → 200 |
| 삭제 | `DELETE /processes/{id}` → 204 | `DELETE /sub-processes/{id}` → 204 | `DELETE /risks/{id}` → 204 | `DELETE /controls/{id}` → 204 |

목록 쿼리 파라미터 — Process: `skip`·`limit` / SubProcess: `process_id`·`skip`·`limit` /
Risk: `sub_process_id`·`skip`·`limit` / Control: `skip`·`limit`.

**Control에만 있는 것**: `GET /controls/search`, `POST /controls/bulk-delete`,
`POST /controls/bulk-update`. **상위 3계층에는 search·bulk 엔드포인트가 없다.**

목록 응답 봉투는 4계층 공통 `{"items": [...], "total": int, "skip": int, "limit": int}`.

## 2. 요청 바디 스키마

### POST (생성)

| 계층 | 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|---|
| Process | `code` | str | ✅ | 1–20자 |
| | `name` | str | ✅ | 1–100자 |
| | `description` | str \| null | — | 기본 `null` |
| SubProcess | `code` | str | ✅ | 1–20자 |
| | `name` | str | ✅ | 1–200자 |
| | `process_id` | UUID | ✅ | — |
| Risk | `code` | str | ✅ | 1–30자 |
| | `description` | str | ✅ | 길이 제한 없음 |
| | `assessment_level` | str | — | 기본 `"LR"`, 패턴 `^(LR\|MR\|HR\|SR)$` |
| | `sub_process_id` | UUID | ✅ | — |

**SubProcess에는 `description` 필드가 없다**(`SubProcessBase` = code/name/process_id).
Process·Risk와 다르지만 모델(`BaselineSubProcess`)에도 없는 필드라 API 누락이 아니라
도메인 정의다.

### PATCH (수정)

| 계층 | 수정 가능 필드 |
|---|---|
| Process | `name`, `description` |
| SubProcess | `name` |
| Risk | `description`, `assessment_level` |
| Control | `name`, `description`, `objective`, `owner_name`, `is_key_control`, `preventive_detective`, `auto_manual`, `activity_*` 6개, `related_accounts`, `frequency`, `ipe_relevant`, `related_systems`, `euc_description` |

전 계층 모두 **모든 필드가 optional**이고, 서버가 `body.model_dump(exclude_unset=True)`로
**전송된 필드만** 처리한다. `false`/`""`/`0`도 유효한 값으로 저장되므로 falsy 판정을 쓰면 안 된다.

**`code`와 상위 참조는 PATCH 대상이 아니다 — 4계층 공통.**
`api/rcm.py:100` 주석: *"code·상위참조는 제외 — 정체성/구조라 override 대상 아님"*.
**코드 변경·상위 이동 UI를 만들면 서버가 조용히 무시한다**(에러도 나지 않는다).

override 대상 필드 집합은 Update 스키마에서 파생된다 —
`_PROCESS_OVERRIDE_FIELDS = list(ProcessUpdate.model_fields.keys())` (`rcm.py:101-103`).
Control도 `_OVERRIDE_FIELDS = list(ControlUpdate.model_fields.keys())` (`rcm.py:587`)로 같은 방식.

## 3. 응답 스키마 — envelope

**4계층 전부 flat 계약이며 필드명·의미가 같다.** 중첩 wrapper 없음.

```python
# ProcessRead / SubProcessRead / RiskRead / ControlRead 공통 (schemas/rcm.py)
source: str | None = None            # "baseline"(adopt/override) | "tenant"(add)
baseline_id: UUID | None = None      # baseline 유래면 그 id, add면 None
is_overridden: bool = False          # override instance 적용 시 True
```

`SubProcessRead` 주석 원문: *"통제(ControlRead)와 **동일한 flat 계약**(중첩 wrapper 금지)
— FE 가 계층별로 분기하지 않도록."*

값 생성 규칙은 `control_resolver.py:_resolve_layer`가 4계층 공통으로 처리한다.

| instance 상태 | `id` | `source` | `baseline_id` | `is_overridden` |
|---|---|---|---|---|
| instance 없음 / `adopt` | baseline id | `"baseline"` | 그 id | `false` |
| `override` | baseline id | `"baseline"` | 그 id | `true` |
| `exclude` | — | 결과에서 행 자체가 빠짐 | — | — |
| `add` | instance id | `"tenant"` | `null` | `false` |

공통 응답 필드: `id`, `created_at`, `updated_at` + 계층별 본문 필드.

**envelope는 항상 채워진다.** 스키마에 기본값이 있는 것은 resolver 외 경로(직접
`model_validate`)를 위한 호환 장치이고, 상위 3계층의 **응답을 내는 4개 경로가 전부
resolver를 거친다** — 목록은 `resolve_processes`/`resolve_hierarchy`, 상세·POST·PATCH는
`_resolved_process_or_404`/`_resolved_sub_process_or_404`/`_resolved_risk_or_404`.
따라서 프론트가 이 3필드를 required로 잡아도 깨지지 않는다
(FE는 2026-09-02 커밋 `8fe0ba4`에서 required로 전환했다).

**주의 — 상위 참조는 읽기에서 nullable이다.** `SubProcessRead.process_id`,
`RiskRead.sub_process_id`, `ControlRead.risk_id`가 전부 `UUID | None = None`이다
(생성 시에는 required). 스키마 주석: *"resolver 는 상위 미지정 add 행을 낼 수 있어
읽기에서는 nullable"*. **이 필드를 required로 잡으면 런타임에 깨질 수 있다.**

## 4. 상위 참조 필드

| 계층 | 요청 필드명 | 응답 필드명 |
|---|---|---|
| SubProcess | `process_id` | `process_id` |
| Risk | `sub_process_id` | `sub_process_id` |
| Control | `risk_id` | `risk_id` |
| Process | 없음(최상위) | 없음 |

**baseline id인지 instance id인지 구분해서 보낼 필요가 없다.** 서버가 판별한다.

```python
# api/rcm.py:196  (_resolve_sub_process_parent, _resolve_risk_parent 도 같은 형태)
def _resolve_process_parent(db, process_id):
    if process_id is None: return None, None
    if db.query(BaselineProcess).filter(BaselineProcess.id == process_id).first() is not None:
        return process_id, None          # baseline 쪽 FK
    if db.query(ProcessInstance).filter(ProcessInstance.id == process_id).first() is not None:
        return None, process_id          # instance 쪽 FK
    return None, None                    # 어느 쪽도 아님
```

**목록에서 받은 `id`를 그대로 넣으면 된다.** 응답의 `process_id`/`sub_process_id`도
"정체성 id"(`_parent_id` 규칙: add 상위 밑이면 instance id, 그 외에는 baseline id)라 왕복이 맞는다.

**⚠ 존재하지 않는 상위 id를 보내면 에러가 아니라 `201`이다.** 위 마지막 줄 `return None, None`이
그대로 적용되어 **상위가 `null`인 행이 생성된다.** 4계층 공통 동작이다(§6-③).

## 5. 에러 응답

| 상황 | Process / SubProcess / Risk | Control |
|---|---|---|
| 인증 없음 | 401 | 401 |
| 바디 검증 실패(길이·패턴·타입) | `422 {"detail": [...]}` | 동일 |
| 대상 없음 (GET/PATCH/DELETE) | `404 {"detail": "Process not found"}` 등 | `404 {"detail": "Control not found"}` |
| **code 중복 — baseline과 충돌** | **`409 {"detail": "프로세스 코드 'X' 는 표준(baseline)에 이미 있습니다"}`** | **검증 없음 → 201로 생성됨** (§6-①) |
| **code 중복 — 같은 tenant add와 충돌** | **`409 {"detail": "프로세스 코드 'X' 는 이미 사용 중입니다"}`** | **`409 {"detail": "데이터 무결성 제약 위반 (중복 또는 참조 오류)"}`** |
| 존재하지 않는 상위 참조 | 에러 없음 — 201, 상위 `null` | 동일 |
| 낙관적 잠금 충돌 | **없음** | **없음** |

409 메시지는 `_assert_code_available`(`rcm.py:106`)이 생성하며 `{label}`은 계층별로
`"프로세스"` / `"하위프로세스"` / `"위험"`이다.
**사용자 노출용으로 작성돼 있으니 `detail`을 그대로 표시해도 된다.**

**낙관적 잠금은 API 계약에 없다.** `row_version` 컬럼은 모델(`VersionMixin`)에 있으나
`schemas/rcm.py`·`api/rcm.py`에 **언급이 0건**이다. 요청에 버전을 실을 곳도, 409를 받을
경로도 없다 — **동시 편집 시 마지막 쓰기가 이긴다.** 4계층 공통.

## 6. Control과 다른 지점

### ① code 중복 검증 — 상위 3계층에만 있다 (차이 있음, **미해결**)

> **⚠ 미해결 항목 — `ClaudeICFR.md` 13.9-17 에 등록됨.**
> **이 결함이 고쳐지면 위 §5 표의 Control 열과 이 절이 함께 틀리게 된다. 반드시 같이 갱신할 것.**

`_assert_code_available` 호출처는 `rcm.py:255`(processes), `310`(sub-processes),
`363`(risks) **3곳뿐**이고 `create_control`(`rcm.py:692`)에는 없다. 결과:

- 3계층: 409 + 어느 쪽과 충돌했는지 구분된 한국어 메시지
- Control: **baseline code와 겹치면 아무 에러 없이 201** → resolver 결과에 같은 code가 둘.
  instance끼리 겹치면 DB 유니크 위반 → 전역 핸들러가 409 + 일반 문구

**판단: 2-A-4-3 작업의 소급 누락이다.** `_assert_code_available` docstring이
*"baseline 테이블의 code 와 겹치는 경우는 어떤 제약도 막지 못하므로 여기서 함께 본다"*라고
적고 있는데, 이 논리는 control에 그대로 해당한다. control CRUD는 2-A-4-1(더 이전)에
만들어졌고 이 헬퍼는 2-A-4-3(`cad62a9`)에 신설되면서 control로 소급되지 않았다.
**의도된 차이로 보이지 않는다.**

**FE 영향**: 통제 생성 폼과 상위 3계층 폼의 409 처리를 같은 코드로 쓰면 안 된다.
3계층은 `detail`을 그대로 노출해도 되지만, 통제는 일반 문구라 별도 안내가 필요하다.

### ② 그 외 계약은 차이 없음 — 단언한다

- envelope 3필드(`source`/`baseline_id`/`is_overridden`): 필드명·타입·기본값·생성 규칙 동일
  (`_resolve_layer` 공통 함수)
- `id` 체계: 목록·상세·생성 응답 전부 정체성 id, 4계층 동일
- PATCH `exclude_unset` 처리, `code`·상위참조 수정 불가: 4계층 동일
- DELETE: 204·본문 없음. baseline 유래는 exclude instance / add는 soft delete —
  서버가 분기하므로 **FE는 source와 무관하게 같은 엔드포인트를 호출**한다 (4계층 동일)
- 404 응답 형태: `{"detail": "<계층명> not found"}` — 문자열만 다름
- 목록 응답 봉투, 정렬(`code` 오름차순): 동일

### ③ 4계층 공통이지만 FE가 알아야 할 동작 2건

- **존재하지 않는 상위 id → 201 + 상위 null.** 검증이 없다. 드롭다운에서만 고르게 하면
  실무상 문제되지 않지만, 서버가 막아주지 않는다는 점은 알고 있어야 한다.
- **낙관적 잠금 없음.** 두 사람이 같은 항목을 편집하면 나중 저장이 이긴다
  (`ClaudeICFR.md` 13.9-18 에 등록).

이 둘은 control에도 동일하게 존재하므로 **3계층 배선의 신규 위험은 아니다.**
