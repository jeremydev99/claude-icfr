import { useFormContext } from 'react-hook-form'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { ControlFormData } from '../ControlFormDialog'

export default function RelatedInfoTab() {
  const { register } = useFormContext<ControlFormData>()

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
    </div>
  )
}
