import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { parseBool, type PolicyDef } from '../PolicyDefs.pure'
import { errorDetail, useUpsertPolicy } from '../api/PolicyAssignmentApi'

interface Props {
  def: PolicyDef
  raw: string | undefined
  canEdit: boolean
}

/** 정책 1건. 불리언은 바꾸는 즉시 저장, 나머지는 [저장] 버튼. */
export default function PolicyField({ def, raw, canEdit }: Props) {
  const upsert = useUpsertPolicy()
  const isSet = raw !== undefined

  const toDisplay = (v: string) => (def.kind === 'number' && def.toDisplay ? def.toDisplay(v) : v)
  const initial = def.kind === 'bool' ? '' : toDisplay(raw ?? def.defaultValue)
  const [draft, setDraft] = useState(initial)
  useEffect(() => setDraft(initial), [initial])

  const save = async (value: string) => {
    try {
      await upsert.mutateAsync({ policy_key: def.key, policy_value: value })
      toast.success(`${def.label} 저장됨`)
    } catch (e) {
      toast.error(errorDetail(e, '저장하지 못했습니다'))
    }
  }

  const validationError = def.kind === 'number' && def.validate ? def.validate(draft) : null
  const dirty = def.kind !== 'bool' && draft !== initial

  return (
    <div className="flex flex-col gap-2 border-b py-3 last:border-b-0 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          {/* 내부 키(dept_approval_enabled 등)는 사용자에게 의미가 없어 화면에서 뺐다 — 지원·문의용으로 마우스를 올리면 보인다 */}
          <Label htmlFor={`policy-${def.key}`} className="font-medium" title={`정책 키: ${def.key}`}>
            {def.label}
          </Label>
          {!isSet && <Badge variant="secondary">기본값</Badge>}
        </div>
        <p className="text-sm text-muted-foreground">{def.description}</p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {def.kind === 'bool' && (
          <>
            <Checkbox
              id={`policy-${def.key}`}
              checked={parseBool(raw, def)}
              disabled={!canEdit || upsert.isPending}
              onCheckedChange={(c) => save(c === true ? 'true' : 'false')}
            />
            <span className="w-10 text-sm">{parseBool(raw, def) ? '켜짐' : '꺼짐'}</span>
          </>
        )}

        {def.kind === 'select' && (
          <Select value={draft} onValueChange={setDraft} disabled={!canEdit}>
            <SelectTrigger id={`policy-${def.key}`} className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {def.options.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {def.kind === 'number' && (
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <Input
                id={`policy-${def.key}`}
                type="number"
                className="w-28"
                value={draft}
                min={def.min}
                max={def.max}
                step={def.step}
                disabled={!canEdit}
                onChange={(e) => setDraft(e.target.value)}
              />
              {def.unit && <span className="text-sm text-muted-foreground">{def.unit}</span>}
            </div>
            {validationError && dirty && <p className="text-xs text-destructive">{validationError}</p>}
          </div>
        )}

        {def.kind !== 'bool' && canEdit && (
          <Button
            size="sm"
            disabled={!dirty || !!validationError || upsert.isPending}
            onClick={() => save(def.kind === 'number' && def.fromDisplay ? def.fromDisplay(draft) : draft)}
          >
            {upsert.isPending && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
            저장
          </Button>
        )}
      </div>
    </div>
  )
}
