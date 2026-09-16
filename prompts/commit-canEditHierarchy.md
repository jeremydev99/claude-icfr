# COMMIT: canEditHierarchy can_write 전환 — feat + docs 분리

## 전제 (이미 완료됨)
구현·단위테스트(29 passed, 종료코드 0)·브라우저 검증(편집 버튼 유지 + `/me can_write=true` 실측) 전부 통과. **이 프롬프트는 커밋+push만** 한다. 코드 재구현·테스트 재실행 불필요(원하면 `git status`로 파일셋 확인만).

마이그레이션 파일은 이 커밋들에 **없음** → CLAUDE.md §8(마스터 직접 push) 비해당, Claude Code push 가능. 저위험 FE 게이트 + 브라우저 검증 완료라 push 자동 승인 대상. **push = origin/main 반영 → GitHub Actions 프로덕션 배포 트리거(다운타임 있음).**

## 제약
- PowerShell 5.1 (`&&` 금지→`;`/분리, `grep`→`Select-String`, `cd`→`Set-Location`).
- 커밋 분리 원칙 — feat와 docs 별도 커밋.
- **아래 명시한 파일만** 스테이징. 다른 untracked 프롬프트 파일은 건드리지 말 것(STEP 3 참조).

## STEP 0 — 파일셋 확인
```
Set-Location E:\claudeprojects\ICFR
git status
```
기대 **수정**: `frontend/src/features/auth/store.ts`, `frontend/src/features/rcm/permissions.ts`, `frontend/src/features/rcm/api/hierarchy.test.ts`, `frontend/package.json`, `frontend/package-lock.json`
기대 **신규**: `frontend/src/features/rcm/permissions.pure.ts`, `frontend/src/features/rcm/permissions.test.ts`
어긋나면 멈추고 보고.

## STEP 1 — feat 커밋 (7개 파일)
```
git add frontend/src/features/auth/store.ts frontend/src/features/rcm/permissions.ts frontend/src/features/rcm/permissions.pure.ts frontend/src/features/rcm/permissions.test.ts frontend/src/features/rcm/api/hierarchy.test.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(rcm): canEditHierarchy를 /me can_write 기반으로 전환 (ADR-0031 seam 실구현)"
```

## STEP 2 — ClaudeICFR.md 편집

**(가) §14 변경 로그** — `## 14. 변경 로그` 헤더와 `> 날짜 / 변경자 / 요약. 최신이 위로.` 안내 바로 다음, **맨 위**(기존 `2026-09-04` 항목 위)에 아래 항목을 그대로 삽입:

```
- **2026-09-09 / Regina + Claude** — **canEditHierarchy를 /me `can_write` 기반으로 전환 (ADR-0031 seam 실구현)** (`prompts/impl-canEditHierarchy.md`, `prompts/probe-role-source.md`). 2026-09-04(`d2c4002`)에 무조건 `true` 하드코딩으로 남긴 편집 게이트 seam을 실제 판정으로 교체. ①**막힌 지점 조사(read-only)**: FE가 현재 사용자의 테넌트 운영 역할(`user_roles`)을 받을 수 없음을 확인 — `/me`는 `UserTenantAccess` join만 조회해 `tenants[].role`(=`user_tenant_access.role`)만 내려오고, `require_write`가 보는 `user_roles`(`external_auditor` 판정 근거)는 응답에 없었다. → 백엔드 핸드오프. ②**백엔드 반영(`5620b68`, 배포 완료)**: `/me` top-level에 `can_write: bool`(=`core/permissions.can_write`, `require_write`와 **동일 함수**)와 `tenant_roles: string[]` 추가. 원본 역할 목록 대신 계산된 capability를 함께 내려 FE가 `external_auditor`를 재판정하지 않고 `can_write` 하나만 신뢰(권한 단일 소스, 서버 403 최종). `active_tenant_id`가 생성순 첫 테넌트를 반환하던 버그도 함께 수정 — 이제 `X-Tenant-Id` 기준으로 `tenant_roles`/`can_write`가 따라온다(테넌트 1개라 미발현, 전환 UI 시 FE가 헤더 실어야 함). ③**FE 구현**: `auth/store.ts` `UserProfile`에 두 필드 추가(spread 매핑이라 타입만 조임). `permissions.pure.ts` 신규 — `canEditHierarchyForUser(user)=user?.can_write ?? false`, zustand 비의존 순수 함수라 jsdom 없이 node 환경 테스트 가능. `permissions.ts` `canEditHierarchy()`가 `useAuthStore.getState().user`를 이 헬퍼에 위임, user null → `false` 폴백. ④**부수 — CI 게이트 복구**: `vite.config.ts`가 기본 환경을 `jsdom`으로 선언하나 미설치라, 테스트 전건 통과에도 vitest가 MISSING DEPENDENCY로 종료코드 1 → CI 빌드 실패로 잡히던 상태. `npm install -D jsdom`으로 해소(기본 환경을 node로 낮추는 대안은 컴포넌트 테스트 도입 시 retrofit이라 기각). ⑤**테스트**: `permissions.test.ts` 신규(node 환경, true/false/null 3케이스), `hierarchy.test.ts`의 canEditHierarchy 케이스는 이관 주석 남기고 제거. 전체 3 files/29 passed, **종료코드 0**. ⑥**검증**: 함께 딸려온 evidence 마이그레이션 2건(`b4c5d6e7f8a9`·`c5d6e7f8a9b0`) 실측 — 전부 nullable `add_column`, 파괴적 op 0건 확인 후 재기동(`alembic current`=`c5d6e7f8a9b0`). 브라우저: 일반 계정 계층 관리 편집 버튼 정상 노출(회귀 없음) + Network `/me` `can_write: true` 실측. ⑦**관찰**: `tenant_roles`가 `["Administrator","Tester"]` — 근거 없는 legacy 3역할(13.9-24), 이번 게이트 무관(can_write만 사용), 역할 UI 착수 시 처리. **다음**: `tenant_roles` 활용 역할 UI(신규 5역할 한국어/기존 3역할 영문), `external_auditor` 음성 케이스 브라우저 검증(해당 역할 시드 계정 필요). 마이그레이션 파일은 이번 커밋에 없어 Claude Code push 가능.
```

**(나) §12.2 모듈별 구현 상태** — `RCM 관리` 행의 **비고 셀 맨 끝**에 이어붙임(기존 `...로컬 검증만(tsc·build·vitest), 브라우저·운영 미확인` 다음):

```
 **canEditHierarchy 실구현 완료(2026-09-09)** — 하드코딩 `true` → `/me can_write` 위임. `permissions.pure.ts` 순수 헬퍼 분리(node 환경 테스트), `UserProfile`에 `can_write`/`tenant_roles` 추가, jsdom 설치로 CI 종료코드 복구. 브라우저 검증(편집 버튼 유지 + can_write=true 실측) 완료.
```

**(다) §13** — canEditHierarchy seam 해소 반영:
- §13/§13.9에서 canEditHierarchy가 "무조건 true / ADR-0031 미확정"으로 남은 항목을 찾으면 해소로 갱신(취소선 + `✅ 완료 (2026-09-09) — /me can_write 위임`).
- `tenant_roles`가 legacy 3역할(Administrator/Tester)을 반환하는 관찰을 **13.9-24**(user_roles 기존 3행 의미 불명확)에 한 줄 연결.
- 역할 UI(신규 5역할 한/영 라벨, external_auditor 읽기전용은 이미 can_write에 반영)를 다음 작업으로 남김.
- **항목 번호를 새로 지어내지 말 것.** seam 항목이 §13에 명시적으로 없으면 §13.9 적절한 하위에 forward 한 줄만 추가하고 어디 넣었는지 보고.

## STEP 3 — docs 커밋 (ClaudeICFR.md + 이 작업 프롬프트 2개)
```
git add ClaudeICFR.md prompts/impl-canEditHierarchy.md prompts/probe-role-source.md
git commit -m "docs: canEditHierarchy 작업 반영 (§14/§12.2/§13) + 프롬프트 기록"
```
**나머지 untracked 2개는 이 커밋에서 제외**:
- `prompts/rcm_상위3계층_crud_ui.md` — `d2c4002` 상위3계층 CRUD 작업 소속(별건).
- `prompts/ICFR_역할모델_설명.docx` — 출처 불명, 확인 전 커밋 보류.
둘 다 그대로 두고 보고만 한다.

## STEP 4 — push
```
git push origin main
```

## 보고
- feat / docs 두 커밋 해시.
- §13 어디에 무엇을 넣었는지(항목 번호 신설 여부 포함).
- untracked 2개(`rcm_상위3계층_crud_ui.md`, `ICFR_역할모델_설명.docx`)를 그대로 남겼는지 확인.
- push 결과 + GitHub Actions 배포 트리거 여부(lint/test 게이트 통과는 Actions에서 확인).
