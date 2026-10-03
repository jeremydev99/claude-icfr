import { useEffect, useState } from 'react'
import { Loader2, Smartphone } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import CodeInput from './CodeInput'
import RecoveryCodes from './RecoveryCodes'
import { errDetail, useMfaEnable, useMfaSetup, type MfaEnableResult } from './api'

/**
 * 인증 앱(TOTP) 등록 — QR 스캔 → 첫 코드 확인 → 복구 코드 보관.
 * 로그인 중 등록이면 `mfaToken` 을 넘기고, 끝나면 `onDone` 이 토큰을 받는다(로그인 완료).
 * 로그인한 상태(사이드바)에서는 `mfaToken` 없이 쓴다.
 */
export default function MfaEnroll({ mfaToken, onDone }: {
  mfaToken?: string | null
  onDone: (result: MfaEnableResult) => void
}) {
  const setup = useMfaSetup()
  const enable = useMfaEnable()
  const [code, setCode] = useState('')
  const [result, setResult] = useState<MfaEnableResult | null>(null)
  const [showKey, setShowKey] = useState(false)

  useEffect(() => {
    setup.mutate(mfaToken)
    // 처음 한 번만 — 다시 부르면 비밀값이 바뀌어 이미 스캔한 QR 이 무효가 된다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (result) return <RecoveryCodes codes={result.recovery_codes} onDone={() => onDone(result)} />

  if (!setup.data) {
    return (
      <div className="flex flex-col items-center gap-3 py-8 text-sm text-muted-foreground">
        {setup.isError ? (
          <>
            <p className="text-destructive">{errDetail(setup.error) ?? '등록을 시작하지 못했습니다'}</p>
            <Button variant="outline" size="sm" onClick={() => setup.mutate(mfaToken)}>다시 시도</Button>
          </>
        ) : (
          <><Loader2 className="h-5 w-5 animate-spin" />준비 중…</>
        )}
      </div>
    )
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    enable.mutate({ mfa_token: mfaToken, code }, { onSuccess: setResult })
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <ol className="space-y-1.5 text-sm text-muted-foreground">
        <li className="flex gap-2"><Smartphone className="mt-0.5 h-4 w-4 shrink-0" />
          휴대폰에 인증 앱(Google Authenticator·Microsoft Authenticator·네이버 앱 OTP 등)을 설치하세요.</li>
        <li>① 앱에서 QR 을 스캔하고 ② 앱에 뜬 6자리를 아래에 입력하세요.</li>
      </ol>
      <div className="flex flex-col items-center gap-2">
        <img src={setup.data.qr_svg} alt="인증 앱 등록 QR 코드" className="h-48 w-48 rounded-lg border bg-white p-2" />
        {/* 휴대폰 한 대로 접속 중이면 QR 을 찍을 수 없다 — 앱 연결 링크와 수동 입력 키 */}
        <a href={setup.data.otpauth_uri} className="text-sm text-primary underline-offset-2 hover:underline md:hidden">
          이 휴대폰의 인증 앱으로 열기
        </a>
        <button type="button" className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          onClick={() => setShowKey((v) => !v)}>
          {showKey ? '키 숨기기' : 'QR 을 쓸 수 없나요? 키 직접 입력'}
        </button>
        {showKey && (
          <code className="select-all break-all rounded bg-muted px-2 py-1 text-center font-mono text-sm">
            {setup.data.secret.replace(/(.{4})/g, '$1 ').trim()}
          </code>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="mfa-code">앱에 표시된 6자리</Label>
        <CodeInput value={code} onChange={setCode} autoFocus={false} />
      </div>
      {enable.isError && (
        <p className="text-center text-sm text-destructive" role="alert">{errDetail(enable.error) ?? '확인하지 못했습니다'}</p>
      )}
      <Button type="submit" className="h-11 w-full" disabled={code.length !== 6 || enable.isPending}>
        {enable.isPending ? '확인 중…' : '등록'}
      </Button>
    </form>
  )
}
