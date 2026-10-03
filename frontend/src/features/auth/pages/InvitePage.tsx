import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Building2, CalendarRange, Loader2, ShieldCheck } from 'lucide-react'
import apiClient from '@/lib/axios'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useFinishLogin } from '../hooks/useAuth'
import MfaEnroll from '../mfa/MfaEnroll'
import { errDetail } from '../mfa/api'
import { passwordPolicyError } from '../password.pure'

interface InviteInfo {
  email: string
  display_name: string
  organization: string
  type_label: string
  company: string
  valid_from: string
  valid_until: string
  existing_account: boolean
}

/**
 * 외부 사용자 초대 수락(ADR-0039 §2.2) — 로그인 전 공개 화면.
 * 비밀번호 설정(기존 계정이면 확인) + 비밀유지 동의 → 2단계 인증 등록 → 로그인 완료.
 */
export default function InvitePage() {
  const { token = '' } = useParams()
  const finish = useFinishLogin()
  const info = useQuery({
    queryKey: ['invite', token],
    queryFn: async () => (await apiClient.get<InviteInfo>(`/api/invite/${token}`)).data,
    retry: false,
  })
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [agree, setAgree] = useState(false)
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [alreadyMfa, setAlreadyMfa] = useState(false)

  const accept = useMutation({
    mutationFn: async () =>
      (await apiClient.post<{ mfa_token: string | null; mfa_required: boolean }>(`/api/invite/${token}/accept`,
        { password: pw, confidentiality: agree })).data,
    onSuccess: (r) => {
      if (r.mfa_token) setMfaToken(r.mfa_token)
      else if (r.mfa_required) setAlreadyMfa(true)
    },
  })

  if (info.isLoading) {
    return <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
  }
  if (info.isError || !info.data) {
    return (
      <Shell title="초대 링크를 열 수 없습니다" desc={errDetail(info.error) ?? '유효하지 않은 링크입니다'}>
        <p className="text-sm text-muted-foreground">초대 링크는 72시간 동안 한 번만 쓸 수 있습니다. 초대한 회사 담당자에게 다시 요청하세요.</p>
        <Button asChild variant="outline" className="w-full"><Link to="/login">로그인 화면으로</Link></Button>
      </Shell>
    )
  }
  const d = info.data

  if (alreadyMfa) {
    return (
      <Shell title="접근이 추가됐습니다" desc={`${d.company} 접근 권한이 기존 계정에 추가됐습니다.`}>
        <Button asChild className="h-11 w-full"><Link to="/login">로그인</Link></Button>
      </Shell>
    )
  }
  if (mfaToken) {
    return (
      <Shell title="2단계 인증 등록" desc="외부 사용자는 2단계 인증이 필수입니다. 처음 한 번만 등록하면 됩니다.">
        <MfaEnroll mfaToken={mfaToken} onDone={(r) => {
          if (r.access_token && r.refresh_token) void finish(r.access_token, r.refresh_token)
        }} />
      </Shell>
    )
  }

  const policy = d.existing_account ? null : passwordPolicyError(pw)
  const mismatch = !d.existing_account && pw2.length > 0 && pw !== pw2
  const ready = agree && pw.length > 0 && !policy && (d.existing_account || pw === pw2)

  return (
    <Shell title={`${d.company} 초대`} desc={`${d.display_name}님, ICFR 시스템에 초대되었습니다.`}>
      <dl className="space-y-2 rounded-lg border bg-muted/40 p-3 text-sm">
        <div className="flex gap-2"><Building2 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <dd><b>{d.organization}</b> · {d.type_label}</dd></div>
        <div className="flex gap-2"><CalendarRange className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <dd>접근 기간 {d.valid_from} ~ {d.valid_until}</dd></div>
        <div className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <dd>{d.email}</dd></div>
      </dl>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); accept.mutate() }}>
        <div className="space-y-2">
          <Label htmlFor="inv-pw">{d.existing_account ? '기존 계정 비밀번호' : '비밀번호 설정'}</Label>
          <Input id="inv-pw" type="password" value={pw} onChange={(e) => setPw(e.target.value)}
            autoComplete={d.existing_account ? 'current-password' : 'new-password'} />
          {d.existing_account
            ? <p className="text-xs text-muted-foreground">이 이메일로 이미 계정이 있습니다. 비밀번호를 확인하면 접근 권한이 추가됩니다.</p>
            : pw.length > 0 && policy && <p className="text-xs text-destructive">{policy}</p>}
        </div>
        {!d.existing_account && (
          <div className="space-y-2">
            <Label htmlFor="inv-pw2">비밀번호 확인</Label>
            <Input id="inv-pw2" type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" />
            {mismatch && <p className="text-xs text-destructive">비밀번호가 서로 다릅니다</p>}
          </div>
        )}
        <label className="flex items-start gap-2.5 rounded-lg border p-3 text-sm leading-relaxed">
          <Checkbox checked={agree} onCheckedChange={(v) => setAgree(v === true)} className="mt-0.5" />
          <span>
            이 시스템에서 보는 회사 정보는 <b>업무 목적으로만</b> 사용하고 외부에 공개하지 않습니다(비밀유지 의무).
            동의 시각이 기록됩니다.
          </span>
        </label>
        {accept.isError && <p className="text-center text-sm text-destructive" role="alert">{errDetail(accept.error) ?? '수락하지 못했습니다'}</p>}
        <Button type="submit" className="h-11 w-full" disabled={!ready || accept.isPending}>
          {accept.isPending ? '처리 중…' : '수락하고 계속'}
        </Button>
      </form>
    </Shell>
  )
}

function Shell({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <Card className="w-full max-w-[460px] border-border/70 shadow-lift">
      <CardHeader className="space-y-1.5 pb-4">
        <CardTitle className="text-2xl font-bold tracking-tight">{title}</CardTitle>
        <CardDescription>{desc}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  )
}
