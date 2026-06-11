import { useEffect, useState } from 'react'
import { useForm, FormProvider } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import type { Control } from '../types'
import { addControl, updateControl } from '../api/useControls'
import BasicInfoTab from './form-tabs/BasicInfoTab'
import ClassificationTab from './form-tabs/ClassificationTab'
import ActivityTab from './form-tabs/ActivityTab'
import RelatedInfoTab from './form-tabs/RelatedInfoTab'

export const controlFormSchema = z.object({
  code: z.string().min(1, '통제 코드는 필수입니다').max(50),
  name: z.string().min(1, '통제명은 필수입니다').max(200),
  description: z.string().nullable().optional(),
  objective: z.string().nullable().optional(),
  owner_name: z.string().nullable().optional(),
  process_code: z.string().min(1, '프로세스를 선택하세요'),
  sub_process_code: z.string().min(1, '세부 프로세스를 선택하세요'),
  risk_level: z.enum(['LR', 'MR', 'HR', 'SR']),
  is_key_control: z.boolean(),
  preventive_detective: z.enum(['P', 'D']),
  auto_manual: z.enum(['A', 'M', 'IT']),
  frequency: z.enum(['O', 'D', 'W', 'M', 'Q', 'A']),
  ipe_relevant: z.enum(['Y', 'N', 'N/A']),
  activity_approval: z.boolean(),
  activity_verification: z.boolean(),
  activity_physical: z.boolean(),
  activity_master_data: z.boolean(),
  activity_reconciliation: z.boolean(),
  activity_supervision: z.boolean(),
  assertions: z.array(z.enum(['E', 'C', 'R', 'V', 'P', 'O', 'M'])).default([]),
  related_accounts: z.string().nullable().optional(),
  related_systems: z.string().nullable().optional(),
  euc_description: z.string().nullable().optional(),
})

export type ControlFormData = z.infer<typeof controlFormSchema>

const DEFAULT_VALUES: ControlFormData = {
  code: '',
  name: '',
  description: '',
  objective: '',
  owner_name: '',
  process_code: '',
  sub_process_code: '',
  risk_level: 'MR',
  is_key_control: false,
  preventive_detective: 'P',
  auto_manual: 'M',
  frequency: 'M',
  ipe_relevant: 'N/A',
  activity_approval: false,
  activity_verification: false,
  activity_physical: false,
  activity_master_data: false,
  activity_reconciliation: false,
  activity_supervision: false,
  assertions: [],
  related_accounts: '',
  related_systems: '',
  euc_description: '',
}

// Maps form fields to their tab
const FIELD_TAB_MAP: Record<string, string> = {
  code: 'basic', name: 'basic', description: 'basic', objective: 'basic',
  owner_name: 'basic', process_code: 'basic', sub_process_code: 'basic', risk_level: 'basic',
  is_key_control: 'classification', preventive_detective: 'classification',
  auto_manual: 'classification', frequency: 'classification', ipe_relevant: 'classification',
  assertions: 'classification',
  activity_approval: 'activity', activity_verification: 'activity',
  activity_physical: 'activity', activity_master_data: 'activity',
  activity_reconciliation: 'activity', activity_supervision: 'activity',
  related_accounts: 'related', related_systems: 'related', euc_description: 'related',
}

const TAB_ORDER = ['basic', 'classification', 'activity', 'related']

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: 'create' | 'edit'
  control?: Control
  onSuccess?: (saved: Control) => void
}

export default function ControlFormDialog({ open, onOpenChange, mode, control, onSuccess }: Props) {
  const [activeTab, setActiveTab] = useState('basic')

  const methods = useForm<ControlFormData>({
    resolver: zodResolver(controlFormSchema),
    defaultValues: DEFAULT_VALUES,
  })

  const { handleSubmit, reset, formState: { errors, isDirty } } = methods

  useEffect(() => {
    if (!open) return
    if (mode === 'edit' && control) {
      reset({
        code: control.code,
        name: control.name,
        description: control.description ?? '',
        objective: control.objective ?? '',
        owner_name: control.owner_name ?? '',
        process_code: control.process_code ?? '',
        sub_process_code: control.sub_process_code ?? '',
        risk_level: control.risk_level ?? undefined,
        is_key_control: control.is_key_control,
        preventive_detective: control.preventive_detective,
        auto_manual: control.auto_manual,
        frequency: control.frequency,
        ipe_relevant: control.ipe_relevant,
        activity_approval: control.activity_approval,
        activity_verification: control.activity_verification,
        activity_physical: control.activity_physical,
        activity_master_data: control.activity_master_data,
        activity_reconciliation: control.activity_reconciliation,
        activity_supervision: control.activity_supervision,
        assertions: control.assertions ?? [],
        related_accounts: control.related_accounts ?? '',
        related_systems: control.related_systems ?? '',
        euc_description: control.euc_description ?? '',
      })
    } else {
      reset(DEFAULT_VALUES)
    }
    setActiveTab('basic')
  }, [open, mode, control, reset])

  // Count errors per tab
  const errorTabCounts: Record<string, number> = {}
  for (const field of Object.keys(errors)) {
    const tab = FIELD_TAB_MAP[field]
    if (tab) errorTabCounts[tab] = (errorTabCounts[tab] ?? 0) + 1
  }

  const onSubmit = (data: ControlFormData) => {
    let saved: Control
    if (mode === 'create') {
      saved = addControl({
        ...data,
        description: data.description || null,
        objective: data.objective || null,
        owner_name: data.owner_name || null,
        related_accounts: data.related_accounts || null,
        related_systems: data.related_systems || null,
        euc_description: data.euc_description || null,
        risk_id: '',
      })
    } else {
      const result = updateControl(control!.id, {
        ...data,
        description: data.description || null,
        objective: data.objective || null,
        owner_name: data.owner_name || null,
        related_accounts: data.related_accounts || null,
        related_systems: data.related_systems || null,
        euc_description: data.euc_description || null,
      })
      if (!result) return
      saved = result
    }
    toast.success('저장되었습니다')
    onSuccess?.(saved)
    onOpenChange(false)
  }

  const onInvalid = () => {
    // Navigate to the first tab that has errors
    for (const tab of TAB_ORDER) {
      if (errorTabCounts[tab]) {
        setActiveTab(tab)
        break
      }
    }
  }

  const handleCancel = () => {
    if (isDirty && !window.confirm('저장하지 않고 닫을까요?')) return
    onOpenChange(false)
  }

  function TabLabel({ tab, label }: { tab: string; label: string }) {
    const count = errorTabCounts[tab]
    return (
      <span className="flex items-center gap-1">
        {label}
        {count ? (
          <span className="inline-flex items-center justify-center rounded-full bg-destructive text-destructive-foreground text-[10px] w-4 h-4 font-bold">
            {count}
          </span>
        ) : null}
      </span>
    )
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleCancel() }}>
      <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-6 pt-6 pb-3">
          <DialogTitle>{mode === 'create' ? '통제 추가' : '통제 편집'}</DialogTitle>
        </DialogHeader>

        <FormProvider {...methods}>
          <form onSubmit={handleSubmit(onSubmit, onInvalid)} className="flex flex-col flex-1 min-h-0">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col flex-1 min-h-0">
              <div className="px-6">
                <TabsList className="w-full grid grid-cols-4">
                  <TabsTrigger value="basic">
                    <TabLabel tab="basic" label="기본 정보" />
                  </TabsTrigger>
                  <TabsTrigger value="classification">
                    <TabLabel tab="classification" label="분류" />
                  </TabsTrigger>
                  <TabsTrigger value="activity">
                    <TabLabel tab="activity" label="활동 유형" />
                  </TabsTrigger>
                  <TabsTrigger value="related">
                    <TabLabel tab="related" label="관련 정보" />
                  </TabsTrigger>
                </TabsList>
              </div>

              <div className="flex-1 overflow-y-auto px-6 py-2">
                <TabsContent value="basic" className="mt-0">
                  <BasicInfoTab isEditMode={mode === 'edit'} />
                </TabsContent>
                <TabsContent value="classification" className="mt-0">
                  <ClassificationTab />
                </TabsContent>
                <TabsContent value="activity" className="mt-0">
                  <ActivityTab />
                </TabsContent>
                <TabsContent value="related" className="mt-0">
                  <RelatedInfoTab />
                </TabsContent>
              </div>
            </Tabs>

            <DialogFooter className="px-6 py-4 border-t flex items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                ⓘ mock 데이터입니다 — 새로고침 시 초기화됩니다.
              </p>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={handleCancel}>
                  취소
                </Button>
                <Button type="submit">저장</Button>
              </div>
            </DialogFooter>
          </form>
        </FormProvider>
      </DialogContent>
    </Dialog>
  )
}
