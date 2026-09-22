import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useDeleteInfoItem,
  useEucFiles,
  useEucMeta,
  useInfoItems,
  useSaveInfoItem,
} from '@/features/euc/api/useEucIuc'
import { errorDetail, labelOf } from '@/features/euc/components/RiskBadge'
import type { InfoItem, InfoItemPayload } from '@/features/euc/types'
import { useControls } from '@/features/rcm/api/useControls'
import InfoItemDialog from '../components/InfoItemDialog'

/**
 * IUC 화면 — **정보 항목(통제) 중심**(ADR-0033 §2.1 정정). 통제가 쓰는 정보를 기술한다.
 *
 * 쓰기 권한은 통제 단위다(`icfr_manager` + 그 통제의 통제책임자·평가자). 서버가 행마다
 * `can_edit` 을, 목록에 `writable_control_ids` 를 준다 — 화면은 그것만 따른다.
 * 제외된 통제의 항목은 서버가 이미 뺐다(effective 제외).
 */
export default function IucPage() {
  const { data: meta } = useEucMeta()
  const { data, isLoading, isError } = useInfoItems()
  const { data: fileData } = useEucFiles()
  const { data: controlData } = useControls({ limit: 500, sort_by: 'code', sort_order: 'asc' })
  const save = useSaveInfoItem()
  const remove = useDeleteInfoItem()

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<InfoItem | null>(null)

  const writableControls = useMemo(() => {
    const allowed = new Set(data?.writable_control_ids ?? [])
    return (controlData?.items ?? [])
      .filter((c) => allowed.has(c.id))
      .map((c) => ({ id: c.id, code: c.code, name: c.name }))
  }, [data, controlData])

  const submit = async (body: InfoItemPayload) => {
    try {
      await save.mutateAsync({ id: editing?.id ?? null, body })
      toast.success(editing ? '정보 항목을 수정했습니다' : '정보 항목을 등록했습니다')
      setOpen(false)
    } catch (e) {
      toast.error(errorDetail(e, '저장하지 못했습니다'))
    }
  }

  const del = async (item: InfoItem) => {
    if (!window.confirm(`「${item.name}」 정보 항목을 삭제할까요?`)) return
    try {
      await remove.mutateAsync(item.id)
      toast.success('정보 항목을 삭제했습니다')
    } catch (e) {
      toast.error(errorDetail(e, '삭제하지 못했습니다'))
    }
  }

  if (isLoading || !meta) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…
      </div>
    )
  }
  if (isError || !data) return <div className="p-6 text-sm text-destructive">정보 항목을 불러오지 못했습니다</div>

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">IUC</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            통제에 쓰이는 정보(IPE)의 완전성·정확성. 정보 Type 이 EUC 인 항목은{' '}
            <Link to="/euc" className="underline">EUC 파일</Link>을 가리키며, 여기서 입력한 중요성이 파일 위험 등급의 재료가 됩니다.
          </p>
        </div>
        {writableControls.length > 0 && (
          <Button onClick={() => { setEditing(null); setOpen(true) }}>
            <Plus className="mr-1 h-4 w-4" /> 정보 항목 등록
          </Button>
        )}
      </div>

      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>통제</TableHead>
              <TableHead>정보</TableHead>
              <TableHead>정보 Type</TableHead>
              <TableHead>중요성</TableHead>
              <TableHead>EUC 파일</TableHead>
              <TableHead>시스템</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-sm text-muted-foreground">
                  등록된 정보 항목이 없습니다
                </TableCell>
              </TableRow>
            )}
            {data.items.map((i) => (
              <TableRow key={i.id}>
                <TableCell className="text-xs">
                  <div className="font-mono">{i.control_code}</div>
                  <div className="text-muted-foreground">{i.control_name}</div>
                </TableCell>
                <TableCell className="font-medium">{i.name}</TableCell>
                <TableCell className="text-sm">{labelOf(meta.info_type, i.info_type)}</TableCell>
                <TableCell className="text-sm">
                  {i.importance === null
                    ? <span className="text-muted-foreground">미평가</span>
                    : `${i.importance} · ${labelOf(meta.importance, i.importance)}`}
                </TableCell>
                <TableCell className="text-sm">{i.euc_file_name ?? <span className="text-muted-foreground">—</span>}</TableCell>
                <TableCell className="text-sm">{i.system_name ?? '—'}</TableCell>
                <TableCell>
                  {i.can_edit && (
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => { setEditing(i); setOpen(true) }}>수정</Button>
                      <Button variant="ghost" size="sm" onClick={() => del(i)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <InfoItemDialog
        open={open}
        onOpenChange={setOpen}
        target={editing}
        meta={meta}
        controls={writableControls}
        files={fileData?.items ?? []}
        onSubmit={submit}
        pending={save.isPending}
      />
    </div>
  )
}
