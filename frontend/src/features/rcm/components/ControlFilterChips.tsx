import { X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { ControlSearchParams } from '../types'
import {
  ASSERTION_LABELS,
  AUTO_MANUAL_LABELS,
  FREQUENCY_LABELS,
  PD_LABELS,
  RISK_LEVEL_LABELS,
} from '../types'

interface Props {
  params: ControlSearchParams
  onChange: (updated: Partial<ControlSearchParams>) => void
}

type Chip = { label: string; onRemove: () => void }

export default function ControlFilterChips({ params, onChange }: Props) {
  const chips: Chip[] = []

  if (params.q) {
    chips.push({ label: `검색: ${params.q}`, onRemove: () => onChange({ q: undefined, skip: 0 }) })
  }
  if (params.process_code) {
    chips.push({
      label: `프로세스: ${params.process_code}`,
      onRemove: () => onChange({ process_code: undefined, skip: 0 }),
    })
  }
  if (params.risk_level) {
    chips.push({
      label: `위험수준: ${RISK_LEVEL_LABELS[params.risk_level]}`,
      onRemove: () => onChange({ risk_level: undefined, skip: 0 }),
    })
  }
  if (params.frequency) {
    chips.push({
      label: `주기: ${FREQUENCY_LABELS[params.frequency]}`,
      onRemove: () => onChange({ frequency: undefined, skip: 0 }),
    })
  }
  if (params.auto_manual) {
    chips.push({
      label: `자동/수동: ${AUTO_MANUAL_LABELS[params.auto_manual]}`,
      onRemove: () => onChange({ auto_manual: undefined, skip: 0 }),
    })
  }
  if (params.preventive_detective) {
    chips.push({
      label: `예방/적발: ${PD_LABELS[params.preventive_detective]}`,
      onRemove: () => onChange({ preventive_detective: undefined, skip: 0 }),
    })
  }
  if (params.assertion) {
    chips.push({
      label: `어서션: ${ASSERTION_LABELS[params.assertion]}`,
      onRemove: () => onChange({ assertion: undefined, skip: 0 }),
    })
  }
  if (params.is_key_control !== undefined) {
    chips.push({
      label: '핵심통제',
      onRemove: () => onChange({ is_key_control: undefined, skip: 0 }),
    })
  }

  if (chips.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <Badge
          key={chip.label}
          variant="secondary"
          className="gap-1 pr-1 text-xs font-normal cursor-default"
        >
          {chip.label}
          <button
            onClick={chip.onRemove}
            className="ml-0.5 rounded-full hover:bg-muted p-0.5"
            aria-label={`${chip.label} 필터 제거`}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}
    </div>
  )
}
