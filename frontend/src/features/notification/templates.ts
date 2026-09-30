// 메일발송 초안 — 표준 ICFR 알림 템플릿·발송 규칙(샘플). 발송 백엔드 미연결.
// 치환자는 {{이름}} 형식. 값이 없으면 치환자를 그대로 남겨 누락이 눈에 띄게 한다.

export interface NotificationTemplate {
  id: string
  name: string
  category: '테스트' | '증빙' | '미비점' | '스코핑' | '재무제표'
  subject: string
  body: string
}

export interface NotificationRule {
  trigger: string
  templateId: string
  recipients: string
  timing: string
}

export const SAMPLE_VALUES: Record<string, string> = {
  담당자: '홍길동',
  통제코드: 'FC-REV-01',
  통제명: '매출 인식 검토',
  기한: '2026-10-15',
  회계연도: '2026',
  미비점코드: 'DEF-2026-003',
  심각도: '중요한 취약점',
  재무제표: '2026 연결 재무상태표',
  링크: 'https://icfr.example.com',
  발신자: '내부회계관리팀',
}

export const TEMPLATES: NotificationTemplate[] = [
  {
    id: 'test-request',
    name: '테스트 수행 요청',
    category: '테스트',
    subject: '[내부회계] {{회계연도}} 운영효과성 테스트 수행 요청 — {{통제코드}}',
    body: '{{담당자}}님, 안녕하십니까.\n\n{{회계연도}} 회계연도 내부회계관리제도 운영효과성 평가를 위해 아래 통제의 테스트 수행을 요청드립니다.\n\n- 통제: {{통제코드}} {{통제명}}\n- 완료 기한: {{기한}}\n\n시스템에서 테스트 절차·표본을 확인하시고 결과와 증빙을 등록해 주십시오.\n{{링크}}\n\n{{발신자}} 드림',
  },
  {
    id: 'test-due',
    name: '테스트 기한 임박',
    category: '테스트',
    subject: '[내부회계] 테스트 기한 임박 안내 — {{통제코드}} ({{기한}})',
    body: '{{담당자}}님,\n\n{{통제코드}} {{통제명}} 테스트의 완료 기한({{기한}})이 다가오고 있습니다. 아직 완료되지 않았으니 기한 내 결과 등록을 부탁드립니다.\n{{링크}}\n\n{{발신자}} 드림',
  },
  {
    id: 'evidence-request',
    name: '증빙 제출 요청',
    category: '증빙',
    subject: '[내부회계] 통제 증빙 제출 요청 — {{통제코드}}',
    body: '{{담당자}}님,\n\n{{통제코드}} {{통제명}}의 통제 수행 증빙(결재 문서·검토 기록·시스템 화면 등) 제출을 요청드립니다.\n\n- 제출 기한: {{기한}}\n\n시스템 증빙 메뉴에 업로드 후 해당 통제에 연결해 주십시오.\n{{링크}}\n\n{{발신자}} 드림',
  },
  {
    id: 'deficiency-registered',
    name: '미비점 등록 알림',
    category: '미비점',
    subject: '[내부회계] 통제 미비점 등록 — {{미비점코드}} ({{심각도}})',
    body: '{{담당자}}님,\n\n{{통제코드}} {{통제명}} 테스트 결과 미비점이 등록되었습니다.\n\n- 미비점: {{미비점코드}}\n- 심각도: {{심각도}}\n\n{{기한}}까지 개선계획을 수립해 등록해 주십시오.\n{{링크}}\n\n{{발신자}} 드림',
  },
  {
    id: 'plan-approval',
    name: '개선계획 승인 요청',
    category: '미비점',
    subject: '[내부회계] 개선계획 승인 요청 — {{미비점코드}}',
    body: '{{담당자}}님,\n\n미비점 {{미비점코드}}({{통제코드}})에 대한 개선계획이 제출되어 승인을 요청드립니다.\n\n- 검토 기한: {{기한}}\n{{링크}}\n\n{{발신자}} 드림',
  },
  {
    id: 'retest-request',
    name: '재테스트 요청',
    category: '테스트',
    subject: '[내부회계] 개선 후 재테스트 요청 — {{통제코드}}',
    body: '{{담당자}}님,\n\n미비점 {{미비점코드}}의 개선 조치가 완료되어 {{통제코드}} {{통제명}}의 재테스트를 요청드립니다.\n\n- 재테스트 기한: {{기한}}\n\n개선 이후 기간에서 충분한 표본을 추출해 주십시오.\n{{링크}}\n\n{{발신자}} 드림',
  },
  {
    id: 'scoping-review',
    name: '스코핑 검토 요청',
    category: '스코핑',
    subject: '[내부회계] {{회계연도}} 스코핑 결과 검토 요청',
    body: '{{담당자}}님,\n\n{{회계연도}} 회계연도 중요성 기준·유의한 계정·프로세스 스코핑 결과가 작성되어 검토를 요청드립니다.\n\n- 검토 기한: {{기한}}\n{{링크}}\n\n{{발신자}} 드림',
  },
  {
    id: 'fs-finalized',
    name: '재무제표 확정 알림',
    category: '재무제표',
    subject: '[내부회계] 재무제표 확정 — {{재무제표}}',
    body: '{{담당자}}님,\n\n{{재무제표}}가 확정되었습니다. 스코핑의 양적 판정이 확정 금액 기준으로 갱신되었는지 확인해 주십시오.\n{{링크}}\n\n{{발신자}} 드림',
  },
]

export const RULES: NotificationRule[] = [
  { trigger: '테스트 회차 생성(계획)', templateId: 'test-request', recipients: '통제 테스트 담당자', timing: '즉시' },
  { trigger: '테스트 미완료 + 기한 도래', templateId: 'test-due', recipients: '테스트 담당자 (참조: 내부회계팀)', timing: '기한 D-7, D-1 09:00' },
  { trigger: '테스트 진행중 + 증빙 미연결', templateId: 'evidence-request', recipients: '통제 수행자(통제 책임자)', timing: '매주 월 09:00' },
  { trigger: '미비점 등록', templateId: 'deficiency-registered', recipients: '통제 책임자·프로세스 오너', timing: '즉시' },
  { trigger: '개선계획 완료 제출', templateId: 'plan-approval', recipients: '내부회계관리자(승인권자)', timing: '즉시' },
  { trigger: '개선계획 승인', templateId: 'retest-request', recipients: '테스트 담당자', timing: '즉시' },
  { trigger: '스코핑 검토 요청 상태 전환', templateId: 'scoping-review', recipients: '내부회계관리자·감사(위원회) 담당', timing: '즉시' },
  { trigger: '재무제표 확정', templateId: 'fs-finalized', recipients: '스코핑 담당자', timing: '즉시' },
]

const PLACEHOLDER = /\{\{\s*([^{}\s]+)\s*\}\}/g

/** {{키}} 를 values 로 치환. 없는 키는 원문 유지. */
export function renderTemplate(text: string, values: Record<string, string>): string {
  return text.replace(PLACEHOLDER, (whole, key: string) =>
    Object.prototype.hasOwnProperty.call(values, key) ? values[key] : whole,
  )
}

/** 템플릿이 쓰는 치환자 키 목록(중복 제거, 등장 순). */
export function placeholdersOf(text: string): string[] {
  const out: string[] = []
  for (const m of text.matchAll(PLACEHOLDER)) if (!out.includes(m[1])) out.push(m[1])
  return out
}
