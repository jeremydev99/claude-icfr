# ICFR-PROMPT-MERGE-03 — origin/main(c692285, 보안 1단계) 병합 + alembic 재일직선화 + push 준비

## 배경 (MERGE-02 종료 지점)
- 로컬: `42ba98a`(병합) → `ce1f65d`(feat testfk 13.9-72) → `2dee27c`(docs), 미push, 클린 트리
- 원격: `7ac30d8` → `c692285` 로 4커밋 이동 (보안 1단계, auth 계열)
  - 신규 마이그레이션: `20261001_0000_1c3e5a7b9d20_auth_security_phase1.py`
  - 겹침 예상: `backend/app/api/auth.py`, `backend/app/core/deps.py`, `backend/app/models/__init__.py`, `ClaudeICFR.md`, `infra/nginx/icfr.conf`, `frontend/src/features/auth/*`
- 로컬 DB: `6b6d7fd94f0d`(FK-less, down_revision=`f5a6b7c8d9e0`) 적용 상태
- 운영 마이그레이션은 backend Dockerfile CMD(`alembic upgrade head && uvicorn`)로 **배포 시 자동 적용**

## 마스터 확정 사항
1. `git pull --no-rebase --no-commit` 로 병합 (rebase 금지 — 로컬에 병합 커밋 존재)
2. 충돌 기준: auth 계열은 **원격(보안 1단계)이 정본**. 로컬 hunk 는 로컬 커밋 메시지로 의도가 확인되는 것만 살림. 애매하면 중단
3. `ClaudeICFR.md` §14: 양쪽 줄 모두 보존, 날짜순 정렬. §13 번호는 원격 유지, 로컬 신규 항목이 겹치면 뒤 번호로 재배치(선례 동일)
4. alembic: `6b6d7fd94f0d` 를 `1c3e5a7b9d20` 위로 reparent (merge revision 금지)
5. `deficiencies` 양쪽 NULL 2건 원인 규명 (운영 리스크)
6. **push 금지** — 마스터가 직접

## 이번 프롬프트에서 허용하는 DB 변경 명령 (이것만)
- `docker compose exec backend alembic downgrade f5a6b7c8d9e0`
- `docker compose up -d --build backend` (entrypoint 가 upgrade head 수행)
- 위 재빌드 후 current 가 head 가 아닐 때만 `docker compose exec backend alembic upgrade head`

그 외: `merge --abort`, `reset --hard`, `checkout -- <file>`, `stash`, `alembic stamp`, seed, 운영 접근, push **금지**.
PowerShell 5.1 규칙(`;`, `Select-String`, `Set-Location`, bash 문법 금지, 965바이트 이하) 준수. 와일드카드 승인 요청 금지.
**node 프로세스 종료가 필요하면 반드시 마스터에게 먼저 묻는다.**

## 작업 순서

### 0. 상태 확인
- HEAD = `2dee27c`, 클린 트리, `git fetch` 후 origin/main = `c692285` 확인
- origin 이 또 움직였으면 **중단**하고 신규 커밋 목록 보고

### 1. 백업
- `git branch backup/pre-merge03-2dee27c 2dee27c`
- DB 덤프 (PowerShell `>` 리다이렉트 금지):
  - `docker compose exec -T postgres pg_dump -U icfr_user -d icfr_db -Fc -f /var/lib/postgresql/icfr_pre_merge03.dump`
  - `docker compose cp postgres:/var/lib/postgresql/icfr_pre_merge03.dump E:\claudeprojects\ICFR-backup\merge-20261001\icfr_pre_merge03.dump`
  - 크기 > 0, `pg_restore -l` 정상 확인

### 2. 기준 스냅샷 + deficiencies NULL 원인 규명 (읽기 전용)
- 5테이블(`control_risk_assessments`, `test_runs`, `control_assertions`, `deficiencies`, `design_assessments`)별: 전체 행 수 / `baseline_control_id` NOT NULL / `instance_control_id` NOT NULL / **둘 다 NULL**
- `deficiencies` 양쪽 NULL 2건:
  - 해당 행의 기존 통제 참조 컬럼 값, 그 통제의 `code` 와 tenant, `baseline_controls` 에 같은 code·tenant 가 있는지
  - 5테이블 CHECK 제약 정의 전문(`pg_get_constraintdef`) — 둘 다 NULL 을 허용하는 구조인지
  - MERGE-02 보고의 "매칭 불가 0건"과 왜 다른지
  - 결론: 정상 설계(예: 통제 미연결 미비점 허용)인지, backfill 누락인지 판정 + **운영에서 같은 상황 발생 시 마이그레이션이 실패하는지/NULL 로 남는지**

### 3. 병합
- `git pull --no-rebase --no-commit origin main`
- 충돌 파일마다 base→원격 / base→로컬 hunk 대조 표 작성 후 해소
  - auth 계열: 원격 정본, 로컬 hunk 는 의도 근거(커밋 해시·메시지) 있을 때만 유지
  - `ClaudeICFR.md`: §14 양쪽 보존·날짜순, §13 번호 겹침 시 로컬을 뒤 번호로. 옛 번호 참조(문서+코드 주석) 전수 갱신
- 충돌 마커 0건(`Select-String -Pattern '^(<<<<<<<|=======|>>>>>>>)'`, 해소 파일 대상), `git diff --name-only --diff-filter=U` 0건
- **중단 조건:** 의도 불명 hunk / 원격 보안 로직을 약화시키는 해소가 필요해 보이는 경우

### 4. alembic 재일직선화
- `1c3e5a7b9d20` 의 `down_revision` = `f5a6b7c8d9e0` 인지, 5테이블을 건드리지 않는지 확인
- 정적 그래프: head 2개(`1c3e5a7b9d20`, `6b6d7fd94f0d`) 확인
- `docker compose exec backend alembic downgrade f5a6b7c8d9e0` → current = `f5a6b7c8d9e0`
- `6b6d7fd94f0d` 의 `down_revision`·docstring `Revises:` → `1c3e5a7b9d20`, 재배치 이력 1줄 추가, `git add`
- 정적 그래프 재분석: head 1개, `… → f5a6… → 1c3e… → 6b6d…`
- `docker compose up -d --build backend` → healthy, Traceback 없음
- 검증: heads/current = `6b6d7fd94f0d`, `1c3e5a7b9d20` 이 만드는 테이블·컬럼 존재(파일에서 목록 추출), 5테이블 스냅샷 = 2단계와 일치
- **중단 조건:** `1c3e` 부모가 `f5a6` 아님 / 5테이블 겹침 / upgrade 실패 / 스냅샷 불일치 → 복구 시도 없이 덤프 경로와 상태 보고

### 5. 커밋 전 검증
- 백엔드 테스트: CI 방식(컨테이너 sqlite). 기지 실패 2건(`test_help_texts.py` 2건, ADR-0035 §6) 외 신규 실패 0건이어야 함
- 프론트: 병합으로 `package.json`/`package-lock.json` 이 바뀌었으면 `npm ci` (잠금 발생 시 마스터에게 프로세스 종료 여부 질문), 아니면 생략
  - `npx tsc --noEmit` → `npx vitest run`
- 실패 시 커밋하지 말고 보고

### 6. 커밋 (push 금지)
1. 병합 커밋: 충돌 해소 + reparent 포함 → `git commit --no-edit`
2. docs 커밋: `ClaudeICFR.md` §14 1줄 — "origin/main(c692285 보안 1단계) 병합, alembic 6b6d7fd94f0d → 1c3e5a7b9d20 reparent"
   - `git add ClaudeICFR.md; git commit -m "docs: 보안 1단계 병합 및 alembic 재일직선화 기록"`
- `git status` 클린, `git log --oneline -6`

### 7. push 직전 재확인 (실행 금지, 보고만)
- `git fetch` → origin/main 이 `c692285` 그대로인지
  - 그대로: 마스터용 명령 `git push origin main` 제시
  - 움직임: 신규 커밋 목록, alembic 신규 파일 유무, 로컬 변경 파일과 겹침 여부를 표로 보고 (경량=마이그레이션·겹침 없음 / 중량=있음)
- push 시 운영 자동 적용 마이그레이션 순서: `1c3e5a7b9d20`(원격 이미 운영 적용 여부 근거 포함) → `6b6d7fd94f0d`(운영 최초)
- push 후 마스터가 볼 항목: CI 결과, Deploy 결과, 운영 backend 기동 로그의 alembic 단계

## 완료 보고 형식
1. 백업(브랜치·덤프)
2. 스냅샷 전/후 표 + deficiencies NULL 판정과 운영 리스크
3. 충돌 파일별 해소 표
4. alembic 최종 계보
5. 테스트 결과(BE / FE)
6. 커밋 해시 + 클린 트리 여부
7. push 직전 fetch 결과와 push 명령(또는 추가 병합 필요 판정)
8. EVAL-01 재개 가능 여부
