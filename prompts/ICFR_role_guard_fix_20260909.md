# 13.9-35 수정: 역할 배정 API 권한 가드·값 검증

작성일: 2026-09-09
근거: ADR-0031(역할·권한 모델) §2.1·§2.1.1·§3.1·§3.2
발견: 3-3 후속 조사(Regina의 역할 UI 착수 전 확인 요청)

---

## 0. 이 작업의 성격 — 보안 결함 수정

**권한 체계가 통째로 뚫려 있다.** 실제 호출로 확인된 상태다.

- 일반 사용자가 자기에게 `icfr_manager`를 부여한 뒤 정책 변경 200
- `external_auditor`가 자기 역할 행을 삭제(204)하면 `can_write=true`
- 오타 `icfr_mananger`도 201로 저장되어 조용히 무효가 됨

`require_write`(외부감사인 조회 전용)와 `require_icfr_manager`(정책 변경) 두 가드가
모두 무력화된다. 3-3 후속 작업보다 우선한다.

## 1. 원인

3-1에서 "CRUD와 화면이 이미 있다"는 이유로 `user_roles` 재사용을 결정했으나
(ADR-0031 §3.1), **그 CRUD가 새 용도에 맞는지 점검하지 않았다.**

- `api/user_mgmt.py:122·139·151` — 생성·수정·삭제 모두 로그인만 확인
- 관련 테스트가 전부 DB 직접 삽입 방식이라 API 경로가 한 번도 검증되지 않았다

## 2. 결정 사항

### 2.1 배정 권한은 `icfr_manager`

제도 운영 역할은 제도 책임자가 배정한다.

**배정·수정·삭제 전부 `icfr_manager`만 가능하다.**
배정만 막으면 `external_auditor`가 자기 역할 행을 삭제해
조회 전용을 벗어나는 구멍이 남는다(13.9-35 ②).
`api/user_mgmt.py:122·139·151` 세 곳 모두에 가드를 건다.

**`sys_admin`이나 `require_admin`(users.role)으로 막지 않는다.**
- ADR-0031 §2.1.1 — `sys_admin`은 제도 활동에 참여하지 않는다
- ADR-0031 §3.2 — `users.role`(시스템 관리)과 `user_roles`(제도 운영)는
  다른 것이며 서로 참조하지 않는다

### 2.2 첫 `icfr_manager`는 부트스트랩 조건으로 생성한다

닭과 달걀 문제가 있다. 운영에 `icfr_manager` 보유자가 0명이며,
`icfr_manager`만 배정할 수 있게 하면 아무도 첫 배정을 할 수 없다.

**해법 — 테넌트에 `icfr_manager`가 0명일 때만 `sys_admin`이 배정할 수 있다.**

- 한 명이라도 존재하면 그 뒤로는 `icfr_manager`만 배정 가능
- `sys_admin`이 제도 운영에 참여하는 것이 아니라 **초기 셋업만** 하는 것이며,
  그 사실이 조건으로 코드에 명시된다. ADR-0031 §3.2 경계가 유지된다
- 이 조건을 코드 주석과 ADR에 남길 것. 왜 예외가 있는지 근거 없이 남으면
  나중에 "sys_admin도 제도 역할을 배정한다"로 잘못 읽힌다

### 2.3 허용 값 목록을 검증한다

**신규 배정은 ADR-0031 5역할만 허용한다.**
`icfr_manager` / `ceo` / `auditor` / `external_auditor` / `sys_admin`

- 목록 밖 값은 거부(422 또는 400 — 기존 규약 확인 후 결정)
- 오타가 201로 통과해 조용히 무효가 되는 상태를 막는다

**구 3역할(`Administrator`/`Reviewer`/`Tester`)은 읽기 허용, 신규 배정 금지.**
- 기존 데이터를 깨지 않으면서 확산을 막는다
- 구 3행 정리는 별건(ClaudeICFR.md 13.9-24)

**값 목록은 한 곳에만 정의한다.** 3-1에서 `role_resolver`·`permissions.py`에
역할 상수가 이미 있는지 확인하고, 있으면 그것을 참조할 것. 새로 만들지 말 것.

### 2.4 중복 배정을 막는다

같은 사용자·역할이 2행 저장되어, 1행을 지워도 역할이 남는다.

`(tenant_id, user_id, role_name)` 유니크 제약을 추가한다.
**마이그레이션 전에 기존 중복 데이터를 확인할 것.** 중복이 있으면
제약 추가가 실패한다. 실데이터 정리가 필요하면 마스터가 직접 실행한다.

### 2.5 FE 드롭다운은 이번 범위 밖

`types.ts`의 `ROLE_NAME_OPTIONS`가 구 역할명 7종이다.
화면에서 "외부감사인"을 고르면 `ExternalAuditor`가 저장되어 조회 전용이 걸리지 않는다.

**백엔드가 값 검증을 하면 이 경로는 422로 막힌다.** 화면이 깨지는 것이 아니라
잘못된 값이 저장되지 않게 된다. FE 수정은 Regina가 역할 UI 작업 시 처리한다.

이 사실을 Regina에게 알려야 하므로 완료 보고에 명시할 것.

## 3. 사전 실측 (STEP 0)

```bash
# 3-1. 현재 권한 가드 상태
sed -n '110,160p' backend/app/api/user_mgmt.py

# 3-2. 역할 상수가 이미 정의돼 있는지
grep -rn "ROLE_\|icfr_manager\|external_auditor" backend/app/core/permissions.py | head -20

# 3-3. 기존 user_roles 데이터 — 중복 여부
docker compose exec postgres psql -U icfr -d icfr_db -c \
  "SELECT user_id, role_name, count(*) FROM user_roles GROUP BY 1,2 HAVING count(*) > 1;"

# 3-4. 기존 role_name 값 분포
docker compose exec postgres psql -U icfr -d icfr_db -c \
  "SELECT role_name, count(*) FROM user_roles GROUP BY 1;"

# 3-5. require_icfr_manager 구현 위치
grep -rn "require_icfr_manager" backend/app/ | head

# 3-6. alembic head
cd backend && alembic current
```

**보고할 것**
- 역할 상수 정의 위치 (있으면 재사용, 없으면 어디에 둘지 판단 + 근거)
- 로컬·운영 `user_roles` 중복 유무
- 거부 상태코드를 422로 할지 400으로 할지 — 기존 규약 확인 후 판단
- `require_icfr_manager`를 그대로 쓸 수 있는지

**운영 데이터 확인은 마스터가 실행한다.** 명령만 제시할 것.

## 4. 검증 조건

1. 일반 사용자가 자기에게 `icfr_manager` 부여 시도 → 거부
2. `external_auditor`가 자기 역할 행 삭제 시도 → 거부
3. `icfr_manager`가 다른 사용자에게 역할 배정 → 성공
4. **테넌트에 `icfr_manager`가 0명일 때 `sys_admin`이 배정 → 성공**
5. **`icfr_manager`가 1명 이상일 때 `sys_admin`이 배정 시도 → 거부**
6. 목록 밖 값(`icfr_mananger` 오타) 배정 시도 → 거부
7. 구 역할명(`Administrator`) 신규 배정 시도 → 거부
8. 구 역할명이 이미 있는 계정의 `/me` 조회 → 정상 동작 (읽기는 허용)
9. 같은 사용자·역할 중복 배정 시도 → 거부
9-1. `icfr_manager`가 아닌 사용자가 **다른 사람의 역할을 수정** 시도 → 거부
9-2. **자기 역할 행을 삭제** 시도 → 거부 (역할 종류 무관)
10. 전체 pytest 통과. **2회 반복 실행으로 재현성 확인**

**1·2번이 이 작업의 목적이다.** 4·5번은 §2.2 부트스트랩 조건이 구현됐는지 본다.
5번이 없으면 `sys_admin`이 상시 배정 가능한 구현으로도 통과한다.

**API 경로로 검증할 것.** DB 직접 삽입으로는 이번 결함이 검증되지 않는다 —
그것이 애초에 이 결함을 놓친 원인이다.

## 5. 문서

- ADR-0031 §3에 배정 권한 결정 추가. 부트스트랩 예외의 근거를 함께 기록
- `docs/api/org-contract.md`에 `/api/users/roles` 권한·허용값 추가
- ClaudeICFR.md 13.9-35 해소 처리. §14 변경로그

**13.9-24(구 3행 의미 불명)와의 관계를 명시할 것.**
읽기 허용으로 당장은 깨지지 않으나 정리는 여전히 필요하다.

## 6. 커밋 분리

파일 구성에 맞춰 나눌 것. 최소한 아래는 분리한다.
- 마이그레이션(유니크 제약)
- 권한 가드·값 검증
- 테스트
- 문서

## 7. push 정책

**로컬 커밋까지. push 대기.**
마이그레이션이 포함되므로 마스터가 백업 후 직접 push한다.
`alembic/versions/` 신규 파일이 있으면 push하지 않고 보고한다(CLAUDE.md §8.3).
