# PROBE: canEditHierarchy 역할 판정 소스 조사 (읽기 전용)

## 목적
`canEditHierarchy()` 실구현에 필요한 **단 하나의 미확인 사항**을 확인한다:
**FE가 현재 로그인 사용자의 "테넌트 역할(`user_roles`)"을 읽을 수 있는가?**

배경: hierarchy 편집 게이트는 백엔드 `require_write`를 미러링한다 — `external_auditor`면 편집 불가(`false`), 그 외 `true`. 판정 소스는 반드시 **`user_roles`(테넌트 단위 역할)**여야 한다. `users.role`(시스템 admin)이나 `user_tenant_access.role`이 아니다 (`docs/api/org-contract.md` §5.1 — admin 계정이라도 자동 편집권 없음). FE가 엉뚱한 role store를 보면 게이팅이 통째로 틀린다.

## 제약 (엄수)
- **읽기 전용.** 파일 편집·생성·커밋·배포·서버 기동 전부 금지. 순수 조사만.
- 토큰 최적화: 전체 통독 금지. 아래 검색어로 관련 파일만 찾아 필요한 구간만 읽는다.
- 검색은 내장 Grep/Glob/Read 사용. 터미널을 쓸 경우 PowerShell 5.1 규칙(`grep`→`Select-String`, `&&`→`;`).
- 이 저장소는 FE+백엔드 공용이다. **A는 FE, B는 백엔드**에서 확인한다.

## A. FE 측 조사
1. `canEditHierarchy` 정의 위치·시그니처·현재 반환값 확인 (현재 `true` 하드코딩 예상).
2. 현재 로그인 사용자를 FE 어디서 들고 있는가 — auth context/store/hook.
   검색어: `canEditHierarchy`, `useAuth`, `AuthContext`, `AuthProvider`, `currentUser`, `useCurrentUser`, `/me`, `auth/me`, `users/me`
3. 그 사용자 객체에 **역할 필드**가 있는가? 있으면 필드명과 정확한 접근 경로(예: `auth.user.role`). 그 값이 3개 store 중 무엇에 해당하는가 — `users.role`(시스템) / `user_tenant_access.role` / `user_roles`(테넌트)?
4. `user_roles`는 테넌트 scoped다. FE에 **활성 테넌트 컨텍스트**가 있는가? (`tenantId`, `activeTenant`, `TenantContext` 등) 역할이 활성 테넌트 기준으로 잡히는지 확인.

## B. 백엔드 측 조사 (FE가 소비하는 값의 실제 출처)
5. 로그인 엔드포인트와 현재 사용자 조회 엔드포인트(`/auth/login`, `/me`, `/users/me` 등)의 **응답 스키마**를 찾는다.
   검색어: `login`, `/me`, `current_user`, `UserResponse`, `TokenResponse`
6. 그 응답이 **테넌트 역할(`user_roles`)을 실어 보내는가?** `external_auditor` 사용자가 로그인하면 FE가 그 사실을 응답에서 알 수 있는가? JWT 토큰 payload에 역할이 들어있다면 payload 구성도 확인.

## 보고 형식 (간결하게, 코드 변경 없이 답만)
- **Q1** canEditHierarchy 위치 / 현재 반환:
- **Q2** FE 현재 사용자 role 필드 유무 + 정확한 접근 경로:
- **Q3** 그 role의 출처 store (`users.role` / `user_tenant_access.role` / `user_roles`):
- **Q4** FE 활성 테넌트 컨텍스트 유무 + 위치:
- **Q5** 백엔드 로그인/me 응답이 테넌트 역할을 싣는가 (Y/N + 근거 `파일:라인`):
- **판정** → 「FE에서 바로 `external_auditor` 판정 가능」 / 「백엔드 핸드오프(응답에 `user_roles` 추가) 필요」 중 하나로 결론.

끝나면 위 6줄만 보고한다. **파일은 하나도 건드리지 않는다.**
