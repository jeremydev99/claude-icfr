import { useEffect } from 'react'
import { toast } from 'sonner'
import { useRegisterSW } from 'virtual:pwa-register/react'

const CHECK_INTERVAL_MS = 60 * 60 * 1000   // 1시간마다 새 버전 확인(오래 열어 두는 화면 대비)

/**
 * 서비스워커 등록 + 새 버전 알림 (PWA). 배포되면 "새 버전이 있습니다" 알림에서 새로고침을 눌러 적용한다 —
 * 작업 중(입력·업로드 미리보기)에 화면이 저절로 바뀌지 않게 자동 적용하지 않는다.
 */
export default function PwaUpdatePrompt() {
  const { needRefresh: [needRefresh], updateServiceWorker } = useRegisterSW({
    onRegisteredSW(_url, reg) {
      if (reg) setInterval(() => { reg.update().catch(() => undefined) }, CHECK_INTERVAL_MS)
    },
  })
  useEffect(() => {
    if (!needRefresh) return
    toast('새 버전이 있습니다', {
      description: '저장하지 않은 입력이 없으면 새로고침해 적용하세요.',
      duration: Infinity,
      action: { label: '새로고침', onClick: () => updateServiceWorker(true) },
    })
  }, [needRefresh, updateServiceWorker])
  return null
}
