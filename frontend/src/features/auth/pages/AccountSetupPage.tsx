import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, Loader2, ShieldCheck } from 'lucide-react'
import apiClient from '@/lib/axios'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { errDetail } from '../mfa/api'
import { PASSWORD_RULE_TEXT, passwordPolicyError } from '../password.pure'

interface SetupInfo {
  email: string
  display_name: string
  purpose: 'invite' | 'reset'
  expires_at: string
}

/**
 * 직원 계정 설정(ADR-0041) — 로그인 전 공개 화면. 관리자가 전달한 링크에서 본인이 비밀번호를 정한다.
 * 관리자는 비밀번호를 모른다. 링크는 72시간·한 번만. 끝나면 로그인 화면에서 평소처럼 로그인(2단계 인증은 그때).
 */
export default function AccountSetupPage() {
  const { token = '' } = useParams()
  const info = useQuery({
    queryKey: ['account-setup', token],
    queryFn: async () => (await apiClient.get<SetupInfo>(`/api/account-setup/${token}`)).data,
    retry: false,
  })
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const save = useMutation({
    mutationFn: async () => (await apiClient.post(`/api/account-setup/${token}`, { password: pw })).data,
  })

  if (info.isLoading) return <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
  if (info.isError || !info.data) {
    return (
      <Shell title="링크를 열 수 없습니다" desc={errDetail(info.error) ?? '유효하지 않은 링크입니다'}>
        <p className="text-sm text-muted-foreground">설정 링크는 72시간 동안 한 번만 쓸 수 있고, 새로 발급하면 이전 링크는 취소됩니다. 관리자에게 새 링크를 요청하세요.</p>
        <Button asChild variant="outline" className="w-full"><Link to="/login">로그인 화면으로</Link></Button>
      </Shell>
    )
  }
  const d = info.data
  const invite = d.purpose === 'invite'

  if (save.isSuccess) {
    return (
      <Shell title="비밀번호를 정했습니다" desc="이제 새 비밀번호로 로그인하세요.">
        <p className="flex items-center gap-2 rounded-lg border bg-muted/40 p-3 text-sm">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />{d.email}
        </p>
        <Button asChild className="h-11 w-full"><Link to="/login">로그인</Link></Button>
      </Shell>
    )
  }

  const policy = passwordPolicyError(pw)
  const mismatch = pw2.length > 0 && pw !== pw2
  const ready = pw.length > 0 && !policy && pw === pw2

  return (
    <Shell title={invite ? 'ICFR 계정 시작' : '비밀번호 재설정'}
      desc={invite ? `${d.display_name}님, 본인만 아는 비밀번호를 정하면 계정이 시작됩니다.`
        : `${d.display_name}님, 새 비밀번호를 정하세요. 정하기 전까지는 기존 비밀번호가 그대로입니다.`}>
      <p className="flex items-center gap-2 rounded-lg border bg-muted/40 p-3 text-sm">
        <ShieldCheck className="h-4 w-4 shrink-0 text-muted-foreground" />{d.email}
      </p>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
        <div className="space-y-2">
          <Label htmlFor="setup-pw">새 비밀번호 <span className="font-normal text-muted-foreground">({PASSWORD_RULE_TEXT})</span></Label>
          <Input id="setup-pw" type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" autoFocus />
          {pw.length > 0 && policy && <p className="text-xs text-destructive">{policy}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="setup-pw2">비밀번호 확인</Label>
          <Input id="setup-pw2" type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" />
          {mismatch && <p className="text-xs text-destructive">비밀번호가 서로 다릅니다</p>}
        </div>
        <p className="text-xs text-muted-foreground">관리자도 이 비밀번호를 알 수 없습니다. 이 링크는 {new Date(d.expires_at).toLocaleString('ko-KR')}까지, 한 번만 쓸 수 있습니다.</p>
        {save.isError && <p className="text-center text-sm text-destructive" role="alert">{errDetail(save.error) ?? '저장하지 못했습니다'}</p>}
        <Button type="submit" className="h-11 w-full" disabled={!ready || save.isPending}>
          {save.isPending ? '처리 중…' : '비밀번호 정하기'}
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
