# ICFR-PROMPT-state-board-sync

## 목적
`ClaudeICFR.md`의 12/13/14 섹션(상태 보드 / pending / changelog)을 2026-08-04 로컬 실측 현황에 맞춰 갱신한다.
**문서만 수정한다. 코드·스키마·DB는 건드리지 않는다.**

---

## 확인된 사실 (2026-08-04 로컬 실측, read-only 검증 완료)

### DB count (구 구조, is_deleted=false)
- processes 8 / sub_processes 29 / risks 85 / risk_categories 7 / controls 96 / control_assertions 469

### 신 구조 스키마 랜딩 = 2-A-2 완료
- baseline_* (6개 존재): baseline_processes, baseline_sub_processes, baseline_risk_categories, baseline_risks, baseline_controls, baseline_control_assertions
- *_instances (5개 존재): process_instances, sub_process_instances, risk_instances, control_instances, control_assertion_instances
- **단, 신 구조 데이터는 전부 0건 → 데이터 백필 미완**

### 코드 전환
- 커밋 `226f604`: envelope optional→required 전환 + source 뱃지 노출 (2-A-3 코드 반영됨)
- control_instances overlay 판별 구조: `baseline_control_id`(nullable) + `action` 컬럼
  - `is_overridden` boolean 컬럼은 존재하지 않음 (기존 기록과 상이)

---

## 확인 대기 — 협업자 회신 전까지 확정 서술 금지 (pending 처리)
1. baseline/instance 데이터 백필 migration이 별도 예정 스텝인지
2. resolver가 `action` → `is_overridden` 매핑을 제공하는지 (FE envelope 계약은 `is_overridden` flat 필드 기준)

---

## 작업 지시
1. `ClaudeICFR.md`를 읽고 12/13/14 섹션 현재 서술 파악
2. 위 "확인된 사실" 반영:
   - 2-A-2 스키마 랜딩 → **완료**로 기록하되 "데이터 백필 미완" 반드시 명시
   - 2-A-3 → 코드 전환(`226f604`) 반영됨으로 기록
   - overlay 판별 구조(`baseline_control_id` + `action`) 기록, 기존 `is_overridden` 가정과의 차이 명기
3. "확인 대기" 2건 → pending 항목으로 명시. **추정 서술 금지**
4. changelog(14)에 오늘 실측 검증 항목 추가

## 범위 경계
- `ClaudeICFR.md` 단일 파일만 수정. 코드/스키마/DB 무변경
- 빌드 불필요 (tsc / npm build 대상 아님)

## 커밋
- 문서 단일 변경 → 자동 진행
- 커밋 메시지: `docs(state): 2-A-2 스키마 랜딩·2-A-3 코드 전환 실측 반영, 백필 미완 pending 기록`
- `-F prompts\_commitmsg.txt` 패턴 사용 (heredoc 금지)
