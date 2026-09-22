import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { AlertTriangle, Loader2, Plus, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useDeleteEucFile, useEucFiles, useEucMeta, useSaveEucFile } from '../api/useEucIuc'
import EucFileDialog from '../components/EucFileDialog'
import { RiskBadge, errorDetail, labelOf } from '../components/RiskBadge'
import type { EucFile, EucFilePayload } from '../types'

/**
 * EUC 화면 — **파일 중심**(ADR-0033 §2.1 정정). 파일 하나에 참조 통제가 여럿 붙을 수 있다.
 *
 * 쓰기 가능 여부는 **서버가 행마다 `can_edit` 로 준다** — 파일 쓰기 권한은 "그 파일을 참조하는
 * 통제의 통제책임자"라서 화면이 역할만 보고 판정할 수 없다. `can_write` 로도 판정하지 않는다
 * (그건 external_auditor 판정이다).
 */
export default function EucPage() {
  const { data: meta } = useEucMeta()
  const { data, isLoading, isError } = useEucFiles()
  const save = useSaveEucFile()
  const remove = useDeleteEucFile()

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<EucFile | null>(null)

  const submit = async (body: EucFilePayload) => {
    try {
      await save.mutateAsync({ id: editing?.id ?? null, body })
      toast.success(editing ? 'EUC 파일을 수정했습니다' : 'EUC 파일을 등록했습니다')
      setOpen(false)
    } catch (e) {
      toast.error(errorDetail(e, '저장하지 못했습니다'))
    }
  }

  const del = async (f: EucFile) => {
    if (!window.confirm(`「${f.name}」을 삭제할까요? 정보 항목이 참조 중이면 삭제되지 않습니다.`)) return
    try {
      await remove.mutateAsync(f.id)
      toast.success('EUC 파일을 삭제했습니다')
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
  if (isError || !data) return <div className="p-6 text-sm text-destructive">EUC 파일을 불러오지 못했습니다</div>

  const threshold = labelOf(meta.risk_grade, meta.identification_threshold)

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">EUC</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            ERP 밖에서 현업이 만든 엑셀·매크로 등 — IT부서 통제를 받지 않는 도구입니다.
            위험 등급이 <strong>{threshold}</strong> 이상이면 EUC 통제 식별 대상입니다.
            중요성은 <Link to="/iuc" className="underline">IUC</Link>의 정보 항목에서 입력합니다.
          </p>
        </div>
        {data.can_create && (
          <Button onClick={() => { setEditing(null); setOpen(true) }}>
            <Plus className="mr-1 h-4 w-4" /> 파일 등록
          </Button>
        )}
      </div>

      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>파일명</TableHead>
              <TableHead>참조 통제</TableHead>
              <TableHead>복잡도</TableHead>
              <TableHead>파일 중요성</TableHead>
              <TableHead>위험 등급</TableHead>
              <TableHead>원천 참고값</TableHead>
              <TableHead>통제 식별</TableHead>
              <TableHead>변경주기</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="text-center text-sm text-muted-foreground">
                  등록된 EUC 파일이 없습니다
                </TableCell>
              </TableRow>
            )}
            {data.items.map((f) => (
              <TableRow key={f.id}>
                <TableCell className="font-medium">
                  {f.name}
                  {f.description && (
                    <p className="line-clamp-1 text-xs font-normal text-muted-foreground" title={f.description}>
                      {f.description}
                    </p>
                  )}
                </TableCell>
                <TableCell className="text-xs">
                  {f.controls.length === 0 ? (
                    // 참조 통제가 전부 제외되거나 아직 연결 전 — 파일은 독립 대상이라 지우지 않는다
                    <span className="text-muted-foreground">참조 통제 0건</span>
                  ) : (
                    f.controls.map((c) => (
                      <div key={c.id} className="font-mono" title={c.name}>{c.code}</div>
                    ))
                  )}
                </TableCell>
                <TableCell className="text-sm">
                  {f.complexity === null
                    ? <span className="text-muted-foreground">미평가</span>
                    : labelOf(meta.complexity, f.complexity)}
                </TableCell>
                <TableCell className="text-sm">
                  {f.importance === null
                    ? <span className="text-muted-foreground">미평가</span>
                    : labelOf(meta.importance, f.importance)}
                </TableCell>
                <TableCell><RiskBadge grade={f.risk_grade} options={meta.risk_grade} /></TableCell>
                <TableCell className="text-xs">
                  <span className="text-muted-foreground">{labelOf(meta.risk_grade, f.source_risk_rating)}</span>
                  {f.source_mismatch && (
                    // 원천 양식이 적은 값과 우리가 산출한 값이 다르다 — 어느 쪽이 맞는지 검토할 신호
                    <div className="mt-0.5 flex items-center gap-1 text-amber-700" title="원천 양식의 위험평가와 산출 등급이 다릅니다">
                      <AlertTriangle className="h-3 w-3" /> 산출값과 다름
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  {f.identified === null
                    ? <span className="text-xs text-muted-foreground">판정 불가</span>
                    : f.identified
                      ? <Badge>식별 대상</Badge>
                      : <span className="text-xs text-muted-foreground">해당 없음</span>}
                </TableCell>
                <TableCell className="text-sm">{labelOf(meta.change_frequency, f.change_frequency)}</TableCell>
                <TableCell>
                  {f.can_edit && (
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => { setEditing(f); setOpen(true) }}>수정</Button>
                      <Button variant="ghost" size="sm" onClick={() => del(f)}>
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

      <p className="text-xs text-muted-foreground">
        「미평가」는 복잡도 또는 중요성이 아직 입력되지 않은 상태입니다. 원천 양식이 Low 로 적어 두었어도
        평가하지 않은 것과 평가해서 낮은 것은 다르므로 따로 표시합니다.
      </p>

      <EucFileDialog
        open={open}
        onOpenChange={setOpen}
        target={editing}
        meta={meta}
        onSubmit={submit}
        pending={save.isPending}
      />
    </div>
  )
}
