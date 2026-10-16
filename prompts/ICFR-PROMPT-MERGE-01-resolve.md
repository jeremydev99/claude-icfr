# ICFR-PROMPT-MERGE-01 — origin/main 병합 해소 (수동 병합본 채택 + §13 재배치 + alembic 계보 정리)

## 배경
EVAL-01 §0 게이트에서 중단됨. `git pull` 병합이 미완료 상태다.
- HEAD `f6d9bcc`(로컬 10커밋 앞) / MERGE_HEAD `7ac30d8`(= origin/main, 63커밋)
- 충돌 미해소: `ClaudeICFR.md`(UU) 1건
- 인덱스 ≠ 워크트리 7건: 워크트리에 13.9-55 testfk-app-transition 수동 병합본 존재

## 마스터 확정 사항
1. 7개 파일의 **워크트리 수동 병합본 채택** (단, 양쪽 변경 포함 검증 후)
2. `ClaudeICFR.md` §13: **origin 54~70 유지, 로컬 2건 → 71·72 재배치**
3. alembic: head 2개면 **미push 로컬 마이그레이션 `6b6d7fd94f0d`를 원격 최신 head로 reparent** (merge revision 생성 금지)
4. **push 금지** — 마스터가 직접 push

## 절대 규칙
- `git merge --abort`, `git reset --hard`, `git checkout -- <file>`, `git stash` 금지 (수동 병합본 유실 위험)
- `alembic upgrade/downgrade/stamp`, seed, DB 쓰기 금지. `alembic heads/current/history`(읽기)만 허용
- PowerShell 5.1: `&&` 금지(`;`), `grep` 금지(`Select-String`), `Set-Location` 사용, bash 문법 금지, 단일 명령 965바이트 이하
- 와일드카드 세션 승인 요청 금지
- 아래 "중단 조건"에 걸리면 즉시 멈추고 보고

## 작업 순서

### 0. 상태 재확인
- HEAD = `f6d9bcc`, `.git/MERGE_HEAD` = `7ac30d8` 인지 확인. 다르면 **중단**
- `git status` 로 UU 1건 + 인덱스≠워크트리 7건이 보고와 동일한지 확인

### 1. 백업 (가장 먼저)
- `git branch backup/pre-merge-f6d9bcc f6d9bcc`
- 7개 파일 + `ClaudeICFR.md` 의 **현재 워크트리 사본**을 `E:\claudeprojects\ICFR-backup\merge-20261001\` 에 원래 상대경로 그대로 복사 (`New-Item -ItemType Directory -Force` + `Copy-Item`)
- 복사본 개수·크기 확인 후 진행

### 2. 수동 병합본 검증 (7개 파일)
대상:
- `backend/app/api/rcm.py`
- `backend/app/api/remediation.py`
- `backend/app/api/test_module.py`
- `backend/app/models/remediation.py`
- `backend/app/models/test_module.py`
- `backend/app/services/control_resolver.py`
- `backend/alembic/**/6b6d7fd94f0d_test_family_control_split.py` (`Get-ChildItem -Recurse -Filter` 로 경로 확정)

각 파일마다:
- `git merge-base f6d9bcc 7ac30d8` 로 base 확보
- base→origin(`7ac30d8`) 변경 hunk 와 base→로컬(`f6d9bcc`) 변경 hunk 를 각각 뽑고, **양쪽 hunk 가 모두 워크트리에 반영됐는지** 대조
- `python -m py_compile <파일>` 로 문법 확인 (로컬 python 없으면 생략하고 보고에 명시)
- 결과를 표로 정리: 파일 / origin 반영 / 로컬 반영 / 문법 / 비고
- 전부 OK면 7개 파일 `git add`

**중단 조건:** 어느 한쪽 hunk 라도 누락·변형됐으면 수정하지 말고 해당 hunk 를 보여주며 중단

### 3. ClaudeICFR.md 충돌 해소
- 충돌 구간(약 2239–2283행): origin 54~70 그대로, 로컬 항목 "54 역할 UI(ROLE_ASSIGN_OPTIONS 분리)" → **71**, "55 Test 계열 FK 정체성 분리" → **72**
- 문서 전체에서 이 두 로컬 항목의 옛 번호(§13.54, §13.55 등) 참조를 `Select-String` 으로 전수 조사 → 두 항목을 가리키는 것이 명확한 곳만 71·72로 수정. origin 54·55를 가리키는 참조는 건드리지 않음. 애매한 참조는 수정 없이 목록으로 보고
- 충돌 마커 잔존 확인: `Select-String -Path ClaudeICFR.md -Pattern '^(<<<<<<<|=======|>>>>>>>)'` 결과 0건
- `git add ClaudeICFR.md`

### 4. alembic 계보 정리
- versions 디렉터리의 모든 리비전 파일에서 `revision` / `down_revision` 을 읽어 **정적으로 그래프를 구성**하고 head 목록 산출
- 원격 신규 4건(`c2d3e4f5a6b7` → `d3e4f5a6b7c8` → `e4f5a6b7c8d9` → `f5a6b7c8d9e0` 예상)이 일직선인지 확인
- `docker-compose.yml` 에서 backend 가 소스를 볼륨 마운트하는지 확인 → 마운트하면 `docker compose exec backend alembic heads` 로 교차 확인
- `docker compose exec backend alembic current` 로 **로컬 DB 적용 리비전** 확인 (읽기 전용)

판정:
- head 1개 → 수정 없음
- head 2개, 로컬 DB에 `6b6d7fd94f0d` **미적용** → `6b6d7fd94f0d` 의 `down_revision` 과 docstring `Revises:` 를 원격 최신 head 로 변경, `git add`
- reparent 전, `6b6d7fd94f0d` 가 원격 4건과 **같은 테이블/컬럼을 건드리는지** 확인해 보고에 명시

**중단 조건:** 로컬 DB에 `6b6d7fd94f0d` 가 이미 적용됨 / head 3개 이상 / 원격 4건이 일직선 아님 / 같은 테이블 충돌 의심

### 5. 커밋 전 검증
- `git diff --name-only --diff-filter=U` 결과 0건
- 백엔드 테스트: `.github/workflows` 의 CI 실행 방식을 그대로 따름. 실행에 `alembic upgrade` 또는 개발 DB 쓰기가 필요하면 **실행하지 말고 보고**
- 프론트: `Set-Location E:\claudeprojects\ICFR\frontend; npm ci` (lock 기준 설치, lock 변경 없음 확인) → `npx tsc --noEmit` → `npx vitest run`
- 실패 시 커밋하지 말고 실패 내역 보고

### 6. 커밋 (push 금지)
- 병합 커밋: `git commit --no-edit`
- 이어서 docs 커밋 분리: `ClaudeICFR.md` §14 changelog 에 1줄 — "origin/main 병합 해소: 13.9-55 수동 병합본 채택, §13 로컬 2건 71·72 재배치, alembic 6b6d7fd94f0d reparent(해당 시)"
  - `git add ClaudeICFR.md; git commit -m "docs: origin/main 병합 해소 기록"`
- `git log --oneline -5`, `git status` 로 클린 트리 확인

### 7. push 준비 정보 (실행 금지, 보고만)
- `.github/workflows` 에서 Deploy 시 **운영 DB에 `alembic upgrade` 가 자동 실행되는지** 확인
- push 시 운영에 적용될 마이그레이션 목록(원격 4건은 이미 운영 적용 여부, 로컬 `6b6d7fd94f0d` 신규 적용 예정)

## 완료 보고 형식
1. 백업 위치(브랜치명, 폴더)
2. 7개 파일 검증 표
3. ClaudeICFR.md 수정 내역 + 애매 참조 목록
4. alembic head 판정과 조치, DB 적용 상태
5. 테스트 결과 (BE / FE)
6. 커밋 해시 2개, 클린 트리 여부
7. push 시 운영 영향 요약 + 마스터용 push 명령
8. EVAL-01 재개 가능 여부
