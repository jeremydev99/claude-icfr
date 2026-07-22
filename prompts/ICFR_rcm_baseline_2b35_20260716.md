# ICFR 2-B-3.5 — baseline_version 컬럼 + 삭제 의미론 명세

- **작성일**: 2026-07-16
- **근거**: ADR-0027, Regina FE 피드백(④ baseline_version 선반영, 삭제 의미론)
- **Tier**: Tier 2 (baseline 스키마 변경 + 마이그레이션 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화. 모든 회사 유연 적용, 고정 코딩 0.

---

## 0. 배경 — 왜 지금 넣나

baseline 콘텐츠는 법령·제도 검토 후 **반드시 개정**된다. 개정 이력을 추적할 `baseline_version`을 그때 추가하면 마이그레이션 + 전 tenant 백필 + 소급 매핑이 붙는다("나중은 프로젝트 하나"). 지금 컬럼 하나로 선반영한다("지금은 컬럼 하나"). 원칙 7(인프라 최종 기준 선확정).

개정 UX(사용자 알림 등)는 여전히 후속이다 — **컬럼과 UX는 별개**다. 본 단계는 스키마 필드만.

---

## 1. baseline_version — 행 단위 버전

**행 단위**로 둔다 (전역 버전 아님). 근거: 법령 개정은 현실에서 **부분 개정**(특정 통제 몇 개만)이다. 기업마다 채택한 통제가 다르므로(비채택·변형), "이 기업이 쓰는 통제 중 무엇이 개정됐나"를 정확히 짚으려면 행 단위여야 한다. 전역 버전은 전체 일괄 개정만 가정하는 숨은 고정이며, 모든 기업에 "전부 재검토"를 강제해 유연성을 죽인다. 행 단위라야 개정된 행을 쓰는 tenant만 영향받는다.

### 대상 — baseline 5테이블
- baseline_processes
- baseline_sub_processes
- baseline_risks
- baseline_risk_categories
- baseline_controls

각 테이블에 추가:
```python
baseline_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
```

- 전부 `default=1`로 시작 (현재 baseline이 v1)
- 개정 트랙에서 **바뀐 행만** 값을 올린다
- **이름 주의**: `IdentityBase`가 상속하는 `VersionMixin.row_version`(낙관적 잠금용 행 버전)과 **다른 개념**이다. `baseline_version`은 baseline 콘텐츠 개정 회차. 이름이 겹치지 않으므로 그대로 사용.

### instance는?
instance 테이블에는 **넣지 않는다** (본 단계). 다만 "instance가 어느 baseline 버전 기준으로 결정했는지"의 소급 매핑은 개정 트랙에서 다룰 미결 사항으로 남긴다 (아래 4절).

---

## 2. 삭제 의미론 — 전 계층 공통 규약

tenant는 baseline 행을 **물리 삭제할 수 없다**(전역 표준). tenant의 "삭제"는 **exclude**(= hide/deactivate)로 표현한다. 이미 action에 `exclude`가 있으므로 구조는 존재하며, 본 단계는 이를 **규약으로 명문화**한다:

- **tenant가 baseline 항목을 "삭제"** → `exclude` instance 생성 (물리 삭제 아님, 원본 보존)
- **tenant가 자기 add 항목을 삭제** → 해당 instance를 soft delete (`is_deleted`, 기존 SoftDeleteMixin)
- 이 규약은 process/sub_process/risk/control/assertion **전 계층 동일**. 계층별 분기 금지.

resolver(2-B-4)는 exclude를 결과에서 제외(이미 설계됨), add의 soft delete도 제외한다.

> 본 단계는 규약 문서화 + baseline_version 컬럼까지. exclude/soft-delete를 실제 수행하는 CRUD는 2-A-4. resolver 반영은 2-B-4.

---

## 3. 마이그레이션

- baseline 5테이블에 `baseline_version` 컬럼 추가 (default 1, NOT NULL)
- 기존 행 backfill = 1 (default로 자동, 또는 명시적 UPDATE)
- instance·기존 테이블 미변경
- downgrade: 5컬럼 제거 왕복
- 마이그레이션 후 기존 `controls` count = 95 확인 (ADR-0023)

---

## 4. 완료 기준

- [ ] baseline 5테이블에 baseline_version (Integer, default 1, NOT NULL)
- [ ] row_version(VersionMixin)과 개념 구분 — docstring 명시
- [ ] 삭제 의미론 규약 문서화 (전 계층 공통: baseline→exclude, add→soft delete)
- [ ] 마이그레이션 + 기존 데이터 baseline_version=1 backfill + controls 95 불변
- [ ] downgrade 왕복
- [ ] 테스트: baseline 행 생성 시 version=1 기본값, 명시적 version 설정 가능
- [ ] pytest 전체 통과 (기존 103 회귀 없음)

완료 후 `docker compose up -d --build backend` 재빌드. **controls count=95 확인**. config.py admin_password 건드리지 말 것.

---

## 미결 (개정 트랙에서)

- instance ↔ baseline 버전 소급 매핑 (instance가 어느 baseline 버전 기준인지)
- 개정 알림 UX
- baseline 개정 워크플로 (누가 언제 baseline_version을 올리나)

---

## 작업 전 확인 (Claude Code 먼저 수행)

- `models/base.py` VersionMixin.row_version (이름 충돌 없음 재확인)
- `models/rcm_baseline.py` baseline 5모델 (컬럼 추가 위치)

---

ICFR_rcm_baseline_2b35_20260716.md 진행해줘
