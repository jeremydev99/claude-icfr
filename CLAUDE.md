# CLAUDE.md

> 이 파일은 Claude Code가 세션 시작 시 자동으로 읽는 가이드입니다.
> 새 세션이 시작되면 Claude는 아래 절차를 **반드시** 따릅니다.

---

## 0. 세션 시작 시 필수 절차

1. **`ClaudeICFR.md` 전체를 먼저 읽는다.** 이 파일이 프로젝트의 단일 진실 공급원이다.
2. `ClaudeICFR.md` 섹션 12(진행 상태 보드)에서 현재 어디까지 왔는지 확인한다.
3. `ClaudeICFR.md` 섹션 13(다음 작업)을 확인하고 사용자에게 진행 의사를 묻는다.
4. **전체 코드 베이스를 무작정 읽지 않는다.** 필요한 파일만 발췌해서 본다.
5. 작업이 끝나면 `ClaudeICFR.md` 섹션 12, 13, 14를 반드시 업데이트한다.

---

## 1. 토큰 절약 규칙

- 이미 합의된 사항은 `ClaudeICFR.md`에 짧게 참조만 한다. 재설명·재인용 금지.
- 코드 변경 시 전체 파일을 다시 출력하지 않는다. 변경된 부분만 diff 형태로 보여준다.
- 큰 결정(아키텍처, 데이터 모델 변경)은 `ClaudeICFR.md` 섹션 10(ADR)에 1건당 10줄 이내로 요약한다.
- 진행 상황 보고 시 장황한 설명 대신 체크리스트와 표를 사용한다.

---

## 2. 파일 변경 규칙

### 2.1 변경 우선순위
1. 코드 변경 → 즉시 `ClaudeICFR.md` 진행 상태 보드 반영
2. 의사결정 → 즉시 `ClaudeICFR.md` 섹션 10(ADR) 반영
3. 새 모듈 작업 시작 → `ClaudeICFR.md` 섹션 12 모듈별 상태표에 🔄 표시
4. 모듈 완료 → `ClaudeICFR.md` 섹션 12에 ✅ 표시 + 섹션 14 변경 로그 추가

### 2.2 커밋 메시지 (Conventional Commits)
```
feat(rcm): 통제 버전 Diff 화면 추가
fix(evidence): 한글 파일명 깨짐 수정
docs(claudeicfr): 진행 상태 보드 업데이트
refactor(notif): 발송 큐 추출
```

### 2.3 PR 본문 필수 항목
- 어느 `ClaudeICFR.md` 항목과 연관된 작업인지 명시
- 변경 요약 (5줄 이내)
- 테스트 결과
- 후속 작업 (있다면 섹션 13에 반영)

---

## 3. 작업 영역 (디렉토리)

```
ICFR/
├─ ClaudeICFR.md          ← 단일 진실 공급원 (반드시 먼저 읽기)
├─ CLAUDE.md              ← 이 파일
├─ README.md
├─ docs/
│   ├─ diagrams/           ← 다이어그램 산출물(mmd/svg/png, ClaudeICFR.md §2에서 참조)
│   ├─ adr/                ← ADR-0028부터 개별 파일 사용 시작. 분리 기준: 운영·인프라 및 대형 설계 ADR은 개별 파일(0028 인프라, 0029 cascade 시맨틱, 0030 baseline 테넌트 소유권, 0031 역할·권한 모델, 0032 평가 회차·워크플로), 코드 설계 ADR은 ClaudeICFR.md §10 요약 유지.
│   ├─ api/                ← 계약 스냅샷 문서. `rcm-hierarchy-contract.md`(상위 3계층 CRUD)·`org-contract.md`(조직·역할 배정).
│   │                        API 스펙 자체는 FastAPI 자동 생성 문서가 단일 진실 공급원(ADR-0017 §19) —
│   │                        `openapi.yaml` 파일 export는 여전히 미착수. 여기의 스냅샷 문서는 자동 문서가
│   │                        드러내지 못하는 것(계층별 검증 차이·계약에 없는 것)을 보완하며, 상단에 기준
│   │                        커밋을 명시하고 API 변경 시 갱신한다.
│   └─ erd/ (예정)         ← ERD는 현재 ClaudeICFR.md §5에 인라인. 별도 다이어그램 소스 분리는 미착수.
├─ backend/
├─ frontend/
├─ infra/
└─ scripts/
```

---

## 4. 모르는 것은 묻는다

- 기술 스택, 보안 정책, 외부 시스템 연동 방식 등 사용자만 알 수 있는 정보는 **추측하지 말고 묻는다.**
- 묻기 전에 `ClaudeICFR.md` 섹션 10(ADR)에 이미 결정되어 있는지 확인한다.

---

## 5. 금지 사항

- ❌ 사용자 확인 없이 git commit·push 실행 (커밋 메시지를 먼저 제시하고 OK 받은 후 진행)
- ❌ 자격증명·토큰·비밀번호를 파일에 저장
- ❌ `ClaudeICFR.md`를 우회하고 독자적으로 진행
- ❌ 전체 코드 베이스 일괄 재읽기
- ❌ 한 PR에 너무 많은 모듈을 동시에 변경

---

## 6. 응답 스타일

- 한국어로 답변한다.
- 결론을 먼저 말하고 근거는 뒤에 둔다.
- 코드보다 의사결정·구조가 우선이면 표나 다이어그램을 활용한다.
- 매 작업 종료 시 "다음에 할 일"을 한 줄로 정리한다.

---

## 7. 프롬프트 파일 운영 (Prompt Library)

claude.ai 채팅에서 큰 작업이 합의되면, Claude Code 실행용 명령을
별도 마크다운 파일로 만들어 `prompts/` 폴더에 보관한다.

### 명명 규칙
`{프로젝트}_{개발분야}_{번호}_{YYYYMMDD}.md`

예시:
- `ICFR_setup_1_20260515.md` — 셋업 작업 1번 (2026-05-15)
- `ICFR_backend_1_20260601.md` — 백엔드 작업 1번
- `ICFR_module-rcm_1_20260701.md` — RCM 모듈 작업 1번

### 개발분야 카테고리
- `setup` — 프로젝트 셋업·문서 갱신·로드맵 등 메타 작업
- `infra` — 인프라·배포·DB 마이그레이션
- `backend` — FastAPI 백엔드 작업
- `frontend` — React 프론트엔드 작업
- `module-{이름}` — 특정 모듈 작업 (예: `module-rcm`, `module-test`, `module-evidence`)
- `bugfix` — 버그 수정
- `refactor` — 리팩토링
- `test` — 테스트 코드 작성
- `docs` — 문서만 변경하는 작업

### 사전 승인 원칙
claude.ai에서 새 프롬프트 파일을 만들기 전, 반드시 사용자에게
"이렇게 프롬프트를 만들어 드릴까요?" 라고 내용 요약을 먼저 제시하고
**승인을 받은 후에** 파일을 생성한다. 빠진 항목 점검과 토큰 절약 효과.

### 호출 방법
Claude Code에 다음과 같이 호출:
```
prompts/ICFR_setup_1_20260515.md 대로 작업해줘
```

### 가치
- Git 이력에 작업 명령이 남아 추적 가능
- 협업자 합류 시 작업 패턴 빠른 파악
- 외부감사 시 AI 작업 이력 제시 가능
- 비슷한 작업 반복 시 복사·수정해서 재사용

---

## 8. Git 자동화 운영 방침

### 7.1 역할 분리
- **claude.ai 채팅**: 기획·설계·토론 전용. 파일 직접 수정 불가.
- **Claude Code (로컬)**: 파일 생성·수정 + `ClaudeICFR.md` 갱신 + git commit & push 일괄 수행.

### 7.2 ClaudeICFR.md 갱신 주체
- 모든 `ClaudeICFR.md` 업데이트는 **Claude Code가 직접** 수행한다.
- claude.ai에서 설계 토론 후 결론이 나면, Claude Code에 "ClaudeICFR.md에 반영해줘"라고 지시한다.

### 7.3 작업 완료 후 Git 자동화 절차
1. `git status` — 변경 파일 확인
2. 커밋 메시지(안)을 사용자에게 제시
3. **사용자 OK 확인 후** `git add . → git commit -m "..."` 실행
4. **push 전 `git log origin/main..HEAD` 로 대기 커밋을 확인한다.
   승인 범위 밖 커밋이 있으면 push하지 않고 보고한다.**
5. **대기 커밋에 마이그레이션이 있는지 확인한다.**
   ```bash
   git diff --name-only origin/main..HEAD | grep alembic/versions/
   ```
   **결과가 있으면 Claude Code 는 push 하지 않는다.** 마스터에게 보고하고 멈춘다.
6. `git push` (5 에서 마이그레이션이 없을 때만)

> 사용자 OK 없이 commit·push 절대 금지.  
> 커밋 메시지는 Conventional Commits 형식 준수 (섹션 2.2 참조).  
> **push 승인은 커밋이 아니라 브랜치에 적용된다** — 대기 커밋이 함께 올라가므로
> "이 커밋만 push"는 성립하지 않는다. 경위는 `ClaudeICFR.md` 13.9 참조.

> **마이그레이션이 포함된 커밋은 Claude Code 가 push 하지 않는다.**
> 마스터가 **백업 실행 후 직접** push 한다. 사용자가 "푸시하자"라고 해도
> 5 에서 걸리면 push 하지 않고 보고한다 — 백업 여부는 실행자가 확인할 수 없다.
>
> `deploy.yml` 에 경로 필터가 없고(13.8) 컨테이너 기동이 `alembic upgrade head` 로
> 시작하므로 **push = 운영 마이그레이션 실행**이다. 되돌리려면 백업이 있어야 한다.
>
> 근거: 2026-09-04 3-2. 프롬프트에 "마스터가 백업 후 push"라고 적었으나
> Claude Code 가 push 했다. **실행자가 확인할 수 없는 조건은 게이트가 되지 못한다** —
> 절차를 지시문에 적는 것과 실행 흐름에 심는 것은 다르다(`ClaudeICFR.md` 13.9-28).

---

## 9. 코딩 시작 전 명세 동기화 체크 (Contract Sync)

사용자가 백엔드(`backend/`) 또는 프론트엔드(`frontend/`) 코드 작업을
요청할 때, Claude Code는 **반드시 작업 시작 전 다음을 수행**한다.

### 9.1 발동 조건
- 사용자 요청에 `backend/`, `frontend/` 폴더의 코드 변경이 포함됨
- 예외: 문서 변경, 일일 진행 로그(`ClaudeICFR.md` 섹션 18), `prompts/` 파일 작성

### 9.2 체크 절차
1. `git fetch origin` 으로 원격 최신 상태 가져오기
2. 로컬 main과 원격 main의 차이 확인 (`git log HEAD..origin/main`)
3. 다음 파일에 원격 변경이 있는지 점검:
   - `ClaudeICFR.md` (특히 섹션 10 ADR, 섹션 19 API 명세 표준)
   - `docs/api/openapi.yaml` (생성된 후)
   - 프론트엔드 작업 시: `backend/app/api/**/*.py`, `backend/app/schemas/**/*.py`
   - 백엔드 작업 시: 자기 영역이므로 동기화 확인만
4. 변경 발견 시 사용자에게 보고하고 동기화 여부 확인
5. 사용자 OK → `git pull` → 작업 시작
6. 변경 없음 → 바로 작업 시작

### 9.3 우회 금지
- 사용자가 "체크 건너뛰고 바로 작업해" 라고 명시하지 않는 한 항상 체크
- 사용자가 우회 지시 시에도 한 번 더 확인 요청

### 9.4 Claude Code 미사용 시 수동 동기화
- 사용자가 Claude Code를 거치지 않고 직접 코드 작업을 시작할 때는
  본인이 수동으로 `git pull` 실행 권장
