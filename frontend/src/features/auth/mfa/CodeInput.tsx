import { Input } from '@/components/ui/input'

/** 인증 코드 입력 — 숫자 6자리(복구 코드 허용 시 XXXX-XXXX). 휴대폰에서 숫자 자판·자동 완성(one-time-code) */
export default function CodeInput({
  value, onChange, allowRecovery = false, autoFocus = true, id = 'mfa-code',
}: { value: string; onChange: (v: string) => void; allowRecovery?: boolean; autoFocus?: boolean; id?: string }) {
  return (
    <Input
      id={id}
      value={value}
      onChange={(e) => onChange(allowRecovery ? e.target.value.toUpperCase().slice(0, 9) : e.target.value.replace(/\D/g, '').slice(0, 6))}
      inputMode={allowRecovery ? 'text' : 'numeric'}
      autoComplete="one-time-code"
      autoFocus={autoFocus}
      placeholder={allowRecovery ? '6자리 또는 복구 코드' : '6자리 숫자'}
      className="h-12 text-center font-mono text-xl tracking-[0.35em] placeholder:font-sans placeholder:text-base placeholder:tracking-normal"
    />
  )
}
