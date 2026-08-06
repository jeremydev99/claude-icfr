# ICFR baseline seed 구축 명세 — 엑셀 단일 원천

- **작성일**: 2026-07-23
- **근거**: ADR-0027, 2-A-2(임시 이관) 후속. baseline 거버넌스 정식화.
- **Tier**: Tier 2 (실데이터 재구축 → 마스터 push, **신중**)
- **원칙**: ADR-0020 제로 추상화. ADR-0023 데이터 보존. 모든 환경 동일 baseline 재현.

---

## 0. 배경 — 왜 seed인가

2-A-2는 "마스터 로컬의 기존 controls → baseline" 이관이었으나, 이는 **임시방편**이었다. 진짜 표준 원천은 **Regina 보유 최종 엑셀(95종)**이다. 로컬마다 다른 데이터를 이관하면 baseline이 환경별로 분열된다(마스터 중간 95 vs Regina 최종 95는 내용이 다르다).

**정식 해법**: 엑셀을 단일 원천으로 repo에 두고, seed 스크립트가 모든 환경(마스터·Regina·CI·운영)에서 **동일 baseline을 재현**한다. 엑셀 = 표준의 유일 원천, 2-A-2 이관 스크립트는 역할 종료(repo엔 남기되 seed가 표준 경로).

---

## 1. 확정 결정 (마스터 승인)

1. **엑셀을 repo에 포함** — `backend/seeds/2026_설계평가_RCM_리스트.xlsx` (사이냅소프트 자사 데이터, 자사 repo 포함 승인됨)
2. **마스터 로컬 baseline 재구축** — 폐기 대상 중간 95를 비우고 엑셀 기준으로 재구축 (승인됨)
3. **seed가 정식 경로, 2-A-2 이관은 역할 종료** (동의됨)

---

## 2. 파싱 로직 방침 — 순수 변환만 재사용

기존 `upload-excel`의 파싱 함수 상당수가 `controls`(구 스키마)에 직접 결합돼 있다. 전면 재사용은 upload-excel API 리팩터링까지 번지므로 **지금은 하지 않는다**(그건 2-A-4-3 범위).

**방침**:
- 기존 함수 중 **controls에 결합되지 않은 순수 변환 로직**(값 정규화, 계층 코드 파악, 어서션 매핑, 위험번호 파생 등)은 **추출·재사용**한다.
- controls에 결합된 삽입 로직은 재사용하지 않고, seed가 **baseline_* 삽입을 자체 작성**한다.
- 작업 전 파싱 코드를 확인해 순수 변환 부분과 결합 부분의 실제 분리 가능성을 판단하고, 분리 방식(공통 함수로 추출 vs seed 내 복제)을 보고할 것. 완전한 파서 코어 분리는 2-A-4-3에서.

---

## 3. 엑셀 구조 (실측 확인)

- 파일: `2026_설계평가_RCM_리스트.xlsx`, Sheet1, ㈜사이냅소프트, Update 2026-05-12
- **다중 헤더행 1~7행**, 데이터 8행부터 (기존 upload-excel의 헤더 스킵 로직 확인·재사용)
- 계층: 프로세스(EL/SD/TR) → 하위프로세스 → 위험번호 → 통제활동번호
  - 프로세스: EL(전사), SD(매출관리), TR(자금관리)
  - 통제코드: `EL-010-10-10`(4단계), 위험번호: `EL-010-10`
- 어서션 7종: 실재성 E · 완전성 C · 권리와의무 R · 평가 V · 재무제표표시와공시 P · 발생사실 O · 측정 M
- 통제 속성: 통제유형(승인/검증/물리적/기준정보/대사/감독), 예방적발(P/D), Auto/Manual(M/A), 주기(O/D/W/M/Q/A), Key Control(Yes)

> 엑셀엔 RCM 본체 외 설계평가·개선업무 데이터도 있으나, **seed 대상은 RCM 본체(baseline 5계층 + 어서션)**뿐이다. 설계평가·개선은 워크플로 영역으로 seed 범위 밖.

> 각 baseline 필드 매핑은 기존 upload-excel의 컬럼→필드 매핑을 기준으로 하되, 삽입 대상만 baseline_*로 바꾼다. 실제 매핑은 코드 확인 후 정확히.

---

## 4. seed 스크립트 (`backend/seeds/seed_baseline.py`)

2-A-2 이관 스크립트와 동일한 안전 패턴을 따른다.

**동작**:
1. 엑셀 로드 (repo 내 고정 경로)
2. 순수 변환 로직으로 행별 파싱 → 계층 구조 추출
3. 계층 순서로 baseline_* 삽입 + id 매핑:
   ```
   baseline_processes → baseline_sub_processes → baseline_risks
   → baseline_risk_categories → baseline_controls → baseline_control_assertions
   ```
4. baseline_version=1, id 신규 생성, tenant_id 없음(IdentityBase)
5. instance는 생성하지 않음 (암묵 adopt)

**안전 장치 (2-A-2와 동일)**:
- **재실행 안전**: baseline 테이블에 데이터 있으면 중단·보고. 덮어쓰기 옵션 만들지 말 것.
- **단일 트랜잭션**: 실패 시 전체 롤백
- **검증 출력**: 계층별 삽입 건수. 어서션 코드는 7종 마스터를 먼저 구성(중복 제거)한 뒤 통제-어서션 연결.

**어서션 처리**: risk_categories(어서션 7종)는 통제마다 반복 등장하므로, **먼저 유니크 7종을 baseline_risk_categories에 삽입**하고, 각 통제의 어서션 플래그(E/C/R/V/P/O/M 컬럼의 O 표시)를 읽어 baseline_control_assertions 연결을 생성한다.

---

## 5. 기존 baseline 정리 (재구축)

마스터 로컬의 폐기 대상 중간 95 baseline을 비운다.

- seed는 "baseline 있으면 중단"이므로, **재구축 시 기존 baseline을 먼저 비우는 별도 단계**가 필요하다.
- 방법: seed에 `--reset` 옵션을 두되, **명시적으로 실행할 때만** baseline_*를 비우고 재삽입. 기본 실행은 절대 비우지 않음(실수 방지).
- `--reset`은 baseline_*와 그에 연결된 instance만 대상. **기존 `controls` 등 구 테이블은 건드리지 않는다.**
- reset 실행 전 현재 baseline 건수를 출력하고, reset 후 재삽입 건수를 출력해 대조.

> `--reset`은 실데이터 삭제 경로다. 스크립트에 존재하되, 실행은 마스터가 명시적으로 판단한다. 2-A-2 이관으로 들어간 중간 95는 이 reset+seed로 최종 엑셀 기준으로 대체된다.

---

## 6. 실행 순서 (마스터 수행)

1. 엑셀을 `backend/seeds/`에 배치, 스크립트 작성 (커밋 전 보고)
2. 재빌드 (Dockerfile에 `COPY seeds/` 필요 — 없으면 추가 또는 `docker compose cp`)
3. **현재 baseline 건수 확인** (중간 95)
4. `seed_baseline.py --reset` 실행 → 기존 비우고 엑셀 기준 재삽입
5. **검증**:
   - baseline 계층 건수 (엑셀 기준 95 통제 + 상위 계층)
   - `resolve_controls`가 통제를 관계필드·envelope 포함 반환
   - 구 `controls` 테이블 미변경 확인
   - instance 0건
6. pytest 전체 통과

---

## 7. 완료 기준

- [ ] 엑셀 `backend/seeds/`에 포함
- [ ] seed_baseline.py — 순수 변환 재사용, baseline_* 자체 삽입, 계층 id 매핑
- [ ] 어서션 7종 유니크 마스터 + 통제 연결
- [ ] 재실행 안전(데이터 있으면 중단) + `--reset` 명시 옵션
- [ ] 단일 트랜잭션, 검증 출력
- [ ] instance 미생성, 구 controls 미변경
- [ ] 재구축 후: baseline이 엑셀 기준(95 통제)으로 채워지고 resolve_controls 정상
- [ ] pytest 전체 통과

**주의**: 스크립트 작성 후 **실행 전 마스터 보고**. `--reset`은 실데이터 삭제이므로 마스터가 실행 판단. config.py admin_password 건드리지 말 것.

---

## 8. 작업 전 확인 (Claude Code)

- `api/rcm.py` upload-excel 파싱 함수 — 순수 변환 vs controls 결합 분리 가능성
- 컬럼→필드 매핑 (baseline 필드에 정확히 대응)
- `models/rcm_baseline.py` baseline 5계층 + 어서션 필드
- `scripts/migrate_rcm_to_baseline.py` — id 매핑·안전장치 패턴 참고
- 엑셀 헤더행 수·데이터 시작행 (기존 파싱과 일치)

---

## 남는 과제 (별도)

- Regina/CI/운영 환경에 seed 배포 방식 (문서화)
- 2-A-4-3에서 upload-excel 파서 코어 완전 분리 (baseline/instance/controls 공용)

---

ICFR_baseline_seed_20260723.md 진행해줘
