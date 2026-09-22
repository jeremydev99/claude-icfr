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
import type { EucFile, EucFilePayload, EucMeta } from '../types'

// Select 는 빈 문자열 값을 쓸 수 없다 — 미평가·미지정 선택지용 센티널
const UNSET = '__none__'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  target: EucFile | null
  meta: EucMeta
  onSubmit: (body: EucFilePayload) => Promise<void>
  pending: boolean
}

export default function EucFileDialog({ open, onOpenChange, target, meta, onSubmit, pending }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [complexity, setComplexity] = useState(UNSET)
  const [frequency, setFrequency] = useState(UNSET)
  const [macro, setMacro] = useState(UNSET)
  const [storage, setStorage] = useState('')
  const [dept, setDept] = useState('')
  const [manager, setManager] = useState('')

  useEffect(() => {
    if (!open) return
    setName(target?.name ?? '')
    setDescription(target?.description ?? '')
    setComplexity(target?.complexity ?? UNSET)
    setFrequency(target?.change_frequency ?? UNSET)
    setMacro(target?.has_macro === null || target?.has_macro === undefined ? UNSET : String(target.has_macro))
    setStorage(target?.storage_path ?? '')
    setDept(target?.managing_department ?? '')
    setManager(target?.manager_name ?? '')
  }, [open, target])

  const orNull = (v: string) => (v === UNSET || v.trim() === '' ? null : v.trim())

  const submit = () =>
    onSubmit({
      name: name.trim(),
      description: orNull(description),
      complexity: orNull(complexity),
      change_frequency: orNull(frequency),
      has_macro: macro === UNSET ? null : macro === 'true',
      storage_path: orNull(storage),
      managing_department: orNull(dept),
      manager_name: orNull(manager),
    })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{target ? 'EUC 파일 수정' : 'EUC 파일 등록'}</DialogTitle>
          <DialogDescription>
            여기서 입력하는 값은 <strong>복잡도</strong>뿐입니다. 중요성은 정보 항목(IUC)에서 입력하고,
            파일 중요성·위험 등급·통제 식별 여부는 시스템이 산출합니다.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="euc-name">파일명</Label>
            <Input id="euc-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="euc-desc">설명</Label>
            <Textarea id="euc-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>복잡도</Label>
              <Select value={complexity} onValueChange={setComplexity}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNSET}>미평가</SelectItem>
                  {meta.complexity.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>파일변경주기</Label>
              <Select value={frequency} onValueChange={setFrequency}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNSET}>미지정</SelectItem>
                  {meta.change_frequency.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>매크로 포함</Label>
              <Select value={macro} onValueChange={setMacro}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNSET}>미확인</SelectItem>
                  <SelectItem value="true">포함</SelectItem>
                  <SelectItem value="false">없음</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="euc-dept">관리부서</Label>
              <Input id="euc-dept" value={dept} onChange={(e) => setDept(e.target.value)} maxLength={100} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="euc-mgr">관리자</Label>
              <Input id="euc-mgr" value={manager} onChange={(e) => setManager(e.target.value)} maxLength={100} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="euc-path">저장소</Label>
              <Input id="euc-path" value={storage} onChange={(e) => setStorage(e.target.value)} maxLength={500} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            매크로가 없다는 것만으로 복잡도를 정하지 않습니다 — 「매크로·링크·모델」에는 외부 링크와 모델도 포함됩니다.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>취소</Button>
          <Button onClick={submit} disabled={pending || name.trim() === ''}>{target ? '수정' : '등록'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
