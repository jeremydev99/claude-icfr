import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Loader2 } from 'lucide-react'
import { fetchControls } from '@/features/rcm/api/controlsApi'
import type { Control } from '@/features/rcm/types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (control: Control) => void
}

export default function ControlSelector({ open, onOpenChange, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [controls, setControls] = useState<Control[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    if (!open) return
    setLoading(true)
    fetchControls({ q: debouncedQuery || undefined, skip: 0, limit: 20, sort_by: 'code', sort_order: 'asc' })
      .then((res) => setControls(res.items))
      .catch(() => setControls([]))
      .finally(() => setLoading(false))
  }, [open, debouncedQuery])

  const handleSelect = (control: Control) => {
    onSelect(control)
    onOpenChange(false)
    setQuery('')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>통제 선택</DialogTitle>
        </DialogHeader>

        <Input
          placeholder="통제 코드 또는 이름으로 검색"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />

        <div className="mt-2 max-h-80 overflow-y-auto space-y-2">
          {loading && (
            <div className="flex justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
          {!loading && controls.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              검색 결과가 없습니다
            </p>
          )}
          {!loading &&
            controls.map((ctrl) => (
              <button
                key={ctrl.id}
                onClick={() => handleSelect(ctrl)}
                className="w-full rounded-md border p-3 text-left hover:bg-accent transition-colors"
              >
                <p className="font-medium text-sm">{ctrl.code}</p>
                <p className="text-sm text-muted-foreground">{ctrl.name}</p>
                {ctrl.process_code && (
                  <p className="text-xs text-muted-foreground mt-1">
                    프로세스: {ctrl.process_code}
                  </p>
                )}
              </button>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
