# ICFR 2-B-4 — Resolver 계층 확장 + source envelope (갱신본)

- **작성일**: 2026-07-16 (source envelope 반영 갱신)
- **근거**: ADR-0027, 2-B-1/2/3/3.5 후속. **2-B의 마지막 단계.** Regina FE 피드백 ② 통합.
- **Tier**: Tier 2 (핵심 병합 로직 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화 — 병합만 명시적 공통 함수. 모든 회사 유연 적용, 고정 코딩 0.

---

## 0. 목표

구조(baseline 5 + instance 4 + junction 2 + baseline_version)는 2-B-1~3.5로 다 섰다. 이제 그 구조를 **실제로 병합해 쓰는 로직**을 완성한다. 완료되면 2-A-3(조회 전환)의 선행조건이 모두 해소된다.

해결할 6가지:
1. 상위 계층 resolve (process/sub_process/risk)
2. cascade — 상위 exclude 시 하위 자동 제외
3. 어서션 병합 (baseline − remove + add)
4. **2-B-2 부채 정리** — risk_instance_id 참조가 baseline으로 임시 매핑됨
5. 관계 필드 (process_code / sub_process_code / risk_level)
6. **source envelope** — 전 계층 공통 규약 (Regina 피드백 ②)

**본 단계는 resolver 로직까지.** API 전환은 2-A-3, CRUD는 2-A-4.

---

## 1. 핵심 원리 — 정체성 id 통일

현 resolver 규칙: **baseline 유래 행(adopt/override)의 id = baseline id, add 행의 id = instance id.** 통제 정체성은 표준 쪽이며 override는 필드만 덮은 것이라 정체성이 안 바뀐다.

**이 규칙을 계층 전체에 통일:**
- resolved 항목의 **id** = 정체성 id
- resolved 항목의 **상위 참조 id**도 정체성 id
  - `<상위>_baseline_id` 있으면 → 그 baseline id
  - `<상위>_instance_id` 있으면 → 그 instance id
  - 둘 다 NULL(baseline 상위 따름) → baseline 항목의 원래 상위 id

**결과**: 정체성 id 기반 dict lookup 체인으로 4계층 연결. 조인 아닌 메모리 lookup(Python 병합).

---

## 2. source envelope — 전 계층 공통 규약 (Regina 피드백 ②)

resolved 항목마다 **다음 메타 필드를 전 계층 공통으로** 실어, 프론트가 단일 라우팅으로 처리하게 한다:

| 필드 | 의미 |
|------|------|
| `id` | 정체성 id (1절) |
| `source` | `"baseline"` \| `"tenant"` — baseline 유래(adopt/override) vs 회사 add |
| `baseline_id` | baseline 유래면 그 baseline id, add면 `null` |
| `is_overridden` | override instance가 적용됐으면 `true`, adopt/add면 `false` |

**규약**:
- adopt → source=baseline, baseline_id=그 id, is_overridden=false
- override → source=baseline, baseline_id=그 id, **is_overridden=true**
- add → source=tenant, baseline_id=null, is_overridden=false
- **process/sub_process/risk/control 전 계층 동일**. 계층마다 다르면 프론트 라우팅이 갈라진다(피드백 ② 취지).

이 envelope은 **2-A-4 CRUD 전환의 라우팅 기반**이기도 하다 — 프론트가 편집·삭제 시 source로 baseline 대상인지 instance 대상인지 판별. Q2(id 이원화)의 최종 답이 이 envelope이다.

어서션 항목에는 envelope 미적용(코드 배열이라 항목 단위 편집 대상 아님). 통제·계층 항목에만 적용.

---

## 3. 상위 계층 resolve 함수

`resolve_controls`와 동일 패턴 3개 추가:
- `resolve_processes(db)` / `resolve_sub_processes(db)` / `resolve_risks(db)`

각각: baseline 로드 → instance 로드(활성 tenant 자동 필터, **tenant 인자 없음**) → exclude 제거 → override 병합(NULL=baseline, False는 유효 override) → add 추가 → **상위 참조·source envelope 정체성 id로 채움**.

기존 `resolve_controls` 구조·주석 스타일 유지.

---

## 4. Cascade — 상위 exclude 전파

**규칙: 상위 exclude면 하위 자동 제외.** instance 행 안 만듦.

process → sub_process → risk → control 순:
1. resolve_processes → 살아남은 정체성 id `alive_processes`
2. resolve_sub_processes → 자체 exclude 아니고 상위가 `alive_processes`에 있는 것 → `alive_sub_processes`
3. resolve_risks → 상위가 `alive_sub_processes`에 → `alive_risks`
4. resolve_controls → risk_id가 `alive_risks`에

> **주의**: control의 risk_id가 NULL이면 cascade에서 제외하지 말 것 (이관 전이라 risk 없는 통제 존재 가능). **risk_id가 있는데 그 risk가 죽었을 때만** 제외.

cascade 규칙 docstring 명시.

---

## 5. 2-B-2 부채 정리 (필수)

현재:
```python
row["risk_id"] = inst.risk_baseline_id   # instance 참조 무시
```
정체성 id 규칙으로 정리:
- `risk_baseline_id` 있으면 → 그 값
- `risk_instance_id` 있으면 → 그 값 (add한 risk 정체성 id)
- 둘 다 NULL → baseline의 risk_id

add 행도 동일. 이 부채 남으면 이관 후 틀린 값.

---

## 6. 어서션 병합

```
통제별 어서션 = baseline_control_assertions(통제)
                − control_assertion_instances(remove)
                + control_assertion_instances(add)
```
- 대상 통제 매칭은 **정체성 id**로
- 결과는 코드 배열 `["E","C","V"]` (`baseline_risk_categories.code`) — 기존 `ControlSearchOut.assertions`와 동일 형태
- add 통제의 어서션은 전부 add 행

---

## 7. 관계 필드 (2-A-3 선행조건)

resolved control에 채움 (`api/rcm.py:331-340`의 조인을 lookup 체인으로):
- `risk_level` = resolved risk의 assessment_level
- `sub_process_code` = 그 risk 상위 resolved sub_process의 code
- `process_code` = 그 sub_process 상위 resolved process의 code
- `assertions` = 6절

상위 없거나 못 찾으면 None. 기존 `ControlSearchOut`(`schemas/rcm.py:180-188`) 필드명·타입 일치.

> resolve_controls가 항상 채울지 별도 함수로 둘지는 구현 시 판단·보고 (목록은 관계 필드 포함, 상세는 분리 사용).

---

## 8. 완료 기준

- [ ] resolve_processes / sub_processes / risks (4 action 병합, tenant 인자 없음)
- [ ] 정체성 id 규칙 계층 전체 통일 (상위 참조도 정체성 id)
- [ ] **source envelope (id/source/baseline_id/is_overridden) 전 계층 공통**
- [ ] cascade (risk_id NULL 통제는 제외 안 함)
- [ ] 2-B-2 부채 정리 — risk_instance_id resolve
- [ ] 어서션 병합 → 코드 배열
- [ ] 관계 필드 process_code/sub_process_code/risk_level
- [ ] 테스트 (촘촘히):
  - 각 계층 4 action
  - cascade: process exclude → 하위 전부 사라짐
  - add risk 밑 add 통제 → risk_id가 instance id로 resolve
  - 어서션: baseline 2개 중 1 remove + 1 add
  - 관계 필드: baseline 체인 / add 체인 / 혼합
  - **source envelope: adopt/override/add 각각 source·baseline_id·is_overridden 정확**
  - override된 상위 밑 통제 → 상위 정체성 baseline 유지
  - tenant 격리
- [ ] pytest 전체 통과 (기존 105 회귀 없음)

완료 후 `docker compose up -d --build backend` 재빌드. **controls count=95 확인**. config.py admin_password 건드리지 말 것. **API·기존 테이블 건드리지 말 것**(2-A-3 범위).

---

## 작업 전 확인 (Claude Code 먼저 수행)

- `services/control_resolver.py` 현재 구조
- `models/rcm_baseline.py` 이중 FK 필드명
- `schemas/rcm.py:180-188` ControlSearchOut 필드명·타입
- `api/rcm.py:331-340` 기존 관계 필드 채우는 방식 (동일 결과)

---

ICFR_rcm_baseline_2b4_20260716.md 진행해줘
