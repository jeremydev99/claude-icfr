import { useEffect, useState } from 'react'
import { Download, Share } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { installMode, type InstallMode } from './pwa.pure'

/** Chrome·Edge 의 설치 이벤트 — 표준 타입 정의가 없어 필요한 만큼만 선언한다 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

// 이벤트는 앱이 뜨자마자 한 번 온다 — 버튼이 그려지기 전에 놓치지 않도록 모듈에서 먼저 받아 둔다
let deferred: BeforeInstallPromptEvent | null = null
const listeners = new Set<() => void>()
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferred = e as BeforeInstallPromptEvent
    listeners.forEach((f) => f())
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    listeners.forEach((f) => f())
  })
}

function standalone(): boolean {
  return window.matchMedia?.('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true
}

function currentMode(): InstallMode {
  return installMode({
    standalone: standalone(), hasPromptEvent: Boolean(deferred),
    userAgent: navigator.userAgent, maxTouchPoints: navigator.maxTouchPoints,
  })
}

/**
 * 앱 설치 버튼 (PC 상단 메뉴바·모바일 상단). 이미 설치했거나 지원하지 않는 브라우저에서는 그리지 않는다.
 * iPhone·iPad 는 설치 API 가 없어 "공유 → 홈 화면에 추가" 안내를 띄운다.
 */
export default function InstallButton({ compact = false }: { compact?: boolean }) {
  const [mode, setMode] = useState<InstallMode>(currentMode)
  const [guide, setGuide] = useState(false)
  useEffect(() => {
    const update = () => setMode(currentMode())
    listeners.add(update)
    const mq = window.matchMedia?.('(display-mode: standalone)')
    mq?.addEventListener?.('change', update)
    return () => {
      listeners.delete(update)
      mq?.removeEventListener?.('change', update)
    }
  }, [])

  if (mode === 'installed' || mode === 'unsupported') return null

  const install = async () => {
    if (mode === 'ios-guide') return setGuide(true)
    if (!deferred) return
    await deferred.prompt()
    const { outcome } = await deferred.userChoice
    if (outcome === 'accepted') toast.success('앱을 설치했습니다 — 바탕화면·시작 메뉴(모바일은 홈 화면)에서 열 수 있습니다')
    deferred = null
    setMode(currentMode())
  }

  return (
    <>
      <Button size="sm" variant="outline" onClick={install} className="gap-1" title="ICFR 을 앱으로 설치">
        <Download className="h-4 w-4" />{!compact && '앱 설치'}
      </Button>
      <Dialog open={guide} onOpenChange={setGuide}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>홈 화면에 추가</DialogTitle>
            <DialogDescription>iPhone·iPad 는 Safari 에서 이렇게 설치합니다.</DialogDescription>
          </DialogHeader>
          <ol className="list-decimal space-y-2 pl-5 text-sm">
            <li>아래(또는 위) 막대의 <Share className="inline h-4 w-4" /> <b>공유</b> 버튼을 누릅니다.</li>
            <li><b>홈 화면에 추가</b>를 고릅니다.</li>
            <li>오른쪽 위 <b>추가</b>를 누르면 홈 화면에 ICFR 아이콘이 생깁니다.</li>
          </ol>
        </DialogContent>
      </Dialog>
    </>
  )
}
