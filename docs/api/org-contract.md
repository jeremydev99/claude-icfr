# 조직·역할 배정 API 계약 (부서 / 소속 / 배정 / 해석 / 정책)

> **스냅샷 문서 — 기준 커밋 `d094a04` + 4-2 수정 / 2026-09-19 시점. API 변경 시 갱신 필요.**
>
> 자동 생성 문서(FastAPI `/docs`)가 API 스펙의 단일 진실 공급원이다(`ClaudeICFR.md` §19).
> 이 문서는 그것이 드러내지 못하는 것 — **판정 규칙, 권한 검사 위치, 실제 에러 문구** — 을
> 코드에서 읽어 정리한 것이다. 스펙을 대체하지 않는다.
>
> 근거 파일: `backend/app/schemas/org.py`, `backend/app/api/org.py`,
> `backend/app/api/role_assignment.py`, `backend/app/api/user_mgmt.py`,
> `backend/app/core/permissions.py`,
> `backend/app/services/role_resolver.py`, `backend/app/models/role_assignment.py`
>
> 근거 ADR: ADR-0031(역할·권한 모델). 형식은 `rcm-hierarchy-contract.md` 와 같다.
>
> 참조 표기 — 문서명 없는 `§3.4` 는 이 문서의 절이다. 다른 문서는 `ADR-0031 §2.4`,
> `ClaudeICFR.md` 13.9-23 처럼 문서명을 붙인다.

**모든 응답 예시는 실제 왕복에서 얻은 원문이다.** 추정으로 적은 값은 없다.

---

## 1. 엔드포인트 전체

| 구분 | 동작 | 경로 |
|---|---|---|
| 부서 | 목록 | `GET /api/org/departments` |
| | 생성 | `POST /api/org/departments` → 201 |
| | 상세 | `GET /api/org/departments/{dept_id}` |
| | 수정 | `PATCH /api/org/departments/{dept_id}` → 200 |
| | 삭제 | `DELETE /api/org/departments/{dept_id}` → 204 |
| 소속 | 목록 | `GET /api/org/memberships` |
| | 생성 | `POST /api/org/memberships` → 201 |
| | 수정 | `PATCH /api/org/memberships/{membership_id}` → 200 |
| | 삭제 | `DELETE /api/org/memberships/{membership_id}` → 204 |
| 배정 | 목록 | `GET /api/org/assignments` |
| | 생성/교체 | `POST /api/org/assignments` → 201 |
| | 삭제 | `DELETE /api/org/assignments/{assignment_id}` → 204 |
| **해석** | **통제별 역할** | **`GET /api/org/controls/{control_id}/roles`** |
| 정책 | 목록 | `GET /api/org/policies` |
| | 설정/변경 | `PUT /api/org/policies` → 200 |
| **테넌트 역할** | 목록 | `GET /api/users/roles/list` |
| | 배정 | `POST /api/users/roles` → 201 |
| | 상세 | `GET /api/users/roles/{role_id}` |
| | 수정 | `PATCH /api/users/roles/{role_id}` → 200 |
| | 해제 | `DELETE /api/users/roles/{role_id}` → 204 |

쿼리 파라미터 — 부서: `skip`·`limit` / 소속: `user_id`·`department_id`·`skip`·`limit` /
배정: `scope`·`target_id`·`skip`·`limit`.

**배정에는 `PATCH` 가 없다.** `POST` 가 생성과 교체를 겸한다 — 같은
`(scope, target_id, role_name)` 이 이미 있으면 `user_id` 만 바꾼다(§6-①).

**정책에는 `POST`/`DELETE` 가 없다.** `PUT` 이 upsert 다.

**테넌트 역할은 `/api/org` 가 아니라 `/api/users` 밑에 있다.** 통제 단위 배정
(`/api/org/assignments`)과 다른 층이다 — 전자는 사람에게 붙는 제도 운영 역할 5종
(ADR-0031 §2.1), 후자는 통제에 붙는 역할 3종(§2.2). 저장소도 `user_roles` 와
`role_assignments` 로 다르다. 권한·허용 값은 §5.3.

## 2. 요청/응답 스키마

### 2.1 부서

**`POST` 바디** (`DepartmentCreate`)

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `name` | str | ✅ | 1–100자 |
| `manager_id` | UUID \| null | — | 기본 `null` |
| `parent_id` | UUID \| null | — | 기본 `null` |
| `external_code` | str \| null | — | 최대 50자 |

**`PATCH` 바디** (`DepartmentUpdate`) — 위 4개 전부 optional. `exclude_unset` 판별.

**응답** (`DepartmentRead`) — 요청 4필드 + `id`, `created_at`, `updated_at`,
`manager_name`(표시용 파생값, 책임자 미지정이면 `null`).

```json
{
  "name": "자금팀",
  "manager_id": "01a06aa0-d82b-7b41-b863-c5ee4c9955b6",
  "parent_id": null,
  "external_code": null,
  "id": "01a06aa1-3c99-7792-b1de-13cd17a2722f",
  "created_at": "2026-09-04T04:15:46",
  "updated_at": "2026-09-04T04:15:46",
  "manager_name": "홍길동"
}
```

**`parent_id` 는 계층 개념 보존용이며 초기 전부 NULL 이다**(ADR-0031 §2.8).
목록은 평면으로 내려온다 — **서버가 계층을 조립하지 않는다.**

**`external_code` 는 인사시스템 연동 키이며 현재 미사용**이다. 값을 넣어도 아무 동작이 없다.

### 2.2 소속

**`POST` 바디** (`UserDepartmentCreate`)

| 필드 | 타입 | 필수 | 기본 |
|---|---|---|---|
| `user_id` | UUID | ✅ | — |
| `department_id` | UUID | ✅ | — |
| `is_primary` | bool | — | `false` |

**`PATCH` 바디** (`UserDepartmentUpdate`) — `is_primary` 만. 다른 필드는 바꿀 수 없다
(부서를 옮기려면 삭제 후 재생성).

**응답** (`UserDepartmentRead`) — `id`, `user_id`, `department_id`, `is_primary`,
`created_at`, `updated_at`, `user_name`, `department_name`.

```json
{
  "id": "01a06aa1-3ccb-73c3-9af0-aa2aa1e26c66",
  "user_id": "01a06aa0-d82b-7b41-b863-c5ee4c9955b6",
  "department_id": "01a06aa1-3c99-7792-b1de-13cd17a2722f",
  "is_primary": true,
  "created_at": "2026-09-04T04:15:46",
  "updated_at": "2026-09-04T04:15:46",
  "user_name": "홍길동",
  "department_name": "자금팀"
}
```

**한 사람이 여러 부서에 소속될 수 있다.** 회계팀 직원이 내부회계전담팀을 겸하는 등
중소기업에서 실재하는 구조다.

**주 소속은 사용자당 정확히 하나다.** 두 번째를 `is_primary: true` 로 만들면
**기존 주 소속이 자동 해제된다** — 부서 이동이 정상 업무이므로 "이미 있습니다" 로
막지 않는다. 사용자당 1건은 DB 부분 유니크 인덱스(`uq_user_departments_one_primary`)가
최종 보장한다.

### 2.3 배정

**`POST` 바디** (`RoleAssignmentCreate`)

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `scope` | str | ✅ | 패턴 `^(process\|control)$` |
| `target_id` | UUID | ✅ | 프로세스 또는 통제의 **정체성 id** |
| `role_name` | str | ✅ | 패턴 `^(control_owner\|dept_approver\|assessor)$` |
| `user_id` | UUID | ✅ | — |
| `conflict_reason` | str \| null | — | 이해상충 발생 시 필수 (§4) |

**`role_name` 에 `icfr_manager`·`ceo`·`auditor`·`external_auditor`·`sys_admin` 을 넣으면
422 다.** 이들은 테넌트 단위 역할이라 통제에 배정되지 않으며 `user_roles`
(`/api/users/roles`)에서 관리한다(ADR-0031 §3.1).

**응답** (`RoleAssignmentRead`) — `id`, `scope`, `target_id`, `role_name`, `user_id`,
`user_name`, `created_at`, `updated_at`.

`target_id` 는 **RCM 목록에서 받은 `id` 를 그대로 넣으면 된다.** baseline 유래인지
회사 add 인지 구분할 필요가 없다(정체성 id 규칙, ADR-0027).

### 2.4 정책

**`PUT` 바디** (`TenantPolicyUpsert`) — `policy_key`(1–60자), `policy_value`(1–200자).
**응답** (`TenantPolicyRead`) — `id`, `policy_key`, `policy_value`, `updated_at`.

현재 서버가 해석하는 키는 **이해상충 금지 토글**뿐이다 —
`conflict_{역할A}_{역할B}_blocked` (역할명은 사전순). 값이
`"true"`/`"1"`/`"yes"`(대소문자 무관)이면 금지, **미설정이면 허용**이 기본이다.

**토글 대상은 실제 판정 조합 2개뿐이다.**

```
conflict_assessor_control_owner_blocked
conflict_assessor_icfr_manager_blocked
```

`control_owner = dept_approver` 는 충돌이 아니므로 **금지 설정 대상이 아니다**
(2026-09-04 정정, §3.4). 그 키를 넣어도 서버가 보지 않는다.

### 2.5 목록 응답 봉투

4종 목록 전부 `{"items": [...], "total": int, "skip": int, "limit": int}` 다 —
기존 RCM 규약과 동일.

**단 `GET /policies` 는 페이지네이션을 하지 않는다.** `skip` 은 항상 `0`,
`limit` 은 반환 건수와 같은 값이 들어간다(정책 수가 적어 전량 반환).

## 3. `GET /controls/{control_id}/roles` — 해석 응답

배정의 실질 소비 지점이다. 저장된 배정이 아니라 **해석 결과**를 낸다.

```json
{
  "control_id": "01a06aa1-9f33-7b81-855b-1c3eefe7ba66",
  "control_code": "PB-C",
  "process_id": "01a06aa1-9f25-7010-8eb2-cef618d0c11f",
  "owner_name": "김세영",
  "roles": [
    {"role_name": "control_owner", "user_id": "...", "user_name": "홍길동",
     "source": "process",  "source_id": "01a06aa1-9f25-7010-8eb2-cef618d0c11f"},
    {"role_name": "dept_approver", "user_id": "...", "user_name": "홍길동",
     "source": "derived",  "source_id": "01a06aa2-058e-7fc2-9368-e889946fffda"},
    {"role_name": "assessor", "user_id": "...", "user_name": "홍길동",
     "source": "control",  "source_id": "01a06aa1-9f33-7b81-855b-1c3eefe7ba66"}
  ],
  "conflicts": ["assessor=control_owner"],
  "dept_approval_skipped": false
}
```

`roles` 배열은 **항상 3건**이다 — `control_owner`, `dept_approver`, `assessor` 순서로
고정되며, 배정이 없는 역할도 `source: "none"` 으로 포함된다. 배열 길이로 분기하지 말 것.

### 3.1 `source` 4종의 의미와 판정 규칙

| `source` | 의미 | `source_id` | `user_id` |
|---|---|---|---|
| `control` | 이 통제에만 지정된 배정 | 통제 id | 배정된 사용자 |
| `process` | 상위 프로세스의 기본값 | 프로세스 id | 배정된 사용자 |
| `derived` | 통제책임자의 주 소속 부서 책임자에서 **유도** | **부서 id** | 부서 책임자 |
| `none` | 배정도 유도도 없음 | `null` | `null` |

**판정 순서 (위가 이긴다)** — `services/role_resolver.py`

1. `scope='control'` 배정이 있으면 → `control`
2. 없고 `scope='process'` 배정이 있으면 → `process`
3. 둘 다 없고 **`dept_approver` 인 경우에 한해**, 해석된 `control_owner` 의 주 소속
   부서에 책임자가 지정돼 있으면 → `derived`
4. 그 외 → `none`

**유도는 `dept_approver` 에만 적용된다.** `control_owner`·`assessor` 는 배정이 없으면
`none` 이다.

**유도 조건 3가지가 모두 성립해야 한다** — ① `control_owner` 가 해석돼 있고,
② 그 사용자에게 주 소속(`is_primary=true`)이 있고, ③ 그 부서에 `manager_id` 가 있어야 한다.
하나라도 없으면 `none` 이다.

**`source_id` 의 대상이 `source` 마다 다르다.** `derived` 일 때만 부서 id 이고
나머지는 배정 대상(통제/프로세스) id 다 — 같은 필드에 다른 종류의 id 가 들어오므로
화면에서 링크를 걸 때 `source` 를 먼저 봐야 한다.

### 3.2 `conflicts` 배열 형식

문자열 배열이며 각 항목은 **`{역할A}={역할B}` 형태로 역할명이 사전순** 정렬돼 있다
(`models/role_assignment.py:conflict_key`). 같은 조합이 두 문자열로 갈리지 않도록
순서를 고정한 것이다.

```
"assessor=control_owner"   ← control_owner = assessor 겸직
"assessor=icfr_manager"    ← assessor 가 테넌트 역할 icfr_manager 도 보유
```

**`control_owner = dept_approver` 는 여기에 나오지 않는다**(2026-09-04 정정).
충돌이 아니라 부서승인 단계 부재이며 §3.4 의 `dept_approval_skipped` 가 표시한다.

**판정은 통제 단위다.** "이 통제에서 같은 사람이 두 역할을 겸하는가"만 본다 —
사람 단위로 보면 상호 배정이 불가피한 중소기업에서 전부 걸린다(ADR-0031 §2.4).

**`derived` 로 유도된 값도 판정 대상이다.** 유도값도 실제 승인자가 되므로
`control_owner = assessor` 등 다른 조합에서는 그대로 본다. 다만
`control_owner = dept_approver` 하나만 §3.4 로 빠졌다.

`assessor=icfr_manager` 는 검사 방식이 다르다 — `icfr_manager` 는 `role_assignments`
가 아니라 `user_roles` 에 있어(ADR-0031 §3.1) 그쪽을 함께 읽는다.

### 3.3 `owner_name` 이 참고 정보인 이유

`baseline_controls.owner_name` 문자열을 **그대로** 싣는다. 계정과 연결되지 않는다.

**이관하지 않기로 한 근거는 실측이다**(2026-09-04 역할 배정 구현 착수 전 운영 DB 실측.
ADR-0031 §5 에는 미해결로 남아 있다). 운영 93건 분포:

| 유형 | 건수 | 예 |
|---|---|---|
| 단일 인물 | 71 (76%) | `김세영`, `이단비` |
| **복수 인물**(개행 구분) | **18 (19%)** | `노정희\n이단비` |
| **팀 이름** | **4 (4%)** | `솔루션사업팀` |

`유헌종\n노정희` 와 `노정희\n유헌종` 이 별개 문자열로 공존한다 — 순서 정규화조차
되어 있지 않아 계정 매핑이 불가능하다. 이관하면 RCM 문서 서술이 계정 존재 여부에
종속되고 퇴사자 발생 시 문서가 깨진다.

**용도**: "문서상 수행자: 김세영" 으로 표시해 초기 배정 힌트로 쓴다.
**배정과 어긋나면 그 자체가 검토 대상**이 된다 — 그 판단은 화면이 한다.

### 3.4 `dept_approval_skipped` — 부서승인 단계 부재

```json
"dept_approval_skipped": true
```

**통제책임자가 곧 부서 책임자일 때 `true`** 다. 부서승인은 "상급자가 검토한다"는
의미인데 통제책임자가 팀장 본인이면 그 위 단계가 없다 — **겸직이 아니라 단계가 없는
것**이므로 `conflicts` 가 아니라 이 필드로 표시한다(ADR-0031 §2.4 정정, 2026-09-04).

판정은 `services/role_resolver.is_dept_approval_skipped` 다 — 해석된
`control_owner` 와 `dept_approver` 의 `user_id` 가 같으면 `true`.
**`derived` 유래에 한정하지 않는다** — 통제별로 통제책임자 본인을 부서승인자로
명시 지정한 경우도 같은 상황이다.

**`true` 여도 `roles[]` 의 `dept_approver` 항목은 그대로 남는다.** `user_id` 가
`control_owner` 와 같은 값이며 **별도 승인자가 아니라는 뜻**이다. 화면에서
"승인자: 홍길동" 으로 렌더하면 오해를 부르므로, 이 필드가 `true` 면
"부서승인 없음(통제책임자가 부서 책임자)" 으로 표시할 것.

**`source` 에 `"skipped"` 를 넣지 않은 이유** — `source` 는 "값이 어디서 왔는가"라는
단일 의미이고 스킵은 상태다. 섞으면 RCM `source` envelope 과 개념이 어긋나고,
스킵일 때 유도된 부서 책임자가 누구인지 표현할 자리가 없어진다. 평가 워크플로
(ADR-0032 §2.3)가 읽을 값도 "이 통제에 부서승인 단계가 있는가" 라는 boolean 이라
최상위 필드가 직접적이다.

**이름이 `skipped` 인 이유** — `dept_approval_required` 로 두면 ADR-0031 §2.6 의 정책 토글
(`dept_approval_enabled`, 아직 미배선)이 꺼진 경우와 사유가 섞인다. 지금 표현하는
것은 "통제책임자 = 부서 책임자" 한 가지뿐이므로 이름을 좁게 뒀다.

## 4. 이해상충 409 흐름

`POST /api/org/assignments` 는 **저장 후 상태를 미리 계산해** 충돌을 본다
(저장하고 되돌리지 않는다).

### 4.1 사유 없음 — 409, 재요청 유도

```
HTTP 409
{"detail": "겸직 조합이 발생합니다(assessor=control_owner). 사유를 입력해야 저장할 수 있습니다"}
```

발생한 조합이 **`detail` 안에 괄호로 나열**된다(복수면 `, ` 로 구분).

**재요청 흐름** — 같은 바디에 `conflict_reason` 만 추가해 다시 `POST` 한다.

```json
{"scope": "control", "target_id": "...", "role_name": "assessor", "user_id": "...",
 "conflict_reason": "인원 4명으로 분리 불가. 상급자 검토로 보완"}
```

→ `201`. 배정이 저장되고 **사유가 `conflict_acknowledgements` 에 이력으로 남는다.**
조합이 여러 개면 조합마다 1건씩 기록된다. 배정이 나중에 바뀌어도 지우지 않는다 —
감사에서 "그때 왜 겸직을 허용했는가" 를 물으면 이 기록이 답이다(보완통제 증적).

### 4.2 정책 금지 — 409, 재요청해도 막힘

```
HTTP 409
{"detail": "정책상 금지된 겸직 조합입니다: assessor=control_owner"}
```

**`conflict_reason` 이 있어도 거부된다.** 사유로 우회할 수 없다.

### 4.3 두 응답의 구분

둘 다 409 이므로 **`detail` 문구로 구분해야 한다.**

| 상황 | 구분 문자열 | 화면 처리 |
|---|---|---|
| 사유 필요 | `"사유를 입력해야"` | 사유 입력 모달 → 재요청 |
| 정책 금지 | `"정책상 금지"` | 저장 불가 안내. 재요청 경로 없음 |

**문자열 매칭이라 백엔드 문구가 바뀌면 깨진다.** 구분용 코드 필드는 현재 계약에 없다 —
필요하면 별도 요청 대상이다.

**충돌은 저장 전에 미리 볼 수 없다.** 조회 전용 판정 엔드포인트가 없으므로,
사유 입력 UI 는 첫 `POST` 의 409 를 받은 뒤에 띄우는 흐름이 된다.

## 5. 권한

### 5.0 `GET /api/auth/me` — FE 가 권한을 판정하는 자리

**`external_auditor` 를 FE 가 판정할 소스가 여기다.** 이전에는 `/me` 가
`UserTenantAccess` 만 조회해 `require_write` 의 판정 근거(`user_roles`)가 응답
어디에도 없었다.

```json
{
  "id": "...", "email": "...", "display_name": "...",
  "role": "admin",
  "tenants": [{"id": "...", "name": "사이냅소프트", "code": "DEFAULT", "role": "admin"}],
  "active_tenant_id": "d0000000-0000-0000-0000-000000000001",
  "tenant_roles": ["assessor", "icfr_manager"],
  "can_write": true
}
```

**`role` 이라는 이름이 세 곳에서 다른 의미다.** 섞으면 권한 판정이 틀어진다.

| 필드 | 출처 | 의미 | 판정에 쓰는가 |
|---|---|---|---|
| `role` | `users.role` | **시스템 관리 권한** | `require_admin` 전용(사용자 CRUD 4곳) |
| `tenants[].role` | `user_tenant_access.role` | 테넌트 **접근** 권한 | **아니오** — 판정 코드 0건(`ClaudeICFR.md` 13.9-23) |
| **`tenant_roles`** | **`user_roles`** | **제도 운영 역할**(ADR-0031 §2.1) | **예** |

**`tenant_roles`·`can_write` 는 활성 테넌트 기준이다.** `active_tenant_id` 와 같은
맥락이라 함께 top-level 에 있다. `tenants[]` 안에 넣지 않은 이유 — 테넌트마다 활성
컨텍스트를 바꿔가며 `user_roles` 를 읽어야 하는데, 그것은 ADR-0025 자동 격리가
막으려던 수동 교차 조회다.

활성 테넌트는 `X-Tenant-Id` 헤더로 정해진다(접근 테넌트가 1개면 자동 수렴).
헤더를 바꾸면 `active_tenant_id`·`tenant_roles`·`can_write` 가 함께 따라간다 —
A사에서 `external_auditor` 인 사람이 B사에서는 아닐 수 있다.

**FE 사용 규칙 — 두 값의 역할이 다르다.**

- **버튼 숨김·비활성은 `can_write`.** `tenant_roles` 로 직접 판정하지 말 것.
  `can_write` 는 백엔드 `core/permissions.can_write` 가 낸 값이고 `require_write` 와
  **같은 함수**다. FE 가 규칙을 다시 구현하면 조건이 늘 때 어긋난다
  (회차 상태별·통제 단위·정책 토글·증빙 편집 권한이 계속 추가되고 있다).
- **안내 문구는 `tenant_roles`.** `can_write` 만으로는 "왜 못 쓰는지"를 설명할 수 없다.
  예: `tenant_roles` 에 `external_auditor` 가 있으면 "외부감사인은 조회만 가능합니다".

`can_write=false` 인 상태로 쓰기 API 를 호출하면
`403 {"detail": "외부감사인은 조회만 가능합니다"}` 가 온다. `can_write` 는 그 403 을
미리 아는 수단이지 우회 수단이 아니다 — 서버가 최종 판정한다.

### 5.1 엔드포인트별 요구 권한

| 엔드포인트 | 가드 | 요구 |
|---|---|---|
| 모든 `GET` | `CurrentUser` | 인증만 |
| **부서 `POST`/`PATCH`/`DELETE`** | **`require_icfr_manager`** | **`icfr_manager` 보유 (§5.4)** |
| **소속 `POST`/`PATCH`/`DELETE`** | **`require_icfr_manager`** | **〃** |
| 배정 `POST`/`DELETE` | `require_write` | 〃 |
| **정책 `PUT`** | **`require_icfr_manager`** | **`icfr_manager` 보유** |
| **테넌트 역할 `POST`/`PATCH`/`DELETE`** | **`require_role_assigner`** | **`icfr_manager` 보유 (§5.3)** |

**`users.role`(시스템 관리 권한)은 이 API 들에서 검사하지 않는다.** `require_admin` 은
사용자 CRUD 4곳 전용이며 제도 운영 권한과 서로 참조하지 않는다(ADR-0031 §3.2).
`users.role == "admin"` 계정이 자동으로 `icfr_manager` 가 되지 않는다.

### 5.2 `external_auditor` 거부 위치

`app/core/permissions.py` 의 **`require_write` 의존성 한 곳**에서 이뤄진다.
엔드포인트마다 검사를 두면 한 곳만 빠뜨려도 뚫리므로 의존성으로 모았다.

판정 소스는 **`user_roles`**(테넌트 단위 역할)이며 `AuditedBase` 자동 격리로
활성 테넌트의 역할만 읽는다.

```
HTTP 403
{"detail": "외부감사인은 조회만 가능합니다"}
```

조회는 그대로 `200` 이다. **`external_auditor` 는 어떤 활동도 생성·수정하지 않는다**
(ADR-0031 §2.1) — 외부감사인이 평가 데이터를 고칠 수 있으면 그 자체가 독립성 훼손이다.

`icfr_manager` 미보유 시 정책 변경:

```
HTTP 403
{"detail": "내부회계관리자 권한이 필요합니다"}
```

### 5.4 조직 구조 쓰기 권한 (2026-09-19, 4-2)

**부서·소속의 생성·수정·삭제는 `icfr_manager` 전용이다.** 3-1 이 `require_write` 로 둔 것은
누락이었다 — 그러면 `external_auditor` 만 막히고 **일반 사용자가 부서를 만들 수 있었다**
(실측 201). 조직도는 제도 운영의 기준 데이터다: 통제책임자의 주 소속이 부서승인 단계를
정한다(ADR-0031 §2.3).

```
HTTP 403
{"detail": "내부회계관리자 권한이 필요합니다"}
```

**조회는 인증만이다.** 대시보드 조직별 집계(`GET /api/rcm/summary`)와 부서 화면이 부서를
읽어야 하고, 조직도 열람 자체를 막을 이유가 없다 — `external_auditor` 도 목록 조회는 200 이다.

**`sys_admin` 도 막힌다.** 제도 활동에 참여하지 않는다(ADR-0031 §2.1.1) — 실측 403.

### 5.5 지웠다가 다시 만들기 (2026-09-19, 4-2)

부서명·소속 짝·주 소속 유니크가 **살아 있는 행만** 대상으로 바뀌었다(마이그레이션 `e7f8a9b0c1d2`).
그 전에는 소프트 삭제된 행이 값을 계속 점유해 아래가 전부 409 였고, 문구가
`데이터 무결성 제약 위반 (중복 또는 참조 오류)` 이라 **사용자가 원인을 알 수 없었다.**

| 동작 | 지금 |
|---|---|
| 부서 삭제 후 같은 이름으로 재생성 | **201** |
| 소속 해제 후 같은 부서에 재추가 | **201** |
| 주 소속 해제 후 다른 부서 주 소속 지정 | **201** |

살아 있는 중복은 앱 레벨 문구가 그대로 나온다 — `부서명 '자금팀' 은 이미 사용 중입니다`,
`이미 해당 부서에 소속되어 있습니다`.

### 5.6 주 소속은 거부가 아니라 이동이다

이미 주 소속이 있는 사람을 다른 부서의 주 소속으로 지정하면 **201 이고 기존 주 소속이
해제된다**(소속 자체는 남는다). 부서 이동이 정상 업무이므로 "이미 주 소속이 있습니다"로
막지 않는다. 화면은 지정 전에 `기존 주 소속 「○○」에서 옮겨집니다` 를 보여준다.

### 5.3 테넌트 역할 배정 — 권한과 허용 값 (2026-09-16)

`/api/users/roles` 의 생성·수정·삭제가 **로그인만 확인하던 상태를 고친 것**이다.
일반 사용자가 자기에게 `icfr_manager` 를 부여하거나 `external_auditor` 가 자기 역할
행을 지워 조회 전용을 벗어나는 것이 실측으로 재현됐다(`ClaudeICFR.md` 13.9-35).
**`require_write`·`require_icfr_manager` 가 보는 테이블이 여기라서** 이 경로가 뚫리면
두 가드가 함께 무력화된다.

**세 경로 모두 `icfr_manager` 다.** 배정만 막으면 삭제로 우회된다.

```
HTTP 403
{"detail": "역할 배정은 내부회계관리자만 가능합니다 (내부회계관리자가 없는 테넌트에 한해 시스템관리자가 첫 배정을 합니다)"}
```

**부트스트랩 예외** — 테넌트에 `icfr_manager` 가 0명일 때만 `user_roles` 의
`sys_admin` 이 배정할 수 있고, 1명이 생기면 닫힌다(ADR-0031 §3.3).
`users.role == "admin"` 은 여기서 보지 않는다(ADR-0031 §3.2).

**허용 값은 5종뿐이다** — `icfr_manager`/`ceo`/`auditor`/`external_auditor`/`sys_admin`.
목록 밖 값은 **422**(스키마 단계에서 거부):

```
HTTP 422
{"detail": [{"type": "value_error", "loc": ["body", "role_name"],
             "msg": "Value error, 허용되지 않는 역할명 'icfr_mananger'. 허용: icfr_manager, ceo, auditor, external_auditor, sys_admin"}]}
```

**구 3역할(`Administrator`/`Reviewer`/`Tester`)은 읽기만 된다.** 기존 행은 `/me`
`tenant_roles` 와 목록 조회에 그대로 나오지만 신규 배정은 422 로 막힌다
(`ClaudeICFR.md` 13.9-24). **FE `ROLE_NAME_OPTIONS` 가 아직 구 역할명 7종이라
화면에서는 5역할을 만들 수 없고 기존 선택지는 전부 422 가 된다** — FE 수정 전까지
역할 배정은 API 로만 가능하다.

**같은 사용자·역할 중복 배정은 409.**

```
HTTP 409
{"detail": "이미 'ceo' 역할이 배정되어 있습니다"}
```

DB 부분 유니크 인덱스(`uq_user_roles_active_pair`)가 최종 보장이며 **살아 있는 행만
대상**이라 해제 후 재배정은 정상 동작한다.

## 6. 기존 RCM 규약과 다른 지점

**아래 4건을 제외하면 차이 없음 — 단언한다.** 목록 봉투, 404
`{"detail": "..."}`, 409 한국어 메시지, `PATCH` 의 `exclude_unset` 판별,
409 를 DB 제약에 맡기지 않고 핸들러에서 명시 검증하는 방식까지 동일하다.

**① 배정에 `PATCH` 가 없다 — `POST` 가 생성과 교체를 겸한다.**
같은 `(scope, target_id, role_name)` 이 있으면 `user_id` 만 바꾼다. RCM 은
`POST`(생성)와 `PATCH`(수정)가 분리돼 있다. **의도된 차이다** — 배정은
"이 자리에 누구" 하나뿐이라 부분 수정이라는 개념이 없다.

**② 해석 응답이 `source` envelope 이 아니라 `roles[].source` 다.**
RCM 은 항목마다 `source`/`baseline_id`/`is_overridden` 3필드가 flat 으로 붙는다.
여기는 통제 1건 안에 역할 3건이 있고 **각 역할이 자기 출처를 가진다.**
개념은 같으나(어디서 온 값인지 표시) 구조가 다르므로 **RCM 어댑터를 재사용할 수 없다.**
`source` 값 집합도 다르다 — RCM 은 `baseline`/`tenant`, 여기는
`control`/`process`/`derived`/`none`.

**③ 정책 목록은 페이지네이션하지 않는다.** 봉투 형태는 같으나 `skip`/`limit` 이
요청과 무관하게 채워진다.

**④ 낙관적 잠금이 없다 — RCM 과 같다.** 차이가 아니라 **같은 미비점**이다.
`row_version` 컬럼은 있으나 요청·응답 어디에도 없다. 동시 편집 시 마지막 쓰기가
이긴다(`ClaudeICFR.md` 13.9-18).

## 7. 알아둘 동작 3건

- **부서 삭제는 소속 인원이 남아 있으면 409 다.**
  `{"detail": "소속 인원 1명이 남아 있어 삭제할 수 없습니다. 소속을 먼저 정리하세요"}`
  소속만 남으면 어느 부서인지 알 수 없기 때문이다.
- **부서를 자기 자신의 상위로 지정하면 409 다.**
  `{"detail": "부서를 자기 자신의 상위로 지정할 수 없습니다"}` — `PATCH` 에서 검사한다.
  `parent_id` 는 초기 전부 NULL 이라 현재는 닿지 않는 경로다.
- **배정 `target_id` 는 존재 검증을 받는다.** 없는 대상이면
  `404 {"detail": "Control not found"}` (또는 `"Process not found"`).
  DB FK 로 막을 수 없어(정체성 id 가 두 테이블에 걸친다) 핸들러가 resolver 결과와
  대조한다. **RCM 상위 계층이 존재하지 않는 상위 id 를 조용히 통과시키는 것과 다르다**
  — 이쪽은 막는다.
