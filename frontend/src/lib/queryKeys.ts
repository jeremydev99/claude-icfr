// TanStack Query key 팩토리 — 5개 모듈(RCM/Test/Evidence/Remediation/Users)의
// queryKey를 한 곳에 모은다. 키 문자열은 리팩터링 전과 완전히 동일하게 유지한다.
// TODO(tenant): tenant_id 확보 시 각 함수 반환 배열의 최상위에 tenantId를 prepend

export const queryKeys = {
  rcm: {
    controls: (params?: unknown) => ['controls', params] as const,
    controlsAll: () => ['controls'] as const,
    rawc: (controlId?: string | null, fiscalYear?: number) =>
      ['rawc', controlId, fiscalYear] as const,
    processes: () => ['processes'] as const,
    subProcesses: (processId?: string) => ['sub-processes', processId] as const,
    risks: (subProcessId?: string) => ['risks', subProcessId] as const,
  },
  test: {
    testRuns: (params?: unknown) => ['testRuns', params] as const,
    testRunsAll: () => ['testRuns'] as const,
    testRunDetail: (id?: string | null) => ['testRunDetail', id] as const,
    testRunHistory: (id?: string | null) => ['testRunHistory', id] as const,
    testSteps: (runId?: string | null) => ['testSteps', runId] as const,
  },
  evidence: {
    files: (params?: unknown) => ['evidence-files', params] as const,
    filesAll: () => ['evidence-files'] as const,
  },
  remediation: {
    plans: (params?: unknown) => ['remediationPlans', params] as const,
    plansAll: () => ['remediationPlans'] as const,
    planDetail: (id?: string | null) => ['remediationPlanDetail', id] as const,
    planHistory: (id?: string | null) => ['remediationPlanHistory', id] as const,
    deficiencies: (params?: unknown) => ['deficiencies', params] as const,
    deficienciesAll: () => ['deficiencies'] as const,
  },
  users: {
    list: (params?: unknown) => ['users', params] as const,
    detail: (id?: string | null) => ['users', id] as const,
    all: () => ['users'] as const,
    roles: (params?: unknown) => ['userRoles', params] as const,
    rolesAll: () => ['userRoles'] as const,
  },
} as const
