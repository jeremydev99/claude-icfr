import { Controller, useFormContext } from 'react-hook-form'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import type { ControlFormData } from '../ControlFormDialog'

const ACTIVITIES: { name: keyof ControlFormData; label: string }[] = [
  { name: 'activity_approval', label: '승인' },
  { name: 'activity_verification', label: '검증' },
  { name: 'activity_inspection', label: '실사' },
  { name: 'activity_master', label: '마스터' },
  { name: 'activity_reconciliation', label: '조정' },
  { name: 'activity_supervision', label: '감독' },
]

export default function ActivityTab() {
  const { control } = useFormContext<ControlFormData>()

  return (
    <div className="space-y-4 py-2">
      <p className="text-sm text-muted-foreground">
        이 통제에 해당하는 활동 유형을 모두 선택하세요. (복수 선택 가능)
      </p>
      <div className="grid grid-cols-2 gap-3">
        {ACTIVITIES.map(({ name, label }) => (
          <Controller
            key={name}
            name={name}
            control={control}
            render={({ field }) => (
              <div className="flex items-center gap-2">
                <Checkbox
                  id={name}
                  checked={field.value as boolean}
                  onCheckedChange={field.onChange}
                />
                <Label htmlFor={name} className="cursor-pointer font-normal">
                  {label}
                </Label>
              </div>
            )}
          />
        ))}
      </div>
    </div>
  )
}
