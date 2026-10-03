import { useState } from 'react'
import { ChevronDown, ChevronUp, Info } from 'lucide-react'

const KEY = 'icfr.scoping.qualGuideOpen'

/**
 * 질적 요소 안내 — 계정 평가 표 **바로 위**. 1~10 열이 무엇이고 어떻게 판정되는지 늘 보이게 한다
 * (머리글 툴팁이나 표 아래 범례는 발견되지 않는다 — 2026-10-03 마스터). 처음엔 펼쳐 두고, 접으면 이 브라우저가 기억한다.
 */
export default function QualFactorGuide({ factors, rule }: { factors: { value: string; label: string }[]; rule: string }) {
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(KEY) !== '0' } catch { return true }
  })
  const toggle = () => {
    setOpen((v) => {
      try { localStorage.setItem(KEY, v ? '0' : '1') } catch { /* 저장 못 해도 동작 */ }
      return !v
    })
  }
  return (
    <div className="rounded-lg border border-primary/20 bg-accent/50 px-4 py-3 text-sm">
      <button type="button" onClick={toggle} className="flex w-full items-center gap-2 text-left font-semibold">
        <Info className="h-4 w-4 shrink-0" />
        질적 평가 요소 1~10 — 각 요소의 위험을 H(높음)·M(중간)·L(낮음)으로 평가합니다
        <span className="ml-auto flex items-center gap-1 text-xs font-normal text-muted-foreground">
          {open ? <>접기 <ChevronUp className="h-4 w-4" /></> : <>펼치기 <ChevronDown className="h-4 w-4" /></>}
        </span>
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          <p className="text-muted-foreground">{rule}</p>
          <ol className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            {factors.map((f, i) => (
              <li key={f.value} className="flex gap-2">
                <span className="w-5 shrink-0 text-right font-bold text-primary">{i + 1}</span>
                <span>{f.label}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
