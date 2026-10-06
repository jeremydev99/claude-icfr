import { useEffect, useState } from 'react'
import { useForm, FormProvider } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { isAxiosError } from 'axios'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import type { Control, ControlCreatePayload, ControlUpdatePayload } from '../types'
import { useCreateControl, useUpdateControl } from '../api/useControls'
import { useChangeAction, useControlChange } from '../changes/api'
import { toControl } from '../api/controlsAdapter'
import { isBaseline } from '../api/sourceEnvelope'
import BasicInfoTab from './form-tabs/BasicInfoTab'
import ClassificationTab from './form-tabs/ClassificationTab'
import ActivityTab from './form-tabs/ActivityTab'
import RelatedInfoTab from './form-tabs/RelatedInfoTab'

function extractErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const data = err.response?.data
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg: string }) => d.msg).join(', ')
    if (err.response?.status === 401) return '로그인이 필요합니다'
    if (err.response?.status === 422) return '입력값을 확인해주세요'
    if (err.response?.status === 409) return '이미 존재하는 통제 코드입니다'
    if (!err.response) return '서버에 연결할 수 없습니다'
  }
  return '알 수 없는 오류가 발생했습니다'
}

export const controlFormSchema = z.object({
  code: z.string().min(1, '통제 코드는 필수입니다').max(30),
  name: z.string().min(1, '통제명은 필수입니다').max(500),
  description: z.string().nullable().optional(),
  objective: z.string().nullable().optional(),
  owner_name: z.string().nullable().optional(),
  process_code: z.string().min(1, '프로세스를 선택하세요'),
  sub_process_code: z.string().min(1, '세부 프로세스를 선택하세요'),
  risk_level: z.enum(['LR', 'MR', 'HR', 'SR']),
  risk_id: z.string().optional(),
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
  risk_id: '',
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
  const createMutation = useCreateControl()
  const updateMutation = useUpdateControl()
  // 편집은 결재를 거친다(2026-10-06): 임시저장 → 상신 → 조직장 → 내부회계 일괄 상신 → 내부회계관리자 승인 → 반영.
  // 바로 반영은 내부회계관리자만(서버 판정 direct_edit)
  const { data: changeInfo } = useControlChange(mode === 'edit' && open ? control?.id : undefined)
  const change = changeInfo?.change ?? null
  const changeAction = useChangeAction()
  const [action, setAction] = useState<'draft' | 'submit' | 'direct'>('draft')
  const lockedByOther = !!change && (!change.is_mine || !['draft', 'rejected'].includes(change.status))
  const isPending = createMutation.isPending || updateMutation.isPending || changeAction.isPending
  const showBaselineHint = mode === 'edit' && isBaseline(control?.envelope)

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
        risk_level: control.risk_level ?? 'MR',
        risk_id: control.risk_id,
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
        // 내 임시저장(또는 반려된 변경)이 있으면 그 값으로 이어서 고친다
        ...(change && change.is_mine && ['draft', 'rejected'].includes(change.status)
          ? Object.fromEntries(Object.entries(change.changes).map(([k, v]) => [k, v ?? '']))
          : {}),
      })
    } else {
      reset(DEFAULT_VALUES)
    }
    setActiveTab('basic')
  }, [open, mode, control, reset, change])

  const errorTabCounts: Record<string, number> = {}
  for (const field of Object.keys(errors)) {
    const tab = FIELD_TAB_MAP[field]
    if (tab) errorTabCounts[tab] = (errorTabCounts[tab] ?? 0) + 1
  }

  const onSubmit = async (data: ControlFormData) => {
    try {
      if (mode === 'create') {
        if (!data.risk_id) {
          toast.error('프로세스 → 세부 프로세스 → 위험 수준을 선택하여 위험 항목을 연결해주세요')
          setActiveTab('basic')
          return
        }
        const payload: ControlCreatePayload = {
          code: data.code,
          name: data.name,
          risk_id: data.risk_id,
          description: data.description || null,
          objective: data.objective || null,
          owner_name: data.owner_name || null,
          is_key_control: data.is_key_control,
          preventive_detective: data.preventive_detective,
          auto_manual: data.auto_manual,
          frequency: data.frequency,
          ipe_relevant: data.ipe_relevant,
          activity_approval: data.activity_approval,
          activity_verification: data.activity_verification,
          activity_physical: data.activity_physical,
          activity_master_data: data.activity_master_data,
          activity_reconciliation: data.activity_reconciliation,
          activity_supervision: data.activity_supervision,
          related_accounts: data.related_accounts || null,
          related_systems: data.related_systems || null,
          euc_description: data.euc_description || null,
        }
        const saved = await createMutation.mutateAsync(payload)
        toast.success('통제가 추가되었습니다')
        onSuccess?.(toControl(saved))
      } else if (mode === 'edit' && control) {
        const payload: ControlUpdatePayload = {
          name: data.name,
          description: data.description || null,
          objective: data.objective || null,
          owner_name: data.owner_name || null,
          is_key_control: data.is_key_control,
          preventive_detective: data.preventive_detective,
          auto_manual: data.auto_manual,
          frequency: data.frequency,
          ipe_relevant: data.ipe_relevant,
          activity_approval: data.activity_approval,
          activity_verification: data.activity_verification,
          activity_physical: data.activity_physical,
          activity_master_data: data.activity_master_data,
          activity_reconciliation: data.activity_reconciliation,
          activity_supervision: data.activity_supervision,
          related_accounts: data.related_accounts || null,
          related_systems: data.related_systems || null,
          euc_description: data.euc_description || null,
        }
        if (action === 'direct') {
          const saved = await updateMutation.mutateAsync({ id: control.id, payload })
          toast.success('통제를 바로 반영했습니다')
          onSuccess?.(toControl(saved))
        } else {
          const draft = await changeAction.mutateAsync({ method: 'put', url: `/api/rcm-changes/control/${control.id}`, body: { changes: payload } }) as { id: string; dept_approver: string | null }
          if (action === 'submit') {
            const r = await changeAction.mutateAsync({ method: 'post', url: `/api/rcm-changes/${draft.id}/submit` }) as { status: string; dept_approver: string | null; dept_skipped: string | null }
            toast.success(r.status === 'dept_review' ? `상신했습니다 — 조직장(${r.dept_approver}) 결재 대기` : `상신했습니다 — ${r.dept_skipped}, 내부회계 대기함으로`)
          } else {
            toast.success('임시저장했습니다 — 상신해야 결재가 시작됩니다')
          }
        }
      }
      onOpenChange(false)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    }
  }

  const onInvalid = () => {
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
          <DialogDescription>
            {mode === 'create' ? '새 통제를 등록합니다.' : '통제 정보를 수정합니다.'} 필수 항목을 모두 입력해 주세요.
          </DialogDescription>
          {showBaselineHint && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2.5 py-1.5">
              이 통제는 기준(baseline)입니다 — 반영 시 귀사 재정의(override)로 기록됩니다.
            </p>
          )}
          {mode === 'edit' && (
            <p className="rounded border bg-muted/60 px-2.5 py-1.5 text-xs text-muted-foreground">
              {change
                ? <>진행 중인 변경: <b>{change.status_label}</b> · 작성 {change.author}{change.rejected_by && change.status === 'rejected'
                    ? ` · 반려 사유: ${(change.rejected_by === 'dept' ? change.dept_note : change.admin_note) ?? '-'}` : ''}
                    {lockedByOther && ' — 결재가 끝나기 전에는 고칠 수 없습니다'}</>
                : <>고친 내용은 <b>임시저장</b> 후 <b>상신</b>하면 조직장 → 내부회계 담당자 → 내부회계관리자 승인을 거쳐 반영됩니다.</>}
            </p>
          )}
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
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={handleCancel} disabled={isPending}>
                  취소
                </Button>
                {mode === 'create' ? (
                  <Button type="submit" disabled={isPending}>{isPending ? '저장 중...' : '저장'}</Button>
                ) : (
                  <>
                    <Button type="submit" variant="outline" disabled={isPending || lockedByOther} onClick={() => setAction('draft')}>
                      임시저장
                    </Button>
                    <Button type="submit" disabled={isPending || lockedByOther} onClick={() => setAction('submit')}>
                      {isPending && action === 'submit' ? '상신 중...' : '임시저장 후 상신'}
                    </Button>
                    {changeInfo?.direct_edit && (
                      <Button type="submit" variant="ghost" disabled={isPending} onClick={() => setAction('direct')}
                        title="결재 없이 바로 RCM 에 반영합니다(내부회계관리자) — 이력에 남습니다">
                        바로 반영
                      </Button>
                    )}
                  </>
                )}
              </div>
            </DialogFooter>
          </form>
        </FormProvider>
      </DialogContent>
    </Dialog>
  )
}
