/**
 * 테넌트 정책 키 정의 — 백엔드 상수와 1:1 (backend/app/models/role_assignment.py, euc.py, scoping.py).
 *
 * 정책은 전부 문자열로 저장된다. 해석 규칙(미설정 시 기본값, 불리언 판정)은 **소비하는 서버 쪽 규칙을
 * 그대로 옮긴다** — 화면이 서버와 다르게 읽으면 "화면엔 꺼짐, 실제론 켜짐"이 된다.
 */

export const POLICY_FISCAL_YEAR_START_MONTH = 'fiscal_year_start_month'
export const DEFAULT_FISCAL_YEAR_START_MONTH = 1

export interface TenantPolicy {
  id?: string
  policy_key: string
  policy_value: string
}

type BoolDef = {
  key: string
  kind: 'bool'
  label: string
  description: string
  /** 미설정일 때 서버가 쓰는 값 */
  defaultValue: boolean
  /** 서버 판정 방식 — 'truthy': true/1/yes 만 참, 'not-falsy': false/0/no 만 거짓 */
  parse: 'truthy' | 'not-falsy'
}
type SelectDef = {
  key: string
  kind: 'select'
  label: string
  description: string
  defaultValue: string
  options: { value: string; label: string }[]
}
type NumberDef = {
  key: string
  kind: 'number'
  label: string
  description: string
  defaultValue: string
  unit?: string
  min?: number
  max?: number
  step?: number
  /** 저장값 ↔ 화면값 변환 (예: 바이트 ↔ MB) */
  toDisplay?: (raw: string) => string
  fromDisplay?: (display: string) => string
  validate?: (display: string) => string | null
}
export type PolicyDef = BoolDef | SelectDef | NumberDef

export const MB = 1024 * 1024

export function bytesToMb(raw: string): string {
  const n = Number(raw)
  if (!Number.isFinite(n)) return raw
  return String(Math.round((n / MB) * 100) / 100)
}

export function mbToBytes(display: string): string {
  const n = Number(display)
  if (!Number.isFinite(n)) return display
  return String(Math.round(n * MB))
}

export function parseBool(raw: string | undefined, def: BoolDef): boolean {
  if (raw === undefined) return def.defaultValue
  const v = raw.toLowerCase()
  if (def.parse === 'truthy') return ['true', '1', 'yes'].includes(v)
  return !['false', '0', 'no'].includes(v)
}

export const POLICY_GROUPS: { title: string; defs: PolicyDef[] }[] = [
  {
    title: '평가 워크플로',
    defs: [
      {
        key: 'dept_approval_enabled',
        kind: 'bool',
        label: '부서승인 단계 사용',
        description:
          '끄면 모든 통제에서 부서승인 단계를 건너뜁니다. 켜져 있어도 통제책임자가 부서장 본인이면 자동 스킵됩니다. (기본: 사용)',
        defaultValue: true,
        parse: 'not-falsy',
      },
    ],
  },
  {
    title: '이해상충(겸직) 조합',
    defs: [
      {
        key: 'conflict_assessor_control_owner_blocked',
        kind: 'bool',
        label: '통제책임자 = 평가자 겸직 금지',
        description:
          '켜면 같은 통제에서 한 사람이 통제책임자와 평가자를 겸하는 배정을 거부합니다. 끄면 경고 후 사유를 남기고 저장합니다. (기본: 허용)',
        defaultValue: false,
        parse: 'truthy',
      },
      {
        key: 'conflict_assessor_icfr_manager_blocked',
        kind: 'bool',
        label: '평가자 = 내부회계관리자 겸직 금지',
        description:
          '켜면 내부회계관리자(테넌트 역할)를 통제 평가자로 배정하는 것을 거부합니다. 끄면 경고 후 사유를 남기고 저장합니다. (기본: 허용)',
        defaultValue: false,
        parse: 'truthy',
      },
    ],
  },
  {
    title: '증빙',
    defs: [
      {
        key: 'evidence_edit_enabled',
        kind: 'bool',
        label: '진행 중 회차 증빙 편집 허용',
        description: '진행 중인 평가 회차에서 통제책임자가 증빙을 수정·삭제할 수 있는지 여부입니다. (기본: 허용)',
        defaultValue: true,
        parse: 'not-falsy',
      },
      {
        key: 'evidence_retention_years',
        kind: 'number',
        label: '증빙 보존기간',
        description:
          '최소 5년(내부회계관리제도 업무지침). 0 은 영구 보존이며 기본값입니다. 현재는 설정값만 저장되고 만료 삭제는 하지 않습니다.',
        defaultValue: '0',
        unit: '년',
        min: 0,
        step: 1,
        validate: (d) => {
          const n = Number(d)
          if (!Number.isInteger(n)) return '정수를 입력하세요'
          if (n !== 0 && n < 5) return '최소 5년입니다 (0 = 영구 보존)'
          return null
        },
      },
      {
        key: 'evidence_max_bytes',
        kind: 'number',
        label: '증빙 업로드 크기 상한',
        description: '파일 1건당 최대 크기입니다. 미설정이면 서버 기본값(50MB)을 씁니다.',
        defaultValue: String(50 * MB),
        unit: 'MB',
        min: 1,
        step: 1,
        toDisplay: bytesToMb,
        fromDisplay: mbToBytes,
        validate: (d) => (Number(d) > 0 ? null : '0보다 큰 값을 입력하세요'),
      },
    ],
  },
  {
    title: 'EUC · 스코핑 기본값',
    defs: [
      {
        key: 'euc_identification_threshold',
        kind: 'select',
        label: 'EUC 통제 식별 임계값',
        description: '위험평가가 이 등급 이상이면 EUC 를 통제 대상으로 식별합니다. (기본: Moderate)',
        defaultValue: 'moderate',
        options: [
          { value: 'low', label: 'Low' },
          { value: 'moderate', label: 'Moderate' },
          { value: 'high', label: 'High' },
        ],
      },
      {
        key: 'scoping_qual_threshold',
        kind: 'number',
        label: '스코핑 질적 판정 기준값',
        description:
          'H/M/L = 3/2/1 평균과 비교하는 기준값(1~3). 새 회계연도 스코핑을 만들 때의 기본값으로만 쓰입니다. (기본: 2)',
        defaultValue: '2',
        min: 1,
        max: 3,
        step: 0.1,
        validate: (d) => {
          const n = Number(d)
          return Number.isFinite(n) && n >= 1 && n <= 3 ? null : '1 이상 3 이하여야 합니다'
        },
      },
      {
        key: 'scoping_qual_comparison',
        kind: 'select',
        label: '스코핑 질적 판정 비교 방식',
        description: '기준값과 비교하는 방식입니다. 새 회계연도 스코핑의 기본값으로만 쓰입니다. (기본: 이상)',
        defaultValue: 'ge',
        options: [
          { value: 'ge', label: '이상 (≥)' },
          { value: 'gt', label: '초과 (>)' },
        ],
      },
    ],
  },
]

export const KNOWN_POLICY_KEYS = new Set<string>([
  POLICY_FISCAL_YEAR_START_MONTH,
  ...POLICY_GROUPS.flatMap((g) => g.defs.map((d) => d.key)),
])

export function policyMap(items: TenantPolicy[] | undefined): Record<string, string> {
  const m: Record<string, string> = {}
  for (const p of items ?? []) m[p.policy_key] = p.policy_value
  return m
}

export function unknownPolicies(items: TenantPolicy[] | undefined): TenantPolicy[] {
  return (items ?? []).filter((p) => !KNOWN_POLICY_KEYS.has(p.policy_key))
}

/** 서버 `fiscal_year_start_month()` 와 같은 규칙 — 미설정·비정상이면 1. */
export function parseStartMonth(raw: string | undefined): number {
  const n = Number(raw)
  return Number.isInteger(n) && n >= 1 && n <= 12 ? n : DEFAULT_FISCAL_YEAR_START_MONTH
}

/** 시작월 → 회계연도 범위 설명 (예: 4 → "4월 1일 ~ 다음 해 3월 31일", 3월 결산) */
export function describeFiscalYear(startMonth: number): string {
  if (startMonth === 1) return '1월 1일 ~ 12월 31일 (12월 결산)'
  const endMonth = startMonth - 1
  return `${startMonth}월 1일 ~ 다음 해 ${endMonth}월 말일 (${endMonth}월 결산)`
}

// ── 역할 배정 ──────────────────────────────────────────

export const ASSIGNMENT_ROLES = [
  { value: 'control_owner', label: '통제책임자' },
  { value: 'dept_approver', label: '부서승인자' },
  { value: 'assessor', label: '평가자' },
] as const

export const ASSIGNMENT_SCOPES = [
  { value: 'process', label: '프로세스(기본값)' },
  { value: 'control', label: '통제(개별 지정)' },
] as const

export function roleLabel(role: string): string {
  return ASSIGNMENT_ROLES.find((r) => r.value === role)?.label ?? role
}

export function scopeLabel(scope: string): string {
  return ASSIGNMENT_SCOPES.find((s) => s.value === scope)?.label ?? scope
}

/** 409 중 "사유를 입력해야" 는 사유 입력으로 풀 수 있는 경고, "정책상 금지" 는 풀 수 없는 거부다. */
export function isConflictReasonRequired(detail: string | undefined): boolean {
  return !!detail && detail.includes('사유를 입력해야')
}
