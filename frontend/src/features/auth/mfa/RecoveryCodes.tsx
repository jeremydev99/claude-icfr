import { useState } from 'react'
import { Check, Copy, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'

/** 복구 코드 10개 — **이 화면에서 한 번만** 보인다. 서버에는 해시만 남는다 */
export default function RecoveryCodes({ codes, onDone, doneLabel = '보관했습니다 — 계속' }: {
  codes: string[]; onDone: () => void; doneLabel?: string
}) {
  const [copied, setCopied] = useState(false)
  const [saved, setSaved] = useState(false)
  const text = codes.join('\n')
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setSaved(true)
    } catch {
      /* 복사가 막힌 환경 — 내려받기를 쓴다 */
    }
  }
  const download = () => {
    const blob = new Blob([`ICFR 복구 코드 (각 1회용)\n\n${text}\n`], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'icfr-recovery-codes.txt'
    a.click()
    URL.revokeObjectURL(a.href)
    setSaved(true)
  }
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
        휴대폰을 잃어버렸을 때 이 코드로 로그인합니다. <b>지금 한 번만</b> 보여 드립니다 — 안전한 곳에 보관하세요.
        각 코드는 한 번만 쓸 수 있습니다.
      </div>
      <ol className="grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-lg bg-muted px-5 py-4 font-mono text-[15px]">
        {codes.map((c) => <li key={c}>{c}</li>)}
      </ol>
      <div className="flex gap-2">
        <Button type="button" variant="outline" className="flex-1" onClick={copy}>
          {copied ? <Check className="mr-1.5 h-4 w-4" /> : <Copy className="mr-1.5 h-4 w-4" />}
          {copied ? '복사됨' : '복사'}
        </Button>
        <Button type="button" variant="outline" className="flex-1" onClick={download}>
          <Download className="mr-1.5 h-4 w-4" />내려받기
        </Button>
      </div>
      <Button type="button" className="h-11 w-full" disabled={!saved} onClick={onDone}>{doneLabel}</Button>
      {!saved && <p className="text-center text-xs text-muted-foreground">복사하거나 내려받으면 계속할 수 있습니다</p>}
    </div>
  )
}
