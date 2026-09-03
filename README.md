# ICFR System

내부회계관리제도(Internal Control over Financial Reporting) 운영을 위한 통합 관리 시스템.

## 📌 시작하기 전에

이 프로젝트의 **모든 의사결정, 진행 상황, 다음 작업**은 `ClaudeICFR.md` 한 파일에 누적 기록됩니다.

- 새 개발자 합류 시 → `ClaudeICFR.md` 섹션 0(문서 사용 규칙) → 섹션 12(진행 상태 보드)부터 읽으세요.
- Claude Code 사용 시 → `CLAUDE.md`가 자동 로드되어 `ClaudeICFR.md`를 먼저 읽도록 안내합니다.

## 핵심 문서

| 파일 | 역할 |
|---|---|
| [`ClaudeICFR.md`](./ClaudeICFR.md) | **단일 진실 공급원**. 명세·ERD·진행상황·ADR 모두 여기에. |
| [`CLAUDE.md`](./CLAUDE.md) | Claude Code 세션 시작 시 자동 로드되는 가이드. |
| `docs/diagrams/` | 다이어그램 산출물 (mmd/svg/png). |
| `docs/adr/` | ADR-0028부터 개별 파일 사용 시작. 분리 기준: 운영·인프라 및 대형 설계 ADR은 개별 파일(`ADR-0028` 인프라 기준, `ADR-0029` cascade 시맨틱, `ADR-0030` baseline 테넌트 소유권, `ADR-0031` 역할·권한 모델, `ADR-0032` 평가 회차·워크플로), 코드 설계 ADR은 `ClaudeICFR.md` 섹션 10 요약 유지. |
| `docs/api/` | `rcm-hierarchy-contract.md` — 상위 3계층 CRUD 계약 스냅샷(기준 커밋 명시, API 변경 시 갱신). API 스펙 자체는 FastAPI 자동 생성 문서가 단일 진실 공급원이며 `openapi.yaml` export는 미착수. |
| `docs/erd/` (예정) | ERD 다이어그램 소스 분리 — 현재는 `ClaudeICFR.md` 섹션 5에 인라인. |

## 핵심 모듈

모듈 목록·개수·상세 명세는 `ClaudeICFR.md` 섹션 1.2·4 참조 (여기서 별도 나열하지 않음 — 모듈 신설/변경 시 이 파일이 stale해지는 것을 방지).

## 현재 진행 단계

`ClaudeICFR.md` 섹션 12 (진행 상태 보드) 참조.

## 라이선스

Private. 내부 사용 전용.
