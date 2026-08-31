# ICFR-PROMPT-record-20260831

## 목적
2026-08-31 세션 성과를 ClaudeICFR.md에 기록한다. 오늘은 코드 변경 없이 검증·조사·로컬 재구축을 수행했고, 2-A-4-3 프론트 잔여 작업의 정체를 확정했다.

## 절대 원칙
- **확정된 사실만 기록.** 추정·미확정 항목은 "미결/설계 결정 대기"로 명시하고 결론을 지어내지 않는다.
- 오늘 세션은 코드 변경 0건 — feat/fix 커밋 없음. **docs 커밋만** 생성.
- 기존 §12/§13/§14 내용 보존. 두 세션(이 세션 + Claude Code 세션) 변경 병합 시 기존 항목 삭제 금지.
- PowerShell 5.1: `&&` 금지, `;` 시퀀싱, 커밋 메시지는 `-F` 플래그.

## 기록 대상 및 내용

### A. §14 changelog — 오늘 작업 기록 추가
날짜: 2026-08-31. 아래 사실을 기록:
- **배포 검증 (조회)**: TrustBuilder의 ADR-0029 배포(상위 3계층 resolver/cascade 전환) 확인. 배포 사이트(icfr.synap.co.kr)에서 프로세스 필터 드롭다운 8개 정상, EX 필터 3건 확인. 상위계층 조회 resolver 전환 정상 동작 확인.
- **로컬 운영상태 재구축**: 로컬 백엔드 8커밋 fast-forward pull(d2b8618→8403a3b, ADR-0029 코드 반영), 도커 재빌드, seed_baseline --reset(691행 재시드). 카운트 검증 프로세스 8 / 하위프로세스 29 / 리스크 85 / 통제 93 기대값 일치.
  - rcm_baseline.py 모델 변경(+26줄)은 ORM 레벨(허용값 모듈 상수화)일 뿐 DB 스키마 불변 확인 — alembic 마이그레이션 부재와 일치.
- **조사(읽기 전용)**: 상위 3계층 CRUD 프론트 배선 현황·설계 조사 완료. 결과는 아래 §13 항목에 반영.

### B. §13 backlog — 2-A-4-3 상태 갱신 + 미결 결정 등록
- **2-A-4-3 상태**: 백엔드 완료(cad62a9 상위 3계층 CRUD overlay 전환, backend만 변경·프론트 0건). 프론트 배선 **미착수** — 사유는 아래.
- **확정된 핵심 발견**:
  - 백엔드 3계층 CRUD API 완비: GET/POST/PATCH/DELETE for /processes /sub-processes /risks (rcm.py:236-390). 응답 flat envelope(source/baseline_id/is_overridden), control과 동일 계약. action은 요청 종류로 서버 암묵 결정(POST=add/PATCH=override/DELETE=exclude) — control과 동일 패턴. 클라이언트 action payload 필드 없음.
  - cascade는 저장하지 않고 조회 시점 계산(control_resolver.py) — 상위 제외 시 하위는 목록에서 사라질 뿐 "상위 때문에 빠짐" 플래그는 응답에 없음.
  - 프론트에 상위 3계층을 **목록으로 렌더링하는 화면이 없음.** 현재 조회 데이터는 필터 드롭다운(ControlSearchBar) + control 폼 연쇄 select(BasicInfoTab) 채우는 용도만. CRUD 버튼을 얹을 목록 UI 부재.
  - control의 API함수/mutation훅/어댑터 패턴은 재사용 골격으로 사용 가능하나, UI 컴포넌트(RcmPage 삭제버튼·DeleteConfirmDialog)는 control 전용이라 3계층에 그대로 못 씀.
  - **Scoping은 상위계층 관리 자리가 아님**: Scoping의 scope는 계정과목 중요성 판단(§4.3 엔티티: AccountBalance/Materiality/ScopeIn) 개념이고, RCM baseline의 exclude/adopt/override와 다른 개념. ADR-0029 문서에 FE/Scoping 언급 0건. 근거 없음.
  - **잠정 판별**: 2-A-4-3 프론트 잔여 작업 = 상위 3계층 관리 **신규 화면 설계·배선**. (기존 목록 UI 없음 + Scoping 부적합)
- **미결 결정 2건 (TrustBuilder 합의 대기)**:
  1. 상위계층 관리 UI 위치·형태 — RCM 모듈 내부(예: 매트릭스 화면 확장) vs 별도 신규 라우트. §13에 계획 없음, 설계 결정 필요.
  2. ProcessItem/SubProcessItem/RiskItem의 envelope optional→required 전환 여부 — 현재 optional(buildOptionalSourceEnvelope 사용). 목록 API가 resolver 경유라 required 전환 가능해 보이나 미결정.

### C. §10 ADR 요약 — ADR-0029 확인
- §10에 ADR-0029(계층 cascade 시맨틱·overlay 소유 경계)가 이미 반영돼 있는지 확인. 없으면 요약 한 줄 추가. 있으면 그대로 둠.
- 요지: 상위 제외 시 하위도 함께 안 보임 / 상위 복원 시 하위 개별 제외는 유지 / 통제 제외 시 어서션 연결도 빠짐. cascade는 저장 없이 조회 시점 계산.

## 커밋
- docs 단일 커밋. 메시지 예: `docs(claudeicfr): 2026-08-31 세션 기록 — ADR-0029 배포 검증·로컬 재구축·2-A-4-3 프론트 신규화면 필요 확정`
- 이 프롬프트 .md 파일도 prompts/에 포함해 함께 커밋(프로젝트 아티팩트).
- Tier 1 문서 변경이므로 origin/main 직접 push 승인.

## 실행 후
기록 완료 후, TrustBuilder에게 미결 결정 2건을 확인하는 메시지 초안은 별도로 논의한다(이 프롬프트 범위 밖).
