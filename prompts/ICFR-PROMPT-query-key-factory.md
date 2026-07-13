# ICFR-PROMPT: Query Key 팩토리 중앙화

## 목적
TanStack Query의 queryKey가 5개 모듈에 흩어져 있어, 향후 멀티테넌시 Phase 2에서
테넌트 프리픽스를 추가할 때 전 모듈을 헤집어야 한다.
지금 **팩토리 한 곳으로 모아두면**, tenant_id가 확보되는 순간 팩토리 파일 하나만
고쳐서 프리픽스를 붙일 수 있다. (retrofit 방지)

**이번 작업의 동작 변화는 0이어야 한다.** 키 문자열은 기존과 완전히 동일하게 유지한다.

## 배경 (참고)
백엔드가 이미 `X-Tenant-Id`를 검증 중이나, FE가 자기 tenant_id를 알 경로가 없어
(JWT·`/me` 모두 미포함) 헤더 주입 작업은 백엔드 대기 중이다.
이 작업은 그 대기와 무관하게 선행할 수 있는 부분이다.

---

## 1. 사전 조사 (먼저 보고할 것)
1. 현재 `useQuery` / `useMutation` / `invalidateQueries` / `setQueryData` /
   `removeQueries` 등에서 사용 중인 **모든 queryKey를 전수 조사**해서 목록으로 보고한다.
   - 모듈별(RCM / Test / Evidence / Remediation / Users)로 정리
   - 파일 경로 + 키 형태 함께 표기
   - **추정 금지.** 실제 코드 grep 결과 기준.
2. 키 구성이 일관되지 않은 부분(예: 어떤 곳은 `['controls']`, 어떤 곳은
   `['control-list']`)이 있으면 함께 지적한다.

조사 결과를 보여준 뒤 구현으로 넘어간다. (별도 승인 대기 불필요)

---

## 2. 구현

### 2-1. `src/lib/queryKeys.ts` 신설
- 모듈별 팩토리를 계층 구조로 정의한다. 예:

```ts
export const queryKeys = {
  rcm: {
    all: () => ['rcm'] as const,
    controls: (filters?: unknown) => ['rcm', 'controls', filters] as const,
    control: (id: string) => ['rcm', 'controls', id] as const,
  },
  // test / evidence / remediation / users 동일 패턴
} as const;
```

- **중요:** 위는 형태 예시일 뿐이다. 실제 키 문자열은 **1번 조사에서 나온 기존 키를
  그대로 보존**해야 한다. 기존 키가 `['controls', filters]` 였다면 팩토리도
  `['controls', filters]`를 반환해야 한다. 임의로 이름을 바꾸지 말 것.
- 키 이름이 모듈 내에서 불일치하는 경우에만, 하나로 통일하고 **어디를 바꿨는지 보고**한다.
- 향후 테넌트 프리픽스를 붙일 지점을 주석으로 명시해둔다.
  예: `// TODO(tenant): 확보 시 여기서 tenantId를 최상위에 prepend`

### 2-2. 호출부 교체
- RCM / Test / Evidence / Remediation / Users 5개 모듈의
  `useQuery`, `useMutation`의 `invalidateQueries`, `setQueryData`, `removeQueries`
  전부를 팩토리 참조로 교체한다.
- 인라인 배열 리터럴 queryKey가 코드에 남아있지 않아야 한다.

---

## 3. 검증

### 3-1. 빌드
- `npm run build` 통과 필수.
- 인라인 queryKey 잔존 여부를 grep으로 재확인하고 결과를 보고한다.

### 3-2. 브라우저 확인 (환경 기동 포함)
```powershell
Set-Location E:\claudeprojects\ICFR
docker compose up -d
docker compose ps
```
프론트 dev 서버는 별도 터미널에서 기동.

로그인(`admin@acme.example / admin123`) 후, **각 모듈에서 CRUD 후 목록이 자동 갱신되는지**
확인한다. (invalidation 키 불일치가 이번 작업의 유일한 회귀 리스크다.)

- RCM: 컨트롤 생성 → 목록 즉시 반영 / 수정 → 상세+목록 반영 / 삭제 → 목록에서 사라짐
- Test: TestRun 생성 → 목록 반영 / 워크플로 전이 → 상태 반영 / TestStep CRUD 반영
- Evidence: 파일 업로드 → 목록 반영 / 삭제 → 목록에서 사라짐
- Remediation: Deficiency·RemediationPlan 생성/수정/워크플로 전이 반영
- Users: 사용자·롤 CRUD 반영

**"새로고침해야 보이는" 화면이 하나라도 있으면 invalidation 키가 어긋난 것이다.**
해당 지점을 찾아 수정하고, 무엇이 어긋났었는지 보고한다.

결과는 요약하지 말고 확인한 항목별로 그대로 보고할 것.

---

## 4. Git
- 브랜치: `refactor/query-key-factory`
- 커밋 전 `npm run build` 통과 필수
- main 머지는 `--no-ff`
- 머지 후 `ClaudeICFR.md` 12·14 섹션 갱신
- **저위험 리팩터링이므로 push까지 자동 진행 승인.**
  단, 브라우저 확인에서 갱신 안 되는 화면이 발견되면 중단하고 보고할 것.

## 5. 환경 제약 (반드시 준수)
- 경로는 **E 드라이브**: `E:\claudeprojects\ICFR`
- PowerShell: `&&`, `||`, `$(...)`, heredoc, `/dev/null` 전부 금지
- `cd` 대신 `Set-Location`
- 한 명령이 965바이트를 넘지 않도록 나눠서 실행
- 설계 판단은 위 지침대로 진행하고, 매번 허가를 묻지 말 것

---

ICFR-PROMPT-query-key-factory.md 진행해줘
