import { useFormContext } from 'react-hook-form'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { listToMethods, METHODS, methodsToList } from '@/features/my-assessment/myAssessment.pure'
import { Textarea } from '@/components/ui/textarea'
import type { ControlFormData } from '../ControlFormDialog'

export default function RelatedInfoTab() {
  const { register, watch, setValue, formState: { errors } } = useFormContext<ControlFormData>()
  const methods = methodsToList(watch('test_methods'))

  return (
    <div className="space-y-4 py-2">
      <div className="space-y-1.5">
        <Label htmlFor="related_accounts">관련 계정</Label>
        <Textarea
          id="related_accounts"
          {...register('related_accounts')}
          rows={3}
          placeholder="예: 매출채권, 매출"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="related_systems">관련 시스템</Label>
        <Textarea
          id="related_systems"
          {...register('related_systems')}
          rows={3}
          placeholder="예: ERP(SAP), 엑셀"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="euc_description">EUC 설명</Label>
        <Textarea
          id="euc_description"
          {...register('euc_description')}
          rows={3}
          placeholder="EUC(End User Computing) 관련 설명을 입력하세요"
        />
      </div>

      <div className="space-y-3 rounded-md border p-3">
        <p className="text-sm font-medium">테스트 방법 — 운영평가 샘플 기준</p>
        <div className="flex flex-wrap gap-4 text-sm">
          {METHODS.map((m) => (
            <label key={m.value} className="flex items-center gap-1.5">
              <Checkbox checked={methods.includes(m.value)} onCheckedChange={(v) => setValue('test_methods',
                listToMethods(v ? [...methods, m.value] : methods.filter((x) => x !== m.value)), { shouldDirty: true })} />
              {m.label}
            </label>
          ))}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sample_size">표본수</Label>
          <Input id="sample_size" inputMode="numeric" className="w-32" {...register('sample_size')}
            placeholder="비우면 주기 기준" />
          <p className="text-xs text-muted-foreground">감사인과 협의한 값. 운영평가에서 이 수만큼 샘플을 채워야 제출됩니다.</p>
          {errors.sample_size && <p className="text-xs text-destructive">{String(errors.sample_size.message)}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="population">모집단</Label>
          <Input id="population" {...register('population')} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="test_procedure">테스트 절차</Label>
          <Textarea id="test_procedure" rows={4} {...register('test_procedure')} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="control_status">통제현황</Label>
          <Textarea id="control_status" rows={5} {...register('control_status')} />
          <p className="text-xs text-muted-foreground">WTT 수준의 통제 운영 현황. 내 평가 테스트 화면에 함께 보입니다.</p>
        </div>
      </div>
    </div>
  )
}
