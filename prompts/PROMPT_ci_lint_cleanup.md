# PROMPT — CI lint 부채 정리 및 배포 게이트 연결

## 배경

CI(`ci.yml`)가 2026-08-11 이후 연속 실패 중이다. 원인은 `ruff check .` 171건.
**lint 스텝이 pytest보다 앞이라 테스트가 한 번도 실행되지 않았다.** 로컬 128 passed만 믿고 있던 상태다.
곧 self-hosted runner를 붙여 자동 배포를 켜므로, 그 전에 CI를 복구하고 배포 게이트를 연결한다.

## 절대 원칙

1. **한 커밋 = 한 원인.** 아래 4개 커밋으로 분리한다. 절대 한 번에 묶지 않는다.
2. **각 커밋 직후 pytest를 재실행**해 `128 passed / 6 xfailed / 0 failed`가 유지되는지 확인한다. import 정렬이 순환 참조를 건드릴 수 있다.
3. **회귀 가드**: 작업 시작 전 기준선 pytest 결과를 먼저 남긴다. 그것과 대조한다.
4. 추정 금지. ruff 출력과 pytest 출력의 **실제 텍스트**를 근거로 보고한다.

## 사전 준비

1. Docker Desktop 기동 → `docker version`으로 Server 응답 확인
2. `git pull --no-rebase` (Regina push 반영)
3. **기준선 확보**: `pytest` 실행 결과를 기록. 128 passed / 6 xfailed가 아니면 **여기서 중단하고 보고**한다.

---

## 커밋 1 — alembic 버전 파일 lint 제외

`alembic/versions/` 하위 마이그레이션 파일은 **이미 적용된 이력**이다. 내용을 고치는 것은 히스토리 조작에 가깝고, 얻는 이득이 없다.

`backend/pyproject.toml`의 ruff 설정에 `per-file-ignores` 또는 `exclude`로 `alembic/versions/*`를 제외한다.
어느 쪽이 적절한지는 현재 설정 구조를 보고 판단하되, **마이그레이션 파일 자체는 수정하지 않는다.**

커밋: `chore(lint): alembic 버전 파일을 ruff 검사 대상에서 제외`

## 커밋 2 — F821 5건 설정 예외 처리

대상: `app/models/remediation.py:40,112,137`, `app/models/test_module.py:131`, `app/models/user_mgmt.py:17`

SQLAlchemy 문자열 타입 힌트(`"Control"`, `"User"`)로, 런타임에 레지스트리로 해석되므로 **실제 오류가 아니다.**
동작하는 코드를 lint에 맞추려 비틀지 않는다. `per-file-ignores`로 해당 파일의 F821만 무시하거나, `TYPE_CHECKING` 블록 import로 해소하는 방법 중 **기존 코드 스타일에 맞는 쪽**을 선택하고 이유를 보고한다.

커밋: `chore(lint): SQLAlchemy 문자열 타입 힌트 F821 예외 처리`

## 커밋 3 — 자동 수정 가능분 일괄 처리

`ruff check . --fix` 실행 (I001 import 정렬, UP007/UP035/UP017 신문법, W292 개행 등)

- 실행 후 **`git diff --stat`으로 변경 파일 수와 라인 수를 확인**
- **pytest 재실행 필수.** import 정렬로 순환 참조가 드러나면 여기서 깨진다
- 실패 시 즉시 중단하고 어느 파일에서 깨졌는지 보고

커밋: `chore(lint): ruff 자동 수정 적용 (import 정렬·신문법 전환)`

## 커밋 4 — 잔여 수동 수정

`ruff check .` 재실행 후 남은 항목을 개별 판단해 수정한다.
**동작을 바꾸는 수정이 필요하면 하지 말고 보고**한다. 스타일 문제로 로직을 건드리지 않는다.

목표: `ruff check .` → `All checks passed!`

커밋: `chore(lint): ruff 잔여 위반 수동 수정`

## 커밋 5 — deploy.yml에 CI 통과 게이트 추가

현재 `deploy.yml`은 main push 시 곧바로 빌드·배포한다. **lint/test 실패 코드가 서버에 올라갈 수 있다.**

`deploy.yml`의 `build` job 앞에 검증 job을 추가하고, `build`가 `needs`로 그것을 참조하게 한다.
검증 내용은 `ci.yml`의 lint·test 스텝과 동일하게 맞춘다(제로 추상화 — reusable workflow 등 추상화 도입하지 말고 필요한 스텝을 직접 기술).

`ci.yml`은 수정하지 않는다.

커밋: `ci(deploy): 배포 전 lint·test 통과를 필수 조건으로 추가`

---

## 검증

1. `ruff check .` → All checks passed
2. `pytest` → **128 passed / 6 xfailed / 0 failed** (기준선과 동일)
3. 위 둘의 실제 출력 텍스트를 보고에 포함
4. `git log --oneline -5`로 커밋 분리 확인

## 커밋·push 규칙

- `git add`는 **명시적 경로 지정**. `git add .` 금지
- 5개 커밋 후 **push까지 자동 진행**한다. lint 정리와 CI 복구는 되돌리기 쉬운 작업이고, Regina가 push 대기 중이라 지연이 더 위험하다
- push 후 GitHub Actions에서 CI가 **초록으로 바뀌는지 확인**하고 결과를 보고한다

## 보고 형식

- 커밋별 해시·메시지·변경 파일 수
- 커밋 1·2에서 선택한 방식과 그 이유
- 커밋 3의 `git diff --stat` 요약
- ruff·pytest 최종 출력
- GitHub Actions CI 결과 (성공/실패)
