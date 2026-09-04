# 3-2: 평가 회차 + 워크플로 (ADR-0032 §2.1~2.6)

작성일: 2026-09-04
근거 ADR: ADR-0032(평가 회차·워크플로), ADR-0031(역할·권한), ADR-0030(테넌트 소유권), ADR-0025(자동 격리), ADR-0020(제로 추상화)
선행: 3-1(부서·역할 배정) — 완료, 운영 배포됨(99c332a)
후속: 3-3 증빙(ADR-0032 §2.7)

---

## 1. 범위

**포함**
- 통제 평가주기 속성 (baseline 기본값 + overlay 변경)
- 테넌트 설정에 회계연도 시작월 추가
- 평가 회차 생성·조회 (설계평가 / 운영평가 독립)
- 활동 기록 (설계·설계변경·테스트·평가)
- 승인 (부서승인·평가자승인·최종승인)
- 회차 마감 (미완 사유 포함)
- 위 전부의 CRUD API

**제외**
- 증빙 → 3-3. 회차·활동 기록만 만들고 파일은 다루지 않는다
- 미비점(deficiency) 관리 → 개선계획 모듈 설계 시
- 표본 추출 → Test 모듈 설계 시
- 아카이브 → 별도 ADR

## 2. 설계 확정 사항

### 2.1 평가주기

**baseline에 기본값, overlay에서 변경.** RCM의 override와 같은 패턴이다.

- 값: `weekly` / `monthly` / `quarterly` / `semiannual` / `annual`
- **일 단위는 지원하지 않는다**(ADR-0032 §2.1). 최소 단위는 주다
- `baseline_controls`에 기본 주기를 둔다. 기존 93건에 값을 채워야 하므로
  마이그레이션에서 기본값을 정할 것 — **어떤 값으로 채울지 판단하고 근거를 보고할 것**
- `control_instances`에서 override 가능. 기존 override 필드 집합에 추가하는 방식을 따를 것
  (`_OVERRIDE_FIELDS`가 `ControlUpdate.model_fields`에서 파생되는 구조 확인)

**조회는 resolver를 거친다.** 통제 조회 시 유효 주기가 나와야 한다.

### 2.2 회계연도 시작월

테넌트 설정(`tenant_policies` 또는 별도)에 회계연도 시작월을 둔다.

- 값: 1~12. 기본값 1(1월 결산)
- 용도: 회차 기간 기본값 제안. 3월 결산 회사면 1분기가 4/1~6/30으로 제안된다
- **자동 계산을 강제하지 않는다.** 제안값일 뿐이며 담당자가 조정할 수 있다

Report 모듈에서도 쓸 값이므로 정책 테이블에 두는 것이 자연스러운지 판단하고 보고할 것.

### 2.3 평가 회차

```
평가 회차
  kind            design | operation   (설계평가 / 운영평가)
  frequency       weekly | monthly | quarterly | semiannual | annual
  name            표시명 (예: "2026년 1분기 운영평가")
  period_start    평가 대상 기간 시작
  period_end      평가 대상 기간 종료
  due_date        마감기한 (nullable)
  status          진행 중 | 마감됨 | 최종승인됨
```

- **생성 주체는 `assessor`(전담부서)다.** 통제책임자는 생성할 수 없다
- **설계평가 회차와 운영평가 회차는 독립이다.** 서로 참조하지 않으며 동시에 열 수 있다
- **대상 통제는 자동으로 묶인다.** 회차의 `frequency`와 일치하는 유효 주기를 가진
  통제가 대상이 된다. 통제를 하나씩 고르지 않는다
- `due_date`는 nullable. 평가 대상 기간과 다른 개념이다 —
  기간은 "언제를 평가하는가", 마감기한은 "언제까지 작업하는가"

**대상 통제를 회차 생성 시점에 스냅샷으로 고정할지, 조회 시점에 계산할지 판단할 것.**
주기가 나중에 바뀌면 대상이 달라지는데, 이미 평가가 진행된 회차의 대상이
사후에 바뀌면 안 된다. 판단 근거를 보고할 것.

### 2.4 활동 기록

| 활동 | 수행 주체 | 회차 종류 |
|---|---|---|
| 설계 / 설계변경 | `control_owner` | design |
| 설계평가 | `assessor` | design |
| 테스트(자체점검) | `control_owner` | operation |
| 운영평가 | `assessor` | operation |

각 기록에 **수행자와 수행 시각**을 남긴다(ADR-0032 §2.8).
역할 배정 이력은 관리하지 않는다. 수행 기록에 수행자가 남으면 충분하다.

**권한 검사는 통제 단위다.** "이 사람이 평가자인가"가 아니라
"이 통제에서 이 사람이 평가자인가"를 본다. 3-1의 `role_resolver`를 사용할 것.

### 2.5 승인

| 단계 | 승인자 | 비고 |
|---|---|---|
| 부서승인 | `dept_approver` | 정책 토글로 on/off. `dept_approval_skipped`면 자동 통과 |
| 평가자 승인 | `assessor` | 설계·설계변경에 대해 |
| 최종승인 | `icfr_manager` | **회차 전체에 대해.** 개별 통제가 아님 |

**`dept_approval_skipped`가 true인 통제는 부서승인 단계를 건너뛴다**(3-1에서 확정).
정책 토글 `dept_approval_enabled`가 false면 전체 스킵이다. 두 경로를 구분해 처리할 것.

### 2.6 회차 마감

- **마감 단위는 회차다.** 통제 단위 마감은 두지 않는다
- **미완 통제가 있어도 마감할 수 있다.** 단 미완 사유 입력이 필수다
- 마감 시 미완 통제 목록을 응답으로 제시한다
- 미완 내역은 회차 기록에 보존된다

사유 없이 마감 시도 → 거부. 미완 목록과 함께 사유를 요구한다.
3-1의 이해상충 처리(409 + 사유 재요청)와 같은 흐름을 따를 것.

### 2.7 최종승인

마감된 회차에 대해 `icfr_manager`가 최종승인한다.
승인 시점과 승인자를 기록한다. 승인 후 대표자·이사회 보고 절차로 넘어간다
(보고 모듈은 별건).

**마감되지 않은 회차는 최종승인할 수 없다.**

## 3. 사전 실측 (STEP 0)

**스키마와 기존 구조를 추정하지 않는다.**

```bash
# 3-1. control override 필드 집합이 어떻게 파생되는지
grep -n "_OVERRIDE_FIELDS\|ControlUpdate" backend/app/api/rcm.py | head -20

# 3-2. tenant_policies 실제 구조
docker compose exec postgres psql -U icfr -d icfr_db -c "\d tenant_policies"

# 3-3. role_resolver 인터페이스 — 3-2에서 권한 검사에 쓸 함수
sed -n '1,60p' backend/app/services/role_resolver.py

# 3-4. 3-1이 만든 권한 가드
grep -n "require_write\|def require" backend/app/core/permissions.py backend/app/core/deps.py

# 3-5. alembic head
cd backend && alembic current
```

**보고할 것**
- `baseline_controls`에 주기 컬럼을 추가할 때 기존 93건을 어떤 값으로 채울지 + 근거
- 회계연도 시작월을 `tenant_policies`에 두는 것이 적절한지 (구조 확인 후 판단)
- 대상 통제 스냅샷 vs 조회 시점 계산 — 어느 쪽인지 + 근거
- `role_resolver`를 그대로 쓸 수 있는지, 확장이 필요한지

**실측이 ADR-0032 전제와 어긋나면 코드를 맞추지 말고 보고할 것.**

## 4. 구현 원칙

- **ADR-0020 준수.** 서비스 클래스·패턴 금지
- **ADR-0025 준수.** 테넌트 필터 수동 금지. `AuditedBase` 상속으로 자동 격리
- **ADR-0030 준수.** 신규 테이블 간 FK는 복합 FK로 테넌트 격리
- 3-1의 `role_resolver`를 재사용할 것. 권한 판정 로직을 복제하지 말 것
- API 계약은 `docs/api/org-contract.md`·`rcm-hierarchy-contract.md`와 같은 규약

## 5. 검증 조건

1. 통제 주기가 baseline 기본값에서 나오고, overlay override가 우선함
2. 설계평가 회차와 운영평가 회차를 동시에 열 수 있고 서로 영향 없음
3. **분기 주기 회차 생성 → 분기 주기 통제만 대상. 주/월 주기 통제 미포함**
4. 회계연도 시작월이 3일 때 1분기 기간 기본값이 4/1~6/30으로 제안됨
5. `control_owner`가 회차를 생성하려 하면 거부됨 (`assessor`만 가능)
6. 통제 A의 평가자가 통제 B에서 평가 기록을 남기려 하면 거부됨 (통제 단위 권한)
7. **미완 통제가 있는 회차 마감 → 사유 없으면 거부, 사유 있으면 마감 + 미완 목록 보존**
8. `dept_approval_skipped`인 통제는 부서승인 단계를 건너뜀
9. 정책 토글 `dept_approval_enabled`가 false면 전체 부서승인 스킵
10. 마감되지 않은 회차에 최종승인 시도 → 거부
11. 활동 기록에 수행자·수행시각이 남고 조회 가능
12. `external_auditor`가 회차 생성·활동 기록 시도 → 거부
13. 다른 테넌트의 회차에 접근 불가 (postgres에서 확인)
14. 전체 pytest 통과, xfail 1건 유지

**3번과 7번이 핵심이다.**
3번은 §2.3(주기 기반 자동 대상 선정)이, 7번은 §2.6(막지 않고 기록)이 구현됐는지 본다.

**13번 주의** — sqlite는 FK를 강제하지 않는다. postgres에서 확인하고,
검증 불가한 항목은 그 사실을 명시할 것.

## 6. 커밋 분리

1. `feat(db): 통제 평가주기 + 회계연도 시작월 (3-2, ADR-0032 §2.1~2.2)`
2. `feat(db): 평가 회차·활동·승인 테이블 (3-2, ADR-0032 §2.3~2.7)`
3. `feat(assess): 평가 회차 CRUD API`
4. `feat(assess): 활동 기록·승인 API`
5. `feat(assess): 회차 마감·최종승인 API`
6. `test(assess): 검증 케이스 추가`

각 커밋 후 `ruff` + `pytest` 통과 확인.

## 7. 완료 보고

1. STEP 0 실측 결과 4건 (판단이 필요한 항목은 근거 포함)
2. 커밋 해시와 변경 파일
3. §5 검증 14개 결과 — 13번은 postgres 확인 여부 명시
4. `ruff` / `pytest` 결과
5. API 계약 요약 — Regina 전달용. `docs/api/` 문서화 여부는 보고 후 판단
6. 로컬 검증만 완료된 상태임을 명시

**실행하지 않은 항목을 완료로 보고하지 않는다.**

## 8. push 정책

**로컬 커밋까지. push 대기.**
마이그레이션이 포함되므로 마스터가 백업 후 push한다.
`git log origin/main..HEAD`로 대기 커밋을 확인하고 보고할 것 (CLAUDE.md §8.3).
