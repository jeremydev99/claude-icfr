import { useState } from 'react'
import { toast } from 'sonner'
import { Crown, Plus, ShieldCheck, Scale, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useUsers } from '@/features/users/api/useUsers'
import { useCreateUserRole, useDeleteUserRole, useUserRoles } from '@/features/users/api/useUserRoles'

/** 법정 직책 — 테넌트 역할(user_roles) 중 보고서 서명·법정 보고 주체가 되는 셋. 보고서 기본 정보의 기본값이 된다 */
export const OFFICER_ROLES = [
  { role: 'ceo', label: '대표이사', icon: Crown, note: '운영실태보고서 서명 · 이사회·주주총회 보고 주체' },
  { role: 'icfr_manager', label: '내부회계관리자', icon: ShieldCheck, note: '마스터관리자와 같은 역할 · 운영실태보고서 공동 서명' },
  { role: 'auditor', label: '감사(감사위원회)', icon: Scale, note: '상근감사·감사위원 — 평가보고서 작성·이사회 보고' },
] as const

const err = (e: unknown, f: string) => (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? f

/**
 * 역할 배정 화면 상단 — 대표이사·내부회계관리자·감사를 사람에게 지정한다(2026-10-06 마스터).
 * 통제 단위 역할(통제책임자 등)과 달리 회사 단위 역할이라 `user_roles` 에 저장한다. 지정 권한은 서버가 판정(마스터관리자).
 */
export default function OfficerRoles({ canEdit }: { canEdit: boolean }) {
  const { data: roleData } = useUserRoles({ limit: 500 })
  const { data: userData } = useUsers({ limit: 500 })
  const create = useCreateUserRole()
  const del = useDeleteUserRole()
  const [pick, setPick] = useState<Record<string, string>>({})
  const names = new Map((userData?.items ?? []).map((u) => [u.id, u.display_name]))
  const roles = roleData?.items ?? []

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {OFFICER_ROLES.map((o) => {
        const holders = roles.filter((r) => r.role_name === o.role)
        return (
          <div key={o.role} className="rounded-xl border bg-card p-4 shadow-card">
            <div className="flex items-center gap-2">
              <o.icon className="h-4 w-4 text-primary" />
              <span className="font-semibold">{o.label}</span>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">{o.note}</p>
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {holders.length === 0 && <li className="text-sm text-amber-700 dark:text-amber-300">지정되지 않음</li>}
              {holders.map((h) => (
                <li key={h.id} className="inline-flex items-center gap-1 rounded-full border bg-muted/50 px-2.5 py-0.5 text-sm">
                  {names.get(h.user_id) ?? '(사용자)'}
                  {canEdit && (
                    <button type="button" aria-label={`${o.label} 지정 해제`} className="text-muted-foreground hover:text-destructive"
                      onClick={() => {
                        if (!window.confirm(`${names.get(h.user_id)}의 ${o.label} 지정을 해제할까요?`)) return
                        del.mutate(h.id, { onSuccess: () => toast.success('해제했습니다'), onError: (e) => toast.error(err(e, '해제하지 못했습니다')) })
                      }}><X className="h-3.5 w-3.5" /></button>
                  )}
                </li>
              ))}
            </ul>
            {canEdit && (
              <div className="mt-3 flex gap-2">
                <select value={pick[o.role] ?? ''} onChange={(e) => setPick({ ...pick, [o.role]: e.target.value })}
                  className="h-9 min-w-0 flex-1 rounded-md border bg-background px-2 py-0 text-sm">
                  <option value="">사람 선택</option>
                  {(userData?.items ?? []).filter((u) => !holders.some((h) => h.user_id === u.id))
                    .map((u) => <option key={u.id} value={u.id}>{u.display_name}</option>)}
                </select>
                <Button size="sm" disabled={!pick[o.role] || create.isPending} onClick={() => create.mutate(
                  { user_id: pick[o.role], role_name: o.role },
                  { onSuccess: () => { toast.success(`${o.label}로 지정했습니다`); setPick({ ...pick, [o.role]: '' }) },
                    onError: (e) => toast.error(err(e, '지정하지 못했습니다')) },
                )}><Plus className="mr-1 h-3.5 w-3.5" />지정</Button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** 보고서 기본값용 — 역할별 지정된 사람 이름(여럿이면 쉼표) */
export function useOfficerNames(): Record<string, string> {
  const { data: roleData } = useUserRoles({ limit: 500 })
  const { data: userData } = useUsers({ limit: 500 })
  const names = new Map((userData?.items ?? []).map((u) => [u.id, u.display_name]))
  const out: Record<string, string> = {}
  for (const o of OFFICER_ROLES) {
    const list = (roleData?.items ?? []).filter((r) => r.role_name === o.role).map((r) => names.get(r.user_id)).filter(Boolean)
    if (list.length) out[o.role] = list.join(', ')
  }
  return out
}
