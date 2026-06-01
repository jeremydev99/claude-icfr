import { CheckCircle2, Circle, Star } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { Control } from '../types'
import {
  ASSERTION_LABELS,
  AUTO_MANUAL_LABELS,
  FREQUENCY_LABELS,
  PD_LABELS,
  RISK_LEVEL_LABELS,
} from '../types'

interface Props {
  control: Control | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const RISK_BADGE_CLASS: Record<string, string> = {
  SR: 'bg-red-100 text-red-700 border-red-200',
  HR: 'bg-orange-100 text-orange-700 border-orange-200',
  MR: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  LR: 'bg-green-100 text-green-700 border-green-200',
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2 py-1.5 text-sm">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="break-words">{value ?? '—'}</span>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <p className="text-sm font-semibold text-foreground mt-6 mb-1">{children}</p>
}

const ACTIVITIES: { key: keyof Control; label: string }[] = [
  { key: 'activity_approval', label: '승인' },
  { key: 'activity_verification', label: '검증' },
  { key: 'activity_inspection', label: '실사' },
  { key: 'activity_master', label: '마스터' },
  { key: 'activity_reconciliation', label: '조정' },
  { key: 'activity_supervision', label: '감독' },
]

export default function ControlDetailSheet({ control, open, onOpenChange }: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-xl overflow-y-auto">
        {control && (
          <>
            <SheetHeader className="pr-2">
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <SheetTitle className="text-xl font-bold">{control.code}</SheetTitle>
                    {control.is_key_control && (
                      <span className="inline-flex items-center gap-0.5 text-amber-600 text-xs font-medium">
                        <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" />
                        핵심
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{control.name}</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled
                  title="준비중입니다"
                  className="shrink-0 mr-8"
                >
                  편집
                </Button>
              </div>
            </SheetHeader>

            <div className="mt-4 space-y-1">
              <SectionTitle>기본 정보</SectionTitle>
              <Separator />
              <InfoRow label="프로세스" value={control.process_code} />
              <InfoRow label="세부 프로세스" value={control.sub_process_code} />
              <InfoRow
                label="위험 수준"
                value={
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${RISK_BADGE_CLASS[control.risk_level]}`}
                  >
                    {RISK_LEVEL_LABELS[control.risk_level]}
                  </span>
                }
              />
              <InfoRow label="통제 목적" value={control.objective} />
              <InfoRow label="담당자" value={control.owner_name} />

              <SectionTitle>통제 분류</SectionTitle>
              <Separator />
              <InfoRow label="예방/적발" value={PD_LABELS[control.preventive_detective]} />
              <InfoRow label="자동/수동" value={AUTO_MANUAL_LABELS[control.auto_manual]} />
              <InfoRow label="수행 주기" value={FREQUENCY_LABELS[control.frequency]} />
              <InfoRow label="IPE 관련성" value={control.ipe_relevant} />
              <InfoRow label="핵심통제" value={control.is_key_control ? '예' : '아니오'} />

              <SectionTitle>통제 활동 유형</SectionTitle>
              <Separator />
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 py-2">
                {ACTIVITIES.map(({ key, label }) => {
                  const active = control[key] as boolean
                  return (
                    <div key={key} className="flex items-center gap-1.5 text-sm">
                      {active ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                      ) : (
                        <Circle className="h-4 w-4 text-muted-foreground/40 shrink-0" />
                      )}
                      <span className={active ? '' : 'text-muted-foreground'}>{label}</span>
                    </div>
                  )
                })}
              </div>

              <SectionTitle>어서션</SectionTitle>
              <Separator />
              <div className="flex flex-wrap gap-1.5 py-2">
                {control.assertions.length > 0 ? (
                  control.assertions.map((a) => (
                    <Badge key={a} variant="secondary" className="text-xs">
                      {a} {ASSERTION_LABELS[a]}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">—</span>
                )}
              </div>

              <SectionTitle>관련 정보</SectionTitle>
              <Separator />
              {(control.related_accounts ||
                control.related_systems ||
                control.euc_description ||
                control.description) ? (
                <>
                  <InfoRow label="관련 계정" value={control.related_accounts} />
                  <InfoRow label="관련 시스템" value={control.related_systems} />
                  <InfoRow label="EUC 설명" value={control.euc_description} />
                  <InfoRow label="통제 설명" value={control.description} />
                </>
              ) : (
                <p className="text-sm text-muted-foreground py-2">정보 없음</p>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
