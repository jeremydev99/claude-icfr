/** AI 제안(ADR-0042) — 서버 `api/ai_proposals.out` 과 같은 모양 */
export interface AiAdjustment { title: string; which: string; from: string; to: string; reason: string | null }
export interface AiChange { title: string; change: string; from?: string[]; to?: string[] }

export interface AiProposal {
  id: string
  kind: string
  kind_label: string
  target_id: string | null
  fiscal_year: number | null
  status: 'proposed' | 'adopted' | 'discarded' | 'superseded'
  status_label: string
  engine: string
  trigger: string
  summary: string
  basis: { source?: string; adjusted?: AiAdjustment[] } & Record<string, unknown>
  created_at: string
  adopted_by: string | null
  adopted_at: string | null
  adopted_changes: AiChange[] | null
  decision_note: string | null
}
