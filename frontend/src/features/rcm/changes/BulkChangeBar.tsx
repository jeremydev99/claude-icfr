import { useState } from 'react'
import { toast } from 'sonner'
import { Save, Send, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { errText, useChangeAction } from './api'

type FieldDef =
  | { key: string; label: string; kind: 'text'; placeholder?: string }
  | { key: string; label: string; kind: 'select'; options: { value: string; label: string }[] }
  | { key: string; label: string; kind: 'bool' }

/** 일괄로 바꿀 수 있는 항목 — 통제 내용 필드(ControlUpdate). 프로세스(소속)는 위험 계층 이동이라 여기 없다 */
const FIELDS: FieldDef[] = [
  { key: 'owner_name', label: '담당자명', kind: 'text', placeholder: '예: 김세영' },
  { key: 'is_key_control', label: '핵심통제', kind: 'bool' },
  // 값은 서버 허용값(models/rcm_baseline: FREQUENCY_VALUES·AUTO_MANUAL_VALUES)과 같아야 한다
  { key: 'frequency', label: '수행 주기', kind: 'select', options: [
    { value: 'D', label: '일' }, { value: 'W', label: '주' }, { value: 'M', label: '월' }, { value: 'Q', label: '분기' },
    { value: 'A', label: '연' }, { value: 'O', label: '수시' }] },
  { key: 'auto_manual', label: '자동/수동', kind: 'select', options: [{ value: 'A', label: '자동' }, { value: 'M', label: '수동' }, { value: 'IT', label: 'IT 의존 수동' }] },
  { key: 'preventive_detective', label: '예방/적발', kind: 'select', options: [{ value: 'P', label: '예방' }, { value: 'D', label: '적발' }] },
  { key: 'related_systems', label: '관련 시스템', kind: 'text', placeholder: '예: ERP(SAP)' },
]

/**
 * 선택한 통제 일괄 변경(2026-10-06) — 같은 값을 여러 통제에 임시저장하거나 바로 상신한다.
 * 통제마다 따로 결재된다(각자의 조직장 → 내부회계 대기함 → 내부회계관리자). 내 기존 임시저장에 더해진다.
 */
export default function BulkChangeBar({ ids, onClear, onDone }: { ids: string[]; onClear: () => void; onDone: () => void }) {
  const [field, setField] = useState(FIELDS[0].key)
  const [value, setValue] = useState<string>('')
  const [note, setNote] = useState('')
  const act = useChangeAction()
  const def = FIELDS.find((f) => f.key === field)!
  const ready = def.kind === 'bool' ? value === 'true' || value === 'false' : def.kind === 'text' ? true : value !== ''
  const run = (submit: boolean) => {
    const v = def.kind === 'bool' ? value === 'true' : def.kind === 'text' ? (value.trim() || null) : value
    act.mutate({ method: 'post', url: '/api/rcm-changes/bulk', body: { control_ids: ids, changes: { [field]: v }, note: note || null, submit } }, {
      onSuccess: (r) => {
        const x = r as { ok: unknown[]; failed: { control_code: string | null; reason: string }[] }
        if (x.failed.length) toast.warning(`${x.ok.length}건 ${submit ? '상신' : '임시저장'}, ${x.failed.length}건 제외 — ${x.failed.slice(0, 3).map((f) => `${f.control_code}: ${f.reason}`).join(' / ')}`, { duration: 9000 })
        else toast.success(`${x.ok.length}건을 ${submit ? '상신했습니다 — 통제마다 조직장 결재로' : '임시저장했습니다'}`)
        if (x.ok.length) onDone()
      },
      onError: (e) => toast.error(errText(e, '처리하지 못했습니다')),
    })
  }
  return (
    <div className="sticky top-14 z-20 flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-accent px-4 py-3 text-sm shadow-card">
      <span>선택한 통제 <b>{ids.length}</b>개의</span>
      <select value={field} onChange={(e) => { setField(e.target.value); setValue('') }} className="h-9 rounded-md border bg-background px-2 py-0">
        {FIELDS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
      </select>
      <span>을(를)</span>
      {def.kind === 'text' && <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder={def.placeholder} className="h-9 w-44 bg-background" />}
      {def.kind === 'select' && (
        <select value={value} onChange={(e) => setValue(e.target.value)} className="h-9 rounded-md border bg-background px-2 py-0">
          <option value="">선택</option>
          {def.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )}
      {def.kind === 'bool' && (
        <select value={value} onChange={(e) => setValue(e.target.value)} className="h-9 rounded-md border bg-background px-2 py-0">
          <option value="">선택</option><option value="true">핵심통제로</option><option value="false">핵심통제 아님으로</option>
        </select>
      )}
      <span>로</span>
      <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="변경 사유(선택)" className="h-9 w-48 bg-background" />
      <span className="ml-auto flex gap-2">
        <Button size="sm" variant="outline" disabled={!ready || act.isPending} onClick={() => run(false)}><Save className="mr-1.5 h-4 w-4" />임시저장</Button>
        <Button size="sm" disabled={!ready || act.isPending} onClick={() => run(true)}><Send className="mr-1.5 h-4 w-4" />일괄 상신</Button>
        <Button size="sm" variant="ghost" onClick={onClear}><X className="mr-1 h-4 w-4" />선택 해제</Button>
      </span>
      <p className="w-full text-xs text-muted-foreground">
        통제마다 따로 결재됩니다 — 각 통제의 조직장 → 내부회계 대기함 → 내부회계관리자. 프로세스(소속) 이동은 위험 계층을 옮기는 일이라 여기서 하지 않습니다.
      </p>
    </div>
  )
}
