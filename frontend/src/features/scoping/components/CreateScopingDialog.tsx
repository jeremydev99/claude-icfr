import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

export type ScopingSource = 'template' | 'financial_statements'

/**
 * 새 회계연도 스코핑 (8-E, 마스터 확정 A안) — 계정 행의 원천을 고른다.
 *
 * - 표준 템플릿: 계정 192건·질적 평가값·판단 근거를 복사(기존 방식). 금액은 직접 입력.
 * - 재무제표 기반: 기준 연도(직전 연도) **확정** 재무제표의 계정·금액으로 행을 만들고, 재무제표 화면에서
 *   확정한 템플릿 연결로 질적 평가 기본값을 가져온다. 주석은 템플릿에서 복사한다.
 */
export default function CreateScopingDialog({ open, onOpenChange, onCreate, pending }: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onCreate: (year: number, source: ScopingSource) => void
  pending: boolean
}) {
  const [year, setYear] = useState(String(new Date().getFullYear()))
  const [source, setSource] = useState<ScopingSource>('financial_statements')
  const y = Number(year)
  const valid = Number.isInteger(y) && y >= 2000 && y <= 2100
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>새 회계연도 스코핑</DialogTitle>
          <DialogDescription>계정 행을 어디에서 가져올지 고르세요. 중요성 기준·문구는 어느 쪽이든 표준 템플릿에서 옵니다.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <label className="flex items-center gap-2">
            회계연도 <Input value={year} onChange={(e) => setYear(e.target.value)} className="h-9 w-28" inputMode="numeric" />
          </label>
          <label className="flex items-start gap-2 rounded border p-3">
            <input type="radio" className="mt-1" checked={source === 'financial_statements'} onChange={() => setSource('financial_statements')} />
            <span>
              <b>재무제표 기반 (권장)</b>
              <span className="block text-xs text-muted-foreground">
                {valid ? `${y - 1}` : '직전'} 회계연도 <b>확정</b> 별도재무제표(재무상태표·손익계산서 필수, 현금흐름표 선택)의 계정과 금액으로
                행을 만듭니다. 질적 평가 기본값은 재무제표 화면 &gt; 스코핑 템플릿 연결에서 확정한 연결로 가져옵니다.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2 rounded border p-3">
            <input type="radio" className="mt-1" checked={source === 'template'} onChange={() => setSource('template')} />
            <span>
              <b>표준 템플릿</b>
              <span className="block text-xs text-muted-foreground">
                계정 192건·질적 평가값·판단 근거를 복사합니다. 금액은 직접 입력합니다(기존 방식).
              </span>
            </span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>취소</Button>
          <Button disabled={!valid || pending} onClick={() => onCreate(y, source)}>
            {pending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}만들기
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
