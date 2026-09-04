// TanStack Query key 팩토리 — 5개 모듈(RCM/Test/Evidence/Remediation/Users)의
// queryKey를 한 곳에 모은다. tenant 프리픽스(['tenant', tenantId, '<module>', ...])로
// 캐시를 tenant별로 격리한다. tenantId는 각 모듈 훅 레이어에서 useActiveTenantId()로 읽어
// 첫 인자로 전달한다 — 컴포넌트 호출부(useControls(params) 등)는 변경하지 않는다.

type TenantId = string | null | undefined

const tenantSegment = (tenantId: TenantId) => tenantId ?? 'no-tenant'

export const queryKeys = {
  rcm: {
    controls: (tenantId: TenantId, params?: unknown) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'controls', params] as const,
    controlsAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'controls'] as const,
    rawc: (tenantId: TenantId, controlId?: string | null, fiscalYear?: number) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'rawc', controlId, fiscalYear] as const,
    processes: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'processes'] as const,
    subProcesses: (tenantId: TenantId, processId?: string) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'sub-processes', processId] as const,
    subProcessesAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'sub-processes'] as const,
    risks: (tenantId: TenantId, subProcessId?: string) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'risks', subProcessId] as const,
    risksAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'rcm', 'risks'] as const,
  },
  test: {
    testRuns: (tenantId: TenantId, params?: unknown) =>
      ['tenant', tenantSegment(tenantId), 'test', 'testRuns', params] as const,
    testRunsAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'test', 'testRuns'] as const,
    testRunDetail: (tenantId: TenantId, id?: string | null) =>
      ['tenant', tenantSegment(tenantId), 'test', 'testRunDetail', id] as const,
    testRunHistory: (tenantId: TenantId, id?: string | null) =>
      ['tenant', tenantSegment(tenantId), 'test', 'testRunHistory', id] as const,
    testSteps: (tenantId: TenantId, runId?: string | null) =>
      ['tenant', tenantSegment(tenantId), 'test', 'testSteps', runId] as const,
  },
  evidence: {
    files: (tenantId: TenantId, params?: unknown) =>
      ['tenant', tenantSegment(tenantId), 'evidence', 'evidence-files', params] as const,
    filesAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'evidence', 'evidence-files'] as const,
  },
  remediation: {
    plans: (tenantId: TenantId, params?: unknown) =>
      ['tenant', tenantSegment(tenantId), 'remediation', 'remediationPlans', params] as const,
    plansAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'remediation', 'remediationPlans'] as const,
    planDetail: (tenantId: TenantId, id?: string | null) =>
      ['tenant', tenantSegment(tenantId), 'remediation', 'remediationPlanDetail', id] as const,
    planHistory: (tenantId: TenantId, id?: string | null) =>
      ['tenant', tenantSegment(tenantId), 'remediation', 'remediationPlanHistory', id] as const,
    deficiencies: (tenantId: TenantId, params?: unknown) =>
      ['tenant', tenantSegment(tenantId), 'remediation', 'deficiencies', params] as const,
    deficienciesAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'remediation', 'deficiencies'] as const,
  },
  users: {
    list: (tenantId: TenantId, params?: unknown) =>
      ['tenant', tenantSegment(tenantId), 'users', 'users', params] as const,
    detail: (tenantId: TenantId, id?: string | null) =>
      ['tenant', tenantSegment(tenantId), 'users', 'users', id] as const,
    all: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'users', 'users'] as const,
    roles: (tenantId: TenantId, params?: unknown) =>
      ['tenant', tenantSegment(tenantId), 'users', 'userRoles', params] as const,
    rolesAll: (tenantId: TenantId) =>
      ['tenant', tenantSegment(tenantId), 'users', 'userRoles'] as const,
  },
} as const
