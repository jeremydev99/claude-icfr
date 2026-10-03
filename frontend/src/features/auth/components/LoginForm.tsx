import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useFinishLogin, useLogin, useMfaVerify } from '../hooks/useAuth'
import { loginErrorMessage } from '../loginError.pure'
import CodeInput from '../mfa/CodeInput'
import MfaEnroll from '../mfa/MfaEnroll'
import { errDetail } from '../mfa/api'

const loginSchema = z.object({
  email: z.string().min(1, '이메일을 입력하세요').email('올바른 이메일 형식이 아닙니다'),
  password: z.string().min(6, '비밀번호는 최소 6자 이상이어야 합니다'),
})

type LoginFormValues = z.infer<typeof loginSchema>

/** 로그인 단계 — 비밀번호 → (MFA 등록돼 있으면) 코드 입력 / (의무인데 미등록이면) 등록 (ADR-0039) */
type Step = { kind: 'password' } | { kind: 'verify'; token: string } | { kind: 'setup'; token: string }

export default function LoginForm({ initialStep }: { initialStep?: Step } = {}) {
  const [step, setStep] = useState<Step>(initialStep ?? { kind: 'password' })
  const back = () => setStep({ kind: 'password' })

  if (step.kind === 'verify') return <VerifyStep token={step.token} onBack={back} />
  if (step.kind === 'setup') return <SetupStep token={step.token} onBack={back} />
  return <PasswordStep onNext={setStep} />
}

function PasswordStep({ onNext }: { onNext: (s: Step) => void }) {
  const loginMutation = useLogin()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = (data: LoginFormValues) => {
    loginMutation.mutate(data, {
      onSuccess: (r) => {
        if (r.mfa_required && r.mfa_token) onNext({ kind: 'verify', token: r.mfa_token })
        else if (r.mfa_setup_required && r.mfa_token) onNext({ kind: 'setup', token: r.mfa_token })
      },
    })
  }

  return (
    <Card className="w-full max-w-[420px] border-border/70 shadow-lift">
      <CardHeader className="space-y-1.5 pb-4">
        <CardTitle className="text-2xl font-bold tracking-tight">로그인</CardTitle>
        <CardDescription>회사 계정 또는 초대받은 계정으로 로그인하세요.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">이메일</Label>
            <Input
              id="email"
              type="email"
              inputMode="email"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              placeholder="이메일을 입력하세요"
              {...register('email')}
            />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">비밀번호</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="비밀번호를 입력하세요"
              {...register('password')}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>

          {loginMutation.error && (
            <p className="text-sm text-destructive text-center" role="alert">
              {loginErrorMessage(loginMutation.error)}
            </p>
          )}

          <Button type="submit" size="lg" className="h-11 w-full text-[15px] font-semibold" disabled={loginMutation.isPending}>
            {loginMutation.isPending ? '로그인 중...' : '로그인'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function StepCard({ title, desc, onBack, children }: {
  title: string; desc: string; onBack: () => void; children: React.ReactNode
}) {
  return (
    <Card className="w-full max-w-[420px] border-border/70 shadow-lift">
      <CardHeader className="space-y-1.5 pb-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary" />
          <CardTitle className="text-2xl font-bold tracking-tight">{title}</CardTitle>
        </div>
        <CardDescription>{desc}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {children}
        <button type="button" onClick={onBack}
          className="block w-full text-center text-sm text-muted-foreground underline-offset-2 hover:underline">
          처음으로 — 다른 계정으로 로그인
        </button>
      </CardContent>
    </Card>
  )
}

function VerifyStep({ token, onBack }: { token: string; onBack: () => void }) {
  const verify = useMfaVerify()
  const [code, setCode] = useState('')
  const [recovery, setRecovery] = useState(false)
  const ready = recovery ? code.replace('-', '').length === 8 : code.length === 6
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    verify.mutate({ mfa_token: token, code })
  }
  const expired = (verify.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail?.includes('만료')
  return (
    <StepCard title="2단계 인증" desc={recovery ? '보관해 둔 복구 코드(XXXX-XXXX)를 입력하세요. 한 번 쓰면 사라집니다.' : '휴대폰 인증 앱에 표시된 6자리를 입력하세요.'} onBack={onBack}>
      <form onSubmit={submit} className="space-y-4">
        <CodeInput value={code} onChange={setCode} allowRecovery={recovery} />
        {verify.isError && (
          <p className="text-center text-sm text-destructive" role="alert">{errDetail(verify.error) ?? '확인하지 못했습니다'}</p>
        )}
        {expired ? (
          <Button type="button" className="h-11 w-full" onClick={onBack}>다시 로그인</Button>
        ) : (
          <Button type="submit" className="h-11 w-full" disabled={!ready || verify.isPending}>
            {verify.isPending ? '확인 중…' : '확인'}
          </Button>
        )}
      </form>
      <button type="button" onClick={() => { setRecovery((v) => !v); setCode('') }}
        className="block w-full text-center text-sm text-primary underline-offset-2 hover:underline">
        {recovery ? '인증 앱 코드로 입력' : '휴대폰을 쓸 수 없나요? 복구 코드 사용'}
      </button>
    </StepCard>
  )
}

function SetupStep({ token, onBack }: { token: string; onBack: () => void }) {
  const finish = useFinishLogin()
  return (
    <StepCard title="2단계 인증 등록" desc="이 계정은 2단계 인증이 필요합니다. 처음 한 번만 등록하면 됩니다." onBack={onBack}>
      <MfaEnroll mfaToken={token} onDone={(r) => {
        if (r.access_token && r.refresh_token) void finish(r.access_token, r.refresh_token)
      }} />
    </StepCard>
  )
}
