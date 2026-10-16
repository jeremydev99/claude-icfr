# ICFR-PROMPT-MERGE-02 — alembic 일직선화(A안) + 커밋 분리 + push 준비 보고

## 배경 (MERGE-01 중단 지점)
- 병합 진행 중: HEAD `f6d9bcc`, MERGE_HEAD `7ac30d8`. 백업 브랜치 `backup/pre-merge-f6d9bcc`, 백업 폴더 `E:\claudeprojects\ICFR-backup\merge-20261001\`
- 스테이징 완료: 7개 파일 + `ClaudeICFR.md`(§13 로컬 2건 → 71·72 재배치)
- alembic head 2개: `f5a6b7c8d9e0`(원격) / `6b6d7fd94f0d`(로컬, down_revision=`b1c2d3e4f5a6`). 테이블 충돌 없음
- **로컬 DB가 이미 `6b6d7fd94f0d` 적용 상태** → reparent 전 downgrade 필요
- backend 컨테이너는 소스 볼륨 마운트 없음(빌드 시점 코드 고정)

## 마스터 확정 사항
1. **A안**: 로컬 DB downgrade → reparent → 이미지 재빌드 → upgrade head
2. **커밋 3분리**: 병합 커밋 / feat 커밋(코드 6개) / docs 커밋
3. 코드 주석 `13.9-55` → `13.9-72` 갱신
4. **push 금지** — 마스터가 직접

## 이번 프롬프트에서 허용하는 DB 변경 명령 (이 3개만)
- `docker compose exec backend alembic downgrade b1c2d3e4f5a6`
- `docker compose up -d --build backend`
- `docker compose exec backend alembic upgrade head`

그 외: `merge --abort`, `reset --hard`, `checkout -- <file>`, `stash`, `alembic stamp`, seed 실행, 운영 접근 **금지**.
PowerShell 5.1 규칙(`;`, `Select-String`, `Set-Location`, bash 문법 금지, 965바이트 이하) 준수. 와일드카드 승인 요청 금지.

## 작업 순서

### 1. 사전 점검
- HEAD/MERGE_HEAD/스테이징 상태가 MERGE-01 종료 시점과 동일한지 확인. 다르면 **중단**
- `6b6d7fd94f0d` 파일의 `upgrade()` / `downgrade()` 를 읽고 보고:
  - `downgrade()` 가 실제 구현돼 있는지(`pass` 아님)
  - `upgrade()` 가 `baseline_control_id` / `instance_control_id` 를 기존 데이터에서 **backfill** 하는지
- 워크트리와 인덱스의 docstring 차이가 무엇인지 확인
- `docker compose exec backend alembic history` 에 `6b6d7fd94f0d` 가 보이는지(= 현재 이미지가 downgrade 가능한지) 확인

**중단 조건:** downgrade 미구현 / 현재 이미지에 6b6d7fd94f0d 없음

### 2. 로컬 DB 백업 + 기준 스냅샷
- 컨테이너 내부에 덤프 후 호스트로 복사 (PowerShell 리다이렉트 `>` 사용 금지 — 바이너리 손상):
  - `docker compose exec -T postgres pg_dump -U icfr_user -d icfr_db -Fc -f /var/lib/postgresql/icfr_pre_merge02.dump`
  - `docker compose cp postgres:/var/lib/postgresql/icfr_pre_merge02.dump E:\claudeprojects\ICFR-backup\merge-20261001\icfr_pre_merge02.dump`
  - 호스트 파일 크기 > 0, `pg_restore -l` 로 목록 조회 가능 확인
- 5개 테이블(`control_risk_assessments`, `test_runs`, `control_assertions`, `deficiencies`, `design_assessments`)별 기준 스냅샷 기록:
  - 전체 행 수, `baseline_control_id` NOT NULL 수, `instance_control_id` NOT NULL 수

### 3. downgrade (현재 이미지로)
- `docker compose exec backend alembic downgrade b1c2d3e4f5a6`
- `alembic current` = `b1c2d3e4f5a6` 확인

### 4. reparent
- `6b6d7fd94f0d` 의 `down_revision` → `'f5a6b7c8d9e0'`, docstring `Revises:` 도 동일하게 수정
- 정적 그래프 재분석: **head 1개(`6b6d7fd94f0d`)**, 체인 `b1c2d3e4f5a6 → c2d3… → d3e4… → e4f5… → f5a6… → 6b6d…` 확인
- `git add` 해당 마이그레이션 파일

### 5. 이미지 재빌드 + upgrade
- `docker compose up -d --build backend`
- `docker compose exec backend alembic heads` = 1개, `alembic history` 에 원격 4건 포함 확인
- `docker compose exec backend alembic upgrade head`
- 검증:
  - `alembic current` = `6b6d7fd94f0d`
  - 원격 테이블 존재: `help_texts`, `fs_accounts`, `fs_statements`, `fs_amounts`, `fs_statement_status_events`, `fs_template_links`, `scoping_accounts.fs_account_id`
  - 5개 테이블 스냅샷 재측정 → 2단계 기준과 **행 수·NOT NULL 수 일치** 확인
- `docker compose ps` 정상, `docker compose logs backend --tail 50` 에 Traceback 없음

**중단 조건:** upgrade 실패 / 스냅샷 불일치 → 복구 시도하지 말고 상태와 덤프 경로를 보고

### 6. 코드 주석 갱신
- `backend/` 내 `13.9-55` 참조를 `Select-String` 으로 전수 조사 → 13.9-55 testfk 항목을 가리키는 것만 `13.9-72` 로 수정 (예상 5곳). 목록 보고

### 7. 커밋 전 검증
- `git diff --name-only --diff-filter=U` 0건
- 백엔드 테스트: `.github/workflows` 의 CI 방식 그대로. 개발 DB(`icfr_db`)에 쓰기가 필요하면 실행하지 말고 보고
- 프론트: `Set-Location E:\claudeprojects\ICFR\frontend; npm ci` (lock 변경 없음 확인) → `npx tsc --noEmit` → `npx vitest run`
- 실패 시 커밋하지 말고 보고

### 8. 커밋 3분리 (push 금지)
1. **병합 커밋**: 코드 6개 파일을 인덱스에서만 내림(워크트리 유지)
   - `git restore --staged backend/app/api/rcm.py backend/app/api/remediation.py backend/app/api/test_module.py backend/app/models/remediation.py backend/app/models/test_module.py backend/app/services/control_resolver.py`
   - 스테이징 = ClaudeICFR.md 충돌 해소 + 마이그레이션 reparent + 원격 병합분인지 확인 후 `git commit --no-edit`
2. **feat 커밋**: 코드 6개 파일
   - `git add` 6개 → `git commit -m "feat(testfk): Test 계열 FK 앱 전환 - resolve_assertion_target 공용화 (13.9-72)"`
3. **docs 커밋**: `ClaudeICFR.md` §14 changelog 1줄 — "origin/main 병합 해소: §13 로컬 2건 71·72 재배치, alembic 6b6d7fd94f0d → f5a6b7c8d9e0 reparent(일직선), testfk 앱 전환 커밋(13.9-72)"
   - `git add ClaudeICFR.md; git commit -m "docs: origin/main 병합 해소 기록"`
- `git status` 클린 트리, `git log --oneline -6` 확인

### 9. push 준비 보고 (실행 금지)
- `git fetch` 후 origin/main 이 `7ac30d8` 그대로인지(그 사이 원격이 움직였는지)
- `.github/workflows` 의 Deploy 가 운영에서 `alembic upgrade head` 를 자동 실행하는지
- 운영 적용 예상: 원격 4건은 운영 기적용 여부(§14·워크플로 기록 근거), **`6b6d7fd94f0d` 는 운영 최초 적용**
- `6b6d7fd94f0d` 운영 영향 분석: 대상 5테이블, backfill 쿼리 방식, 운영 데이터에서 매칭 실패 가능성(NULL 남는 행), 락/소요 예상, 롤백 경로(downgrade)
- 마스터용 push 명령과 push 후 확인할 CI/Deploy 항목

## 완료 보고 형식
1. 사전 점검 결과(downgrade 구현·backfill 여부)
2. DB 덤프 경로, 스냅샷 전/후 표
3. alembic 최종 계보(head 1개)
4. 주석 갱신 목록
5. 테스트 결과(BE / FE)
6. 커밋 해시 3개 + 클린 트리 여부
7. push 시 운영 영향 분석 + push 명령
8. EVAL-01 재개 가능 여부
