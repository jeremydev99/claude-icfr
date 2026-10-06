// 이사회 보고 패키지 템플릿 (2026-10-06) — 기본 문구는 데이터(평가 결과)와 기본 정보로 만들고, 사람이 고친 부분만 저장한다.
// 순수 함수(`reportTemplates.test.ts`). 샘플(회사 실제 양식)은 참고만 — 법정 기재사항을 빠짐없이 넣고, 수치는 데이터에서 가져온다.
import { selectConclusion, type ReportFacts } from './reportModel'

export type DocKey = 'meta' | 'ops_report' | 'ac_report' | 'board_ops' | 'ac_eval' | 'ac_minutes' | 'board_minutes'

export interface DocContent {
  /** 기본 정보 값 (meta 문서) */
  fields?: Record<string, string>
  /** 고친 문단 — 섹션 키 → 본문 */
  sections?: Record<string, string>
  /** 고친 표 — 표 키 → 행(셀 문자열 배열) */
  rows?: Record<string, string[][]>
}

export type Contents = Partial<Record<DocKey, DocContent>>

// ── 기본 정보 ────────────────────────────────────────────
export interface FieldDef { key: string; label: string; hint?: string; group: string; type?: 'text' | 'date' | 'select'; options?: { value: string; label: string }[] }

export const META_FIELDS: FieldDef[] = [
  { group: '회사', key: 'company', label: '회사명', hint: '예: 주식회사 OOO' },
  { group: '회사', key: 'term', label: '사업연도 기수', hint: '예: 제26기' },
  { group: '회사', key: 'size_note', label: '회사 구분', hint: '예: 자산총액 1천억원 미만 상장회사(내부회계 검토 대상)' },
  { group: '회사', key: 'framework', label: '적용 기준', type: 'select', options: [
    { value: 'sme', label: '중소기업 적용(개념체계·평가 기준 제4장)' },
    { value: 'general', label: '일반(개념체계·평가 및 보고 기준)' },
  ] },
  { group: '회사', key: 'auditor_firm', label: '외부감사인', hint: '예: OO회계법인' },
  { group: '서명', key: 'ceo', label: '대표이사' },
  { group: '서명', key: 'icfr_manager', label: '내부회계관리자' },
  { group: '서명', key: 'ac_chair', label: '감사위원회 위원장' },
  { group: '서명', key: 'report_date', label: '보고서 일자', type: 'date' },
  { group: '감사위원회 회의', key: 'ac_date', label: '일자', type: 'date' },
  { group: '감사위원회 회의', key: 'ac_time', label: '시작', hint: '예: 오전 10시 00분' },
  { group: '감사위원회 회의', key: 'ac_end_time', label: '종료', hint: '예: 오전 10시 30분' },
  { group: '감사위원회 회의', key: 'ac_place', label: '장소', hint: '예: 본점 8층 회의실' },
  { group: '감사위원회 회의', key: 'ac_seq', label: '회차', hint: '예: 2026년 1차' },
  { group: '이사회', key: 'board_date', label: '일자', type: 'date' },
  { group: '이사회', key: 'board_time', label: '시작', hint: '예: 오전 10시 30분' },
  { group: '이사회', key: 'board_end_time', label: '종료' },
  { group: '이사회', key: 'board_place', label: '장소' },
  { group: '이사회', key: 'board_seq', label: '회차', hint: '예: 2026년 2차' },
  { group: '정기주주총회', key: 'agm_date', label: '일자', type: 'date' },
  { group: '정기주주총회', key: 'agm_place', label: '장소' },
  { group: '회사 평가(운영실태)', key: 'ops_period', label: '평가 기간', hint: '예: 2025.01 ~ 2025.12 (연 1회)' },
  { group: '회사 평가(운영실태)', key: 'ops_performers', label: '평가 수행자', hint: '예: 내부회계 전담조직(경영지원실)' },
  { group: '회사 평가(운영실태)', key: 'ops_method', label: '평가 방법' },
  { group: '감사위원회 평가', key: 'ac_period', label: '평가 기간', hint: '예: 2026.01 ~ 2026.02' },
  { group: '감사위원회 평가', key: 'ac_performers', label: '평가 수행자', hint: '예: 감사위원회 지원조직(경영지원실, 2명)' },
  { group: '감사위원회 평가', key: 'ac_method', label: '평가 방법' },
]

export const META_ROWS: { key: string; label: string; cols: string[]; defaults: string[][] }[] = [
  { key: 'ac_members', label: '감사위원회 위원', cols: ['직책', '구분', '성명'],
    defaults: [['위원장', '사외이사', ''], ['위원', '사외이사', ''], ['위원', '사외이사', '']] },
  { key: 'directors', label: '이사', cols: ['직책', '구분', '성명'],
    defaults: [['의장', '대표이사', ''], ['이사', '사내이사', ''], ['이사', '사외이사', '']] },
]

export interface Ctx {
  fy: number
  facts: ReportFacts
  contents: Contents
  /** 기본 정보가 비었을 때 쓰는 값 — 역할 배정의 대표이사·내부회계관리자 지정자 */
  defaults?: Record<string, string>
}

const P = (v: string | undefined, ph: string) => (v && v.trim() ? v.trim() : `(${ph})`)
export function field(c: Ctx, key: string, ph?: string): string {
  const def = META_FIELDS.find((f) => f.key === key)
  return P(c.contents.meta?.fields?.[key] || c.defaults?.[key], ph ?? def?.label ?? key)
}
export function rawField(c: Ctx, key: string): string { return (c.contents.meta?.fields?.[key] || c.defaults?.[key])?.trim() ?? '' }

export function koDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  return m ? `${m[1]}년 ${m[2]}월 ${m[3]}일` : iso
}
const dateOr = (c: Ctx, key: string, ph: string) => (rawField(c, key) ? koDate(rawField(c, key)) : `(${ph})`)

export function metaRows(c: Ctx, key: string): string[][] {
  return c.contents.meta?.rows?.[key] ?? META_ROWS.find((r) => r.key === key)!.defaults
}

// ── 문서 정의 ────────────────────────────────────────────
export type Block =
  | { kind: 'title'; text: string }
  | { kind: 'addressee'; text: string }
  | { kind: 'heading'; text: string }
  | { kind: 'para'; key: string; label: string; text: (c: Ctx) => string; note?: string }
  | { kind: 'rows'; key: string; label: string; cols: string[]; defaults: (c: Ctx) => string[][] }
  | { kind: 'date'; text: (c: Ctx) => string }
  | { kind: 'signers'; lines: (c: Ctx) => string[] }
  | { kind: 'hint'; text: string }

export interface DocDef {
  key: Exclude<DocKey, 'meta'>
  title: string
  short: string
  /** 누가 → 누구에게 */
  audience: string
  statutory: boolean
  /** 회사마다 양식이 다르다는 안내를 붙일지 */
  companyForm?: boolean
  blocks: (c: Ctx) => Block[]
}

const fwText = (c: Ctx) => (rawField(c, 'framework') === 'general'
  ? { design: '내부회계관리제도운영위원회에서 발표한 ‘내부회계관리제도 설계 및 운영 개념체계’',
      eval: '「외부감사 및 회계 등에 관한 규정 시행세칙」 별표6 ‘내부회계관리제도 평가 및 보고 기준’' }
  : { design: '내부회계관리제도운영위원회에서 발표한 ‘내부회계관리제도 설계 및 운영 개념체계’의 제4장 중소기업에 대한 적용',
      eval: '「외부감사 및 회계 등에 관한 규정 시행세칙」 별표6 ‘내부회계관리제도 평가 및 보고 기준’(내부회계관리제도 평가 및 보고 모범규준 제4장 중소기업에 대한 적용)' })

const asOf = (c: Ctx) => `${c.fy}년 12월 31일 현재`
const mwOpen = (c: Ctx) => c.facts.byClass.material_weakness.open
const sdOpen = (c: Ctx) => c.facts.byClass.significant.open

function opsConclusion(c: Ctx): string {
  const k = selectConclusion(c.facts).kind
  if (k === 'ineffective') {
    return `본 대표이사 및 내부회계관리자의 내부회계관리제도 운영실태 평가결과, ${asOf(c)} 당사의 내부회계관리제도는 아래에 기술한 중요한 취약점 ${mwOpen(c)}건으로 인하여 ‘내부회계관리제도 설계 및 운영 개념체계’에 근거하여 볼 때, 중요성의 관점에서 효과적으로 설계되어 운영되고 있지 않다고 판단됩니다.`
  }
  return `본 대표이사 및 내부회계관리자의 내부회계관리제도 운영실태 평가결과, ${asOf(c)} 당사의 내부회계관리제도는 ‘내부회계관리제도 설계 및 운영 개념체계’에 근거하여 볼 때, 중요성의 관점에서 효과적으로 설계되어 운영되고 있다고 판단됩니다.`
}

function acOpinion(c: Ctx): string {
  const k = selectConclusion(c.facts).kind
  if (k === 'ineffective') {
    return `본 감사위원회의 의견으로는, ${asOf(c)} 당사의 내부회계관리제도는 중요한 취약점 ${mwOpen(c)}건으로 인하여 ‘내부회계관리제도 설계 및 운영 개념체계’에 근거하여 볼 때, 중요성의 관점에서 효과적으로 설계되어 운영되고 있지 않다고 판단됩니다.`
  }
  return `본 감사위원회의 의견으로는, ${asOf(c)} 당사의 내부회계관리제도는 ‘내부회계관리제도 설계 및 운영 개념체계’에 근거하여 볼 때, 중요성의 관점에서 효과적으로 설계되어 운영되고 있다고 판단됩니다.`
}

/** 표 값 — 고친 값이 있으면 그것, 없으면 기본 */
export function rowsOf(c: Ctx, doc: DocKey, key: string, defaults: string[][]): string[][] {
  return c.contents[doc]?.rows?.[key] ?? defaults
}

const improvementDefaults = (c: Ctx): string[][] => {
  const f = c.facts
  const out: string[][] = []
  if (f.byClass.material_weakness.total) out.push(['중요한 취약점', `${f.byClass.material_weakness.total}건(미종결 ${f.byClass.material_weakness.open})`, '개선계획에 따라 시정, 기말 재테스트'])
  if (f.byClass.significant.total) out.push(['유의한 미비점', `${f.byClass.significant.total}건(미종결 ${f.byClass.significant.open})`, '개선계획에 따라 시정'])
  if (f.byClass.simple.total) out.push(['단순한 미비점', `${f.byClass.simple.total}건(미종결 ${f.byClass.simple.open})`, '차기 평가 전 개선'])
  if (!out.length) out.push(['(개선 항목)', '(내용)', '(조치 계획·시기)'])
  return out
}

const recommendationDefaults = (c: Ctx): string[][] => (c.facts.deficienciesWithoutPlan > 0
  ? [['개선계획 수립', `개선계획이 없는 미비점 ${c.facts.deficienciesWithoutPlan}건에 대해 조치 계획과 완료 시기를 정할 것`]]
  : [['(권고 항목)', '(권고 내용)']])

const testSummary = (c: Ctx) => {
  const t = c.facts.tests
  return t.total ? `통제 테스트 ${t.total}건(완료 ${t.done}: 적정 ${t.pass} · 예외 ${t.fail}${t.na ? ` · 해당 없음 ${t.na}` : ''}${t.pending ? ` · 진행 중 ${t.pending}` : ''})` : '(테스트 결과)'
}

const scopeSummary = (c: Ctx) => {
  const f = c.facts
  const parts = []
  if (f.has.scoping) parts.push(`유의한 계정 ${f.significantAccounts}개`)
  if (f.has.rcm) parts.push(`프로세스 ${f.processTotal}개 · 통제 ${f.controlTotal}개${f.keyControls != null ? `(핵심통제 ${f.keyControls}개)` : ''}`)
  return parts.length ? parts.join(', ') : '(평가 범위)'
}

const deficiencySummary = (c: Ctx) => {
  const b = c.facts.byClass
  if (!c.facts.has.deficiencies) return '(미비점 현황)'
  return `중요한 취약점 ${b.material_weakness.total}건 · 유의한 미비점 ${b.significant.total}건 · 단순한 미비점 ${b.simple.total}건${b.unclassified.total ? ` · 미분류 ${b.unclassified.total}건` : ''}`
}

export const DOCS: DocDef[] = [
  {
    key: 'ops_report', short: '운영실태보고서', statutory: true,
    title: '내부회계관리제도 운영실태보고서',
    audience: '대표이사·내부회계관리자 → 주주총회·이사회·감사위원회 (외부감사법 제8조④)',
    blocks: (c) => [
      { kind: 'title', text: '내부회계관리제도 운영실태보고서' },
      { kind: 'addressee', text: `${field(c, 'company')} 주주, 이사회 및 감사위원회 귀중` },
      { kind: 'para', key: 'scope', label: '평가 대상', text: (x) => `본 대표이사 및 내부회계관리자는 ${x.fy}년 12월 31일 현재 동일자로 종료하는 회계연도에 대한 당사의 내부회계관리제도의 설계 및 운영실태를 평가하였습니다.` },
      { kind: 'para', key: 'responsibility', label: '책임', text: () => '내부회계관리제도의 설계 및 운영에 대한 책임은 본 대표이사 및 내부회계관리자를 포함한 회사의 경영진에 있습니다.' },
      { kind: 'para', key: 'objective', label: '평가 목적', text: () => '본 대표이사 및 내부회계관리자는 회사의 내부회계관리제도가 신뢰할 수 있는 재무제표의 작성 및 공시를 위하여 재무제표의 왜곡을 초래할 수 있는 오류나 부정행위를 예방하고 적발할 수 있도록 효과적으로 설계 및 운영되고 있는지의 여부에 대하여 평가하였습니다.' },
      { kind: 'para', key: 'criteria', label: '준거·평가 기준', text: (x) => `본 대표이사 및 내부회계관리자는 내부회계관리제도의 설계 및 운영을 위해 ${fwText(x).design}을 준거기준으로 사용하였습니다. 또한 내부회계관리제도의 설계 및 운영실태를 평가함에 있어 ${fwText(x).eval}을 평가기준으로 사용하였습니다.` },
      { kind: 'para', key: 'conclusion', label: '평가 결론', note: '평가 결과(미종결 중요한 취약점)에 따라 문구가 바뀝니다', text: opsConclusion },
      ...(mwOpen(c) > 0 ? [
        { kind: 'heading', text: '중요한 취약점 및 시정 계획' } as Block,
        { kind: 'para', key: 'mw_plan', label: '중요한 취약점·시정 계획', note: '법정 기재사항 — 취약점 내용과 시정 계획을 구체적으로', text: (x: Ctx) => `당사는 평가 결과 중요한 취약점 ${mwOpen(x)}건을 식별하였으며, 그 내용과 시정 계획은 다음과 같습니다.\n1) (취약점 내용) — (시정 계획 및 완료 예정 시기)` } as Block,
      ] : []),
      { kind: 'para', key: 'confirm1', label: '확인 1', text: () => '본 대표이사 및 내부회계관리자는 보고내용이 거짓으로 기재되거나 표시되지 아니하였고, 기재하거나 표시하여야 할 사항을 빠뜨리고 있지 아니함을 확인하였습니다.' },
      { kind: 'para', key: 'confirm2', label: '확인 2', text: () => '또한 본 대표이사 및 내부회계관리자는 보고내용에 중대한 오해를 일으키는 내용이 기재되거나 표시되지 아니하였다는 사실을 확인하였으며, 충분한 주의를 다하여 직접 확인·검토하였습니다.' },
      { kind: 'date', text: (x) => dateOr(x, 'report_date', '보고서 일자') },
      { kind: 'signers', lines: (x) => [`대 표 이 사  ${field(x, 'ceo')}  (인)`, `내부회계관리자  ${field(x, 'icfr_manager')}  (인)`] },
      { kind: 'hint', text: '별첨: 내부회계관리제도 평가 결과(데이터 근거) — Report › 별첨 탭' },
    ],
  },
  {
    key: 'ac_report', short: '감사위원회 평가보고서', statutory: true,
    title: '감사위원회의 내부회계관리제도 평가보고서',
    audience: '감사위원회 → 이사회 (외부감사법 제8조⑤, 본점 5년 비치)',
    blocks: (c) => {
      const recs = rowsOf(c, 'ac_eval', 'recommendations', recommendationDefaults(c)).filter((r) => r.some((x) => x && !x.startsWith('(')))
      return [
        { kind: 'title', text: '감사위원회의 내부회계관리제도 평가보고서' },
        { kind: 'addressee', text: `${field(c, 'company')} 주주, 이사회 귀중` },
        { kind: 'para', key: 'scope', label: '평가 대상', text: (x) => `본 감사위원회는 ${x.fy}년 12월 31일 현재 동일자로 종료하는 회계연도에 대한 당사의 내부회계관리제도의 설계 및 운영실태를 평가하였습니다.` },
        { kind: 'para', key: 'responsibility', label: '책임', text: () => '내부회계관리제도의 설계 및 운영에 대한 책임은 대표이사 및 내부회계관리자를 포함한 회사의 경영진에 있으며, 본 감사위원회는 관리감독 책임이 있습니다.' },
        { kind: 'para', key: 'basis', label: '평가 방법', text: () => '본 감사위원회는 대표이사 및 내부회계관리자가 본 감사위원회에게 제출한 내부회계관리제도 운영실태보고서를 참고로, 회사의 내부회계관리제도가 신뢰할 수 있는 재무제표의 작성 및 공시를 위하여 재무제표의 왜곡을 초래할 수 있는 오류나 부정행위를 예방하고 적발할 수 있도록 효과적으로 설계 및 운영되고 있는지의 여부에 대하여 평가하였으며, 내부회계관리제도가 신뢰성 있는 회계정보의 작성 및 공시에 실질적으로 기여하는지를 평가하였습니다.' },
        { kind: 'para', key: 'review', label: '운영실태보고서 점검', text: () => '또한 본 감사위원회는 내부회계관리제도 운영실태보고서에 거짓으로 기재되거나 표시된 사항이 있거나, 기재하거나 표시하여야 할 사항을 빠뜨리고 있는지를 점검하였으며, 내부회계관리제도 운영실태보고서의 시정 계획이 해당 회사의 내부회계관리제도 개선에 실질적으로 기여할 수 있는지를 검토하였습니다.' },
        { kind: 'para', key: 'criteria', label: '준거·평가 기준', text: (x) => `회사는 내부회계관리제도의 설계 및 운영을 위해 ${fwText(x).design}을 준거기준으로 사용하였습니다. 본 감사위원회는 내부회계관리제도의 설계 및 운영실태를 평가함에 있어 ${fwText(x).eval}을 평가기준으로 사용하였습니다.` },
        { kind: 'para', key: 'opinion', label: '평가 의견', note: '평가 결과에 따라 문구가 바뀝니다', text: acOpinion },
        ...(recs.length ? [{ kind: 'para', key: 'corrective', label: '시정 의견', note: '외부감사법 제8조⑤ — 시정 의견이 있으면 포함. 기본 문구는 감사위원회 평가결과의 개선 권고에서 만듭니다',
          text: () => `본 감사위원회는 내부회계관리제도의 관리·운영에 대하여 다음과 같이 시정 의견을 제시합니다.\n${recs.map((r, i) => `${i + 1}) ${r[0]}: ${r[1] ?? ''}`).join('\n')}` } as Block] : []),
        { kind: 'date', text: (x) => dateOr(x, 'report_date', '보고서 일자') },
        { kind: 'signers', lines: (x) => [`감사위원회 위원장  ${field(x, 'ac_chair')}  (인)`] },
      ]
    },
  },
  {
    key: 'board_ops', short: '보고: 운영실태 결과', statutory: false,
    title: '내부회계관리제도 운영실태 결과 보고',
    audience: '이사회 보고 안건 — 대표이사·내부회계관리자',
    blocks: (c) => [
      { kind: 'title', text: `${field(c, 'board_seq', '이사회 회차')} 이사회 — 보고 안건: 내부회계관리제도 운영실태 결과 보고` },
      { kind: 'heading', text: '1. 근거' },
      { kind: 'para', key: 'basis', label: '근거 규정', text: () => '「주식회사 등의 외부감사에 관한 법률」 제8조④ — 회사의 대표자는 사업연도마다 주주총회, 이사회 및 감사(감사위원회)에게 해당 회사의 내부회계관리제도의 운영실태를 보고하여야 합니다.' },
      { kind: 'heading', text: '2. 평가 개요' },
      { kind: 'rows', key: 'overview', label: '평가 개요', cols: ['구분', '내용'], defaults: (x) => [
        ['평가 대상 연도', `${x.fy}년(${field(x, 'term', '기수')})`],
        ['회사 구분', field(x, 'size_note')],
        ['평가 기간', field(x, 'ops_period')],
        ['평가 수행자', field(x, 'ops_performers')],
        ['평가 범위', scopeSummary(x)],
        ['평가 방법', rawField(x, 'ops_method') || '통제별 표본을 추출하여 설계대로 운영되었는지 문서 검증 또는 재수행'],
        ['평가 결과', testSummary(x)],
        ['미비점', deficiencySummary(x)],
      ] },
      { kind: 'heading', text: '3. 평가 결론' },
      { kind: 'para', key: 'conclusion', label: '결론 요약', note: '평가 결과에 따라 바뀝니다', text: (x) => {
        const k = selectConclusion(x.facts).kind
        if (k === 'insufficient') return '(평가 결과가 없어 결론을 만들 수 없습니다 — 테스트 결과를 먼저 입력하세요)'
        if (k === 'ineffective') return `중요한 취약점 ${mwOpen(x)}건으로 내부회계관리제도가 효과적이지 않다고 판단하며, 아래 시정 계획에 따라 개선합니다.`
        return sdOpen(x) > 0
          ? `중요한 취약점은 없으며 내부회계관리제도는 효과적으로 설계·운영되고 있습니다. 다만 유의한 미비점 ${sdOpen(x)}건은 아래 계획에 따라 개선합니다.`
          : '중요한 취약점 및 유의한 미비점은 없으며, 내부회계관리제도는 효과적으로 설계·운영되고 있습니다. 일부 개선 사항은 차기에 반영합니다.'
      } },
      { kind: 'heading', text: '4. 개선 항목 및 계획' },
      { kind: 'rows', key: 'improvements', label: '개선 항목', cols: ['항목', '내용', '조치 계획·시기'], defaults: improvementDefaults },
      { kind: 'heading', text: '5. 차기 연도 계획' },
      { kind: 'para', key: 'next_plan', label: '차기 계획', text: (x) => `${x.fy + 1}년 내부회계관리제도 연간 기본계획(스코핑 → RCM 갱신 → 설계·운영평가 → 미비점 개선 → 운영실태 보고)에 따라 진행합니다.` },
      { kind: 'hint', text: '첨부: 운영실태보고서(대표이사·내부회계관리자), 평가 결과 데이터(별첨)' },
    ],
  },
  {
    key: 'ac_eval', short: '보고: 감사위원회 평가결과', statutory: false,
    title: '감사위원회의 내부회계관리제도 평가결과 보고',
    audience: '감사위원회 보고 → 이사회 보고 안건',
    blocks: () => [
      { kind: 'title', text: '감사위원회의 내부회계관리제도 평가결과 보고' },
      { kind: 'heading', text: '1. 근거' },
      { kind: 'para', key: 'basis', label: '근거 규정', text: () => '「주식회사 등의 외부감사에 관한 법률」 제8조⑤ — 회사의 감사(감사위원회)는 내부회계관리제도의 운영실태를 평가하여 이사회에 사업연도마다 보고하고 그 평가보고서를 해당 회사의 본점에 5년간 비치하여야 하며, 관리·운영에 대하여 시정 의견이 있으면 그 의견을 포함하여 보고하여야 합니다.' },
      { kind: 'heading', text: '2. 평가 개요' },
      { kind: 'para', key: 'overview', label: '평가 개요', text: (x) => `본 감사위원회는 ${x.fy}년(${field(x, 'term', '기수')}) 회계연도 내부회계관리제도의 설계 및 운영실태를 회사가 보고한 운영실태보고서를 바탕으로, 통제환경·위험평가·통제활동·정보 및 의사소통·모니터링 활동의 5가지 구성요소가 체계적으로 작동하고 있는지 검토하였습니다.` },
      { kind: 'rows', key: 'detail', label: '평가 세부 내역', cols: ['구분', '내용'], defaults: (x) => [
        ['평가 기간', field(x, 'ac_period')],
        ['평가 수행자', field(x, 'ac_performers')],
        ['평가 방법', rawField(x, 'ac_method') || '핵심통제의 표본을 선별하여 증빙 검증 등 독립적 평가 수행, 회사 평가 결과 재검토'],
        ['검토 범위', scopeSummary(x)],
        ['회사 평가 결과', `${testSummary(x)} / ${deficiencySummary(x)}`],
      ] },
      { kind: 'heading', text: '3. 평가 결과 및 의견' },
      { kind: 'para', key: 'result', label: '결과', note: '평가 결과에 따라 바뀝니다', text: (x) => (mwOpen(x) > 0
        ? `회사의 내부회계관리제도에서 중요한 취약점 ${mwOpen(x)}건이 확인되었습니다. 회사가 제시한 시정 계획의 이행을 점검하겠습니다.`
        : sdOpen(x) > 0
          ? `중요한 취약점은 발견되지 않았으나 유의한 미비점 ${sdOpen(x)}건이 있어, 회사의 개선 이행을 점검하겠습니다.`
          : '회사의 내부회계관리제도를 무력화하거나 재무제표의 신뢰성을 심각하게 훼손할 만한 ‘중요한 취약점’이나 ‘유의한 미비점’은 발견되지 않았습니다.') },
      { kind: 'heading', text: '4. 개선 권고 사항' },
      { kind: 'rows', key: 'recommendations', label: '개선 권고', cols: ['항목', '권고 내용'], defaults: recommendationDefaults },
      { kind: 'heading', text: '5. 종합 결론' },
      { kind: 'para', key: 'conclusion', label: '종합 결론', text: (x) => (selectConclusion(x.facts).kind === 'ineffective'
        ? '회사의 내부회계관리제도는 중요한 취약점으로 인하여 효과적으로 설계 및 운영되고 있지 않다고 판단합니다. 시정 계획의 조속한 이행을 요구합니다.'
        : `회사의 내부회계관리제도는 관련 법규에 따라 적절하게 설계 및 운영되고 있는 것으로 판단됩니다. 상기 권고 사항을 반영하여 ${x.fy + 1}년에도 제도 운영의 내실을 기할 것을 당부합니다.`) },
      { kind: 'heading', text: '6. 감사위원회 활동 내역' },
      { kind: 'rows', key: 'decisions', label: '주요 결정 사항', cols: ['회차(일자)', '결정 사항'], defaults: () => [['(예: 2025년 1차(02.07))', '(예: 외부감사인 선정 기준 승인, 감사인 선임)']] },
      { kind: 'rows', key: 'activities', label: '활동 내역', cols: ['일자', '활동', '내용'], defaults: (x) => [
        ['', `${x.fy}년 내부회계관리제도 운영실태 보고 검토 및 평가`, '회사의 운영실태 보고 검토 및 감사위원회 별도 평가 수행'],
        ['', '대표이사 및 내부회계관리자 평가', '외부감사법 시행령 제9조에 따라 대표이사·내부회계관리자의 운영 결과 평가'],
        ['', '외부감사인과의 커뮤니케이션', `${field(x, 'auditor_firm')}와 중간·기말 감사 결과, 핵심감사사항 논의`],
        ['', '내부회계관리제도 평가보고서 작성', '평가 결과를 토대로 평가보고서 작성'],
      ] },
    ],
  },
  {
    key: 'ac_minutes', short: '감사위원회 의사록(안)', statutory: false, companyForm: true,
    title: '감사위원회 의사록',
    audience: '감사위원회 — 회사 양식에 맞게 수정',
    blocks: (c) => {
      const members = metaRows(c, 'ac_members')
      return [
        { kind: 'title', text: '감사위원회 의사록' },
        { kind: 'para', key: 'opening_line', label: '일시·장소', text: (x) => `${dateOr(x, 'ac_date', '일자')} ${field(x, 'ac_time', '시작 시각')} ${field(x, 'ac_place', '장소')}에서 다음과 같이 감사위원회를 개최하다.` },
        { kind: 'para', key: 'quorum', label: '출석', text: () => `감사위원회 위원의 총수 ${members.length}명    출석한 위원의 수 ${members.length}명` },
        { kind: 'para', key: 'open', label: '개회', text: (x) => `감사위원회 위원장(의장) ${field(x, 'ac_chair')}은(는) 정관 규정에 따라 의장석에 등단하여 위와 같이 법정수에 달하는 위원이 출석하였으므로 본 감사위원회가 적법하게 성립되었음을 알리고 개회를 선언한 후 다음 의안을 부의하고 심의를 구하다.` },
        { kind: 'para', key: 'report1', label: '보고 제1호', text: (x) => `제1호 보고 의안: 감사위원회의 내부회계관리제도 평가결과 보고\n의장 ${field(x, 'ac_chair')}은(는) 감사위원회의 내부회계관리제도 평가결과 보고의 건을 상정하고 이에 대하여 상세히 설명한 바, 출석 위원들은 그 내용을 검토한 후 전원 이의 없이 보고사항으로 접수하다.` },
        { kind: 'para', key: 'resolution1', label: '심의 제1호', text: (x) => `제1호 심의 의안: 내부회계관리제도 평가보고서 승인 및 이사회 보고 안건 상정의 건\n의장 ${field(x, 'ac_chair')}은(는) 다음 사항을 이사회에 보고하는 건에 대하여 상세히 설명하고 가부를 물은 바, 출석 위원 전원 이의 없이 찬성하여 승인 가결하다.\n1) 감사위원회의 내부회계관리제도 평가결과\n2) 감사위원회의 내부회계관리제도 평가 세부 내역\n3) 감사위원회의 내부회계관리제도 평가보고서\n4) 감사위원회 활동 내역` },
        { kind: 'para', key: 'close', label: '폐회', text: (x) => `의장은 이상으로서 의안 전부의 심의를 종료하였으므로 폐회를 선언하다. (회의 종료 시각 ${field(x, 'ac_end_time', '종료 시각')})\n위 의사의 경과 요령과 결과를 명백히 하기 위하여 이 의사록을 작성하고 의장과 출석한 위원이 기명날인 또는 서명하다.` },
        { kind: 'date', text: (x) => dateOr(x, 'ac_date', '일자') },
        { kind: 'signers', lines: (x) => [field(x, 'company'), ...members.map((m) => `감사위원회${m[0] === '위원장' ? '위원장' : '위원'}  ${m[1] ?? ''}  ${m[2] || '(성명)'}  (인)`)] },
      ]
    },
  },
  {
    key: 'board_minutes', short: '이사회 의사록(안)', statutory: false, companyForm: true,
    title: '이사회 의사록',
    audience: '이사회 — 회사 양식에 맞게 수정',
    blocks: (c) => {
      const dirs = metaRows(c, 'directors')
      const chairName = dirs.find((d) => d[0] === '의장')?.[2] || rawField(c, 'ceo') || '(의장)'
      const others = rowsOf(c, 'board_minutes', 'other_agenda', [])
      return [
        { kind: 'title', text: '이사회 의사록' },
        { kind: 'para', key: 'opening_line', label: '일시·장소', text: (x) => `${dateOr(x, 'board_date', '일자')} ${field(x, 'board_time', '시작 시각')} ${field(x, 'board_place', '장소')}에서 다음과 같이 이사회를 개최하다.` },
        { kind: 'para', key: 'quorum', label: '출석', text: () => `이사의 총수 ${dirs.length}명    출석한 이사의 수 ${dirs.length}명` },
        { kind: 'para', key: 'open', label: '개회', text: () => `대표이사 ${chairName}은(는) 정관 규정에 따라 의장석에 등단하여 위와 같이 법정수에 달하는 이사가 출석하였으므로 본 이사회가 적법하게 성립되었음을 알리고 개회를 선언한 후 다음 의안을 부의하고 심의를 구하다.` },
        { kind: 'heading', text: '보고 의안' },
        { kind: 'para', key: 'report1', label: '보고 제1호', text: () => `제1호 보고 의안: 내부회계관리제도 운영실태 보고의 건\n의장 ${chairName}은(는) ‘내부회계관리제도 운영실태 보고의 건’을 상정하고, 대표이사 및 내부회계관리자가 작성한 운영실태보고서의 내용을 상세히 설명한 바, 출석 이사들은 그 내용을 검토한 후 전원 이의 없이 보고사항으로 접수하다.` },
        { kind: 'para', key: 'report2', label: '보고 제2호', text: (x) => `제2호 보고 의안: 감사위원회의 내부회계관리제도 평가결과 보고의 건\n감사위원회 위원장 ${field(x, 'ac_chair')}은(는) ‘감사위원회의 내부회계관리제도 평가결과 보고의 건’에 대하여 평가보고서와 시정 의견을 포함하여 상세히 설명한 바, 출석 이사들은 그 내용을 검토한 후 전원 이의 없이 보고사항으로 접수하다.` },
        { kind: 'rows', key: 'other_agenda', label: '그 밖의 심의 의안', cols: ['의안', '내용·결과'], defaults: () => [] },
        ...(others.length ? [] : [{ kind: 'hint', text: '그 밖의 심의 의안(재무제표 승인, 주주총회 소집 등)이 있으면 위 표에 추가하세요.' } as Block]),
        { kind: 'para', key: 'close', label: '폐회', text: (x) => `의장은 이상으로서 의안 전부의 심의를 종료하였으므로 폐회를 선언하다. (회의 종료 시각 ${field(x, 'board_end_time', '종료 시각')})\n위 의사의 경과 요령과 결과를 명백히 하기 위하여 이 의사록을 작성하고 의장과 출석한 이사가 기명날인 또는 서명하다.` },
        { kind: 'date', text: (x) => dateOr(x, 'board_date', '일자') },
        { kind: 'signers', lines: (x) => [field(x, 'company'), ...dirs.map((d) => `${d[0] === '의장' ? '의장' : ''} ${d[1] ?? ''}  ${d[2] || '(성명)'}  (인)`.trim())] },
      ]
    },
  },
]

/** 섹션 본문 — 고친 값이 있으면 그것 */
export function sectionText(c: Ctx, doc: DocKey, key: string, def: (c: Ctx) => string): { text: string; edited: boolean } {
  const v = c.contents[doc]?.sections?.[key]
  return v != null ? { text: v, edited: true } : { text: def(c), edited: false }
}

/** 채워지지 않은 자리표시 `(…)` 개수 — 확정 전 점검 */
// 괄호지만 빈칸이 아닌 것 — 조사 `은(는)`, 직함 보충 `위원장(의장)`, 서명 `(인)` 등
const NOT_BLANK = /^(인|안|별첨|개별|감사 후|주|는|은|이|가|을|를|과|와|의장|대면|서면)$/
export function placeholders(text: string): string[] {
  return [...text.matchAll(/\(([^()\n]{1,20})\)/g)].map((m) => m[1]).filter((s) => !NOT_BLANK.test(s) && !/^\d/.test(s))
}

/** 보고 순서 — 감사위원회 → 이사회 → 정기주주총회 */
export function timeline(c: Ctx) {
  return [
    { step: '감사위원회', date: rawField(c, 'ac_date'), items: ['운영실태보고서 수령·검토', '감사위원회 평가결과 보고', '평가보고서 승인·이사회 상정 의결'] },
    { step: '이사회', date: rawField(c, 'board_date'), items: ['보고 1: 운영실태 결과(대표이사)', '보고 2: 감사위원회 평가결과(감사위원장)'] },
    { step: '정기주주총회', date: rawField(c, 'agm_date'), items: ['보고사항: 내부회계관리제도 운영실태 보고'] },
  ]
}
