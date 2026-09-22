import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { EucFile, EucMeta, InfoItem, InfoItemPayload } from '@/features/euc/types'

const UNSET = '__none__'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  target: InfoItem | null
  meta: EucMeta
  /** 정보 항목을 붙일 수 있는 통제만 — 서버가 준 `writable_control_ids` 로 좁힌 목록 */
  controls: Array<{ id: string; code: string; name: string }>
  files: EucFile[]
  onSubmit: (body: InfoItemPayload) => Promise<void>
  pending: boolean
}

export default function InfoItemDialog({
  open, onOpenChange, target, meta, controls, files, onSubmit, pending,
}: Props) {
  const [controlId, setControlId] = useState('')
  const [name, setName] = useState('')
  const [infoType, setInfoType] = useState('')
  const [importance, setImportance] = useState(UNSET)
  const [fileId, setFileId] = useState(UNSET)
  const [system, setSystem] = useState('')
  const [sourceData, setSourceData] = useState('')
  const [logic, setLogic] = useState('')

  useEffect(() => {
    if (!open) return
    setControlId(target?.control_id ?? '')
    setName(target?.name ?? '')
    setInfoType(target?.info_type ?? meta.info_type[0]?.value ?? '')
    setImportance(target?.importance ?? UNSET)
    setFileId(target?.euc_file_id ?? UNSET)
    setSystem(target?.system_name ?? '')
    setSourceData(target?.source_data ?? '')
    setLogic(target?.report_logic ?? '')
  }, [open, target, meta])

  const orNull = (v: string) => (v === UNSET || v.trim() === '' ? null : v.trim())

  const submit = () => {
    const body: InfoItemPayload = {
      name: name.trim(),
      info_type: infoType,
      importance: orNull(importance),
      euc_file_id: orNull(fileId),
      system_name: orNull(system),
      source_data: orNull(sourceData),
      report_logic: orNull(logic),
    }
    // 통제는 생성 때만 정한다 — 수정으로 다른 통제에 옮기면 권한 판정 대상이 바뀐다
    if (!target) body.control_id = controlId
    return onSubmit(body)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{target ? '정보 항목 수정' : '정보 항목 등록'}</DialogTitle>
          <DialogDescription>
            <strong>중요성은 여기서만 입력합니다.</strong> 같은 EUC 파일을 여러 통제가 쓰면 파일 중요성은
            그중 가장 높은 값으로 산출됩니다.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 py-2">
          <div className="space-y-1.5">
            <Label>통제</Label>
            {target ? (
              <p className="text-sm"><span className="font-mono">{target.control_code}</span> {target.control_name}</p>
            ) : (
              <Select value={controlId} onValueChange={setControlId}>
                <SelectTrigger><SelectValue placeholder="선택" /></SelectTrigger>
                <SelectContent>
                  {controls.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.code} {c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="info-name">정보명</Label>
            <Input id="info-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>정보 Type</Label>
              <Select value={infoType} onValueChange={setInfoType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {meta.info_type.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>중요성</Label>
              <Select value={importance} onValueChange={setImportance}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNSET}>미평가</SelectItem>
                  {meta.importance.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.value} · {o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>EUC 파일</Label>
            <Select value={fileId} onValueChange={setFileId}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={UNSET}>연결 안 함</SelectItem>
                {files.map((f) => (
                  <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="info-system">시스템/어플리케이션</Label>
            <Input id="info-system" value={system} onChange={(e) => setSystem(e.target.value)} maxLength={100} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="info-source">기초정보(Source Data)</Label>
            <Textarea id="info-source" value={sourceData} onChange={(e) => setSourceData(e.target.value)} rows={2} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="info-logic">Report Logic</Label>
            <Textarea id="info-logic" value={logic} onChange={(e) => setLogic(e.target.value)} rows={2} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>취소</Button>
          <Button onClick={submit} disabled={pending || name.trim() === '' || (!target && !controlId)}>
            {target ? '수정' : '등록'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
