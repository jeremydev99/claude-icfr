# ICFR-PROMPT-EVAL-01 — 평가 3모듈(테스트·개선계획·증빙) 현황 실사 + 도메인 계약 초안

## 목적
평가 영역 신규 개발 착수 전, **실제 코드·DB·API 기준**으로 현황을 실사하고
테스트 → 미비점 → 개선계획 → 재테스트 흐름과 공통 증빙의 **도메인 계약 초안**을 만든다.
이 작업은 **조사·문서화 전용**이다. 앱 코드/스키마/데이터는 일절 변경하지 않는다.

## 절대 규칙
- 코드 수정, `npm install`, `alembic upgrade/downgrade`, seed 실행, DB 쓰기(INSERT/UPDATE/DELETE/DDL) **금지**
- DB는 추정 금지. 반드시 실제 DB를 `SELECT`/`\d` 계열로 조회해 확인한다
- 확인 못 한 항목은 "미확인"으로 표기하고 추측으로 채우지 않는다
- PowerShell 5.1: `&&` 금지(`;` 사용), `grep` 금지(`Select-String`), `cd` 대신 `Set-Location`, bash 문법(`2>&1`, `$()`, heredoc, `/tmp`) 금지, 단일 명령 965바이트 이하
- 와일드카드 세션 승인 요청 금지

## 작업 순서

### 0. 동기화
```powershell
Set-Location E:\claudeprojects\ICFR; git fetch --all; git status; git log origin/main -15 --date=short --format="%h %ad %an %s"
```
- 로컬 미커밋 변경이 있으면 중단하고 보고
- `git pull --rebase` 로 main 최신화

### 1. 프론트엔드 초안 인벤토리 (협업자 작업 포함)
- 라우터 정의에서 평가 영역 라우트 전수 조사: `/evidence` 및 test, deficiency, remediation, 개선, 증빙 관련 경로
- 각 라우트 → 페이지 컴포넌트 → 사용하는 hooks/API 클라이언트/타입 매핑
- 최근 커밋 중 평가 영역 관련 변경(작성자, 해시, 요약)
- 각 화면 상태 판정: **실데이터 연동 / 목업·하드코딩 / 빈 껍데기**
- 참고: 화면 리뷰 기준은 배포본 `https://icfr.synap.co.kr` (로그인 필요 — 직접 접속하지 말고 origin/main 코드 기준으로 판정)

### 2. DB 실사 (읽기 전용)
- `docker compose ps` 로 DB 서비스명 확인 후, 컨테이너 내부 psql로 `icfr_db` 접속
- 테스트·미비점·개선계획·증빙·첨부·파일 관련 테이블 전수: 컬럼, 타입, NULL 여부, FK, 인덱스, `tenant_id` 유무
- Alembic: 현재 head 리비전과 해당 테이블들을 만든 리비전 파일 목록
- RCM Control 테이블과의 FK 연결 여부 명시

### 3. 백엔드 API 실사
- FastAPI 라우터에서 평가 영역 엔드포인트 전수: method, path, 요청/응답 스키마, 권한 체크 방식
- Source Envelope **flat 계약**(`source`/`baseline_id`/`is_overridden` 최상위) 적용 여부
- MinIO 업로드/다운로드 경로(presigned 여부, 버킷/키 규칙)
- 권한: `can_write`, `tenant_roles`(특히 `external_auditor` 읽기 전용) 반영 여부

### 4. 산출물 1 — 갭 맵
`docs/` 하위 기존 문서 위치 관례를 따라 `ICFR-EVAL-01-gap-map.md` 생성.
모듈(테스트/개선계획/증빙) × 계층(FE 화면 / FE API 연동 / BE API / DB) 표로 **있음 / 초안만 / 없음 / 미확인** 표기 + 근거(파일 경로·테이블명·커밋 해시).

### 5. 산출물 2 — 도메인 계약 초안
같은 위치에 `ICFR-EVAL-01-domain-contract.md` 생성. 포함 내용:
- 엔티티와 관계도(텍스트/mermaid): Control → TestPlan → TestExecution(설계/운영 효과성, 표본) → TestResult → Deficiency(단순 미비점/유의한 미비점/중요한 취약점) → RemediationPlan → Retest, Evidence는 여러 엔티티에 붙는 **공통 첨부**
- 엔티티별 필드: **실존(DB 확인됨)** 과 **제안(신규 필요)** 을 구분 표기
- 상태 전이(워크플로 status)와 각 전이의 권한 주체
- 멀티테넌트(`tenant_id`), 감사추적(작성자/수정자/시각), 증빙 버전 관리, 파일 무결성(해시) 기준 — 외부 판매 수준 기준으로 필요 여부 제시
- 백엔드(TrustBuilder) 확인이 필요한 질문 목록

### 6. ClaudeICFR.md 반영
- §14 changelog에 이번 실사 1줄 기록
- §13은 **직접 수정하지 말고**, 신규 backlog 후보를 갭 맵 문서 하단 "§13 반영 후보" 절에 정리

### 7. 커밋·푸시 (docs 전용, 자동 push 승인)
```powershell
git add docs ClaudeICFR.md; git commit -m "docs(eval): EVAL-01 평가 3모듈 현황 실사 및 도메인 계약 초안"; git pull --rebase; git push
```
- docs 외 파일이 스테이징되면 중단하고 보고

## 완료 보고 형식
1. 갭 맵 요약(모듈별 3줄 이내)
2. 협업자 초안 화면 목록과 상태
3. DB/API에서 발견한 계약 충돌 또는 리스크
4. TrustBuilder 확인 필요 질문
5. 다음 단계 추천 1개
