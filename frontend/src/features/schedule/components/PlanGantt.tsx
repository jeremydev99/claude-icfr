import { useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import { TOTAL_COLUMNS, dateEndX, dateToX, dragDates, xToDate, type DragMode, type MonthColumn } from '../schedule.pure'

export interface GanttBar {
  id: string
  label: string
  start: string            // YYYY-MM-DD
  end: string
  barClass: string
  title?: string
  editable?: boolean
  /** 승인본 대비 — 편집 모드에서 바뀐 막대 표시 */
  mark?: 'changed' | 'added'
}

const GRID = { gridTemplateColumns: `minmax(10rem, 14rem) repeat(${TOTAL_COLUMNS}, minmax(0, 1fr))` }
const short = (d: string) => d.slice(5).replace('-', '.')

/**
 * 연간 일정 간트(13.9-100) — 일 단위 막대. 편집 가능한 막대는 가운데를 끌어 옮기고, 양 끝을 끌어 시작·종료일을 바꾼다.
 * 놓는 순간 `onCommit` — 저장은 작성 중 판에만 되고, 화면 기본 보기(승인본)는 결재 승인 때 바뀐다.
 */
export default function PlanGantt({ fy, startMonth, columns, nowOffset, rows, onCommit, section }: {
  fy: number
  startMonth: number
  columns: MonthColumn[]
  nowOffset: number | null
  rows: GanttBar[]
  onCommit?: (id: string, start: string, end: string) => void
  /** 아래쪽 별도 구간(평가 회차 등) — 제목과 막대 */
  section?: { title: string; rows: GanttBar[] }
}) {
  const [drag, setDrag] = useState<null | { id: string; mode: DragMode; grab: string; start: string; end: string; cur: { start: string; end: string } }>(null)
  const tracks = useRef(new Map<string, HTMLDivElement>())

  const dateAt = (id: string, clientX: number) => {
    const el = tracks.current.get(id)
    if (!el) return null
    const r = el.getBoundingClientRect()
    return xToDate(fy, startMonth, (clientX - r.left) / r.width)
  }

  const down = (b: GanttBar, mode: DragMode) => (e: React.PointerEvent) => {
    if (!b.editable || !onCommit) return
    e.preventDefault()
    e.stopPropagation()
    const grab = dateAt(b.id, e.clientX)
    if (!grab) return
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    setDrag({ id: b.id, mode, grab, start: b.start, end: b.end, cur: { start: b.start, end: b.end } })
  }
  const move = (e: React.PointerEvent) => {
    if (!drag) return
    const now = dateAt(drag.id, e.clientX)
    if (now) setDrag({ ...drag, cur: dragDates(drag.mode, drag.start, drag.end, drag.grab, now) })
  }
  const up = () => {
    if (!drag) return
    const { id, start, end, cur } = drag
    setDrag(null)
    if (cur.start !== start || cur.end !== end) onCommit?.(id, cur.start, cur.end)
  }

  const row = (b: GanttBar) => {
    const live = drag?.id === b.id ? drag.cur : { start: b.start, end: b.end }
    const left = dateToX(fy, startMonth, live.start)
    const width = Math.max(dateEndX(fy, startMonth, live.end) - left, 0.004)
    const can = b.editable && !!onCommit
    return (
      <div key={b.id} className="contents">
        <div className="flex items-center gap-1.5 truncate pr-2 leading-6" title={b.label}>
          {b.mark && <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', b.mark === 'added' ? 'bg-emerald-500' : 'bg-amber-500')}
            title={b.mark === 'added' ? '승인본에 없는 새 일정' : '승인본과 기간·제목이 다름'} />}
          <span className="truncate">{b.label}</span>
        </div>
        <div ref={(el) => { if (el) tracks.current.set(b.id, el); else tracks.current.delete(b.id) }}
          className="relative h-6" style={{ gridColumn: `2 / span ${TOTAL_COLUMNS}` }}>
          {nowOffset != null && (
            <div className="pointer-events-none absolute inset-y-0 bg-primary/10"
              style={{ left: `${((nowOffset - 1) / TOTAL_COLUMNS) * 100}%`, width: `${100 / TOTAL_COLUMNS}%` }} />
          )}
          <div
            className={cn('group absolute top-1 h-4 rounded', b.barClass, can && 'cursor-grab touch-none ring-offset-1 hover:ring-2 hover:ring-primary/40',
              drag?.id === b.id && 'cursor-grabbing ring-2 ring-primary', b.mark && 'outline outline-2 outline-offset-1 outline-amber-400/70')}
            style={{ left: `${left * 100}%`, width: `${width * 100}%` }}
            title={can ? `${b.title ?? b.label}\n${live.start} ~ ${live.end}\n가운데를 끌어 옮기고, 양 끝을 끌어 늘이거나 줄입니다` : (b.title ?? `${live.start} ~ ${live.end}`)}
            onPointerDown={down(b, 'move')} onPointerMove={move} onPointerUp={up} onPointerCancel={() => setDrag(null)}
          >
            {can && (
              <>
                <span className="absolute inset-y-0 -left-1 w-2.5 cursor-ew-resize rounded-l bg-black/0 group-hover:bg-black/20"
                  onPointerDown={down(b, 'start')} onPointerMove={move} onPointerUp={up} />
                <span className="absolute inset-y-0 -right-1 w-2.5 cursor-ew-resize rounded-r bg-black/0 group-hover:bg-black/20"
                  onPointerDown={down(b, 'end')} onPointerMove={move} onPointerUp={up} />
              </>
            )}
          </div>
          {drag?.id === b.id && (
            <div className="pointer-events-none absolute -top-5 z-10 whitespace-nowrap rounded bg-foreground px-1.5 py-0.5 text-[10px] font-medium text-background"
              style={{ left: `${left * 100}%` }}>
              {short(live.start)} ~ {short(live.end)}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={cn('grid gap-y-1 text-xs', drag && 'select-none')} style={GRID}>
      <div />
      {columns.map((col) => (
        <div key={col.offset}
          className={`py-1 text-center ${col.nextYear ? 'bg-muted/60' : ''} ${col.offset === nowOffset ? 'rounded-t bg-primary/15 font-semibold text-primary' : 'text-muted-foreground'}`}
          title={`${col.year}년 ${col.month}월${col.nextYear ? ' (익년)' : ''}`}>
          {col.month === 1 || col.offset === 1 ? <div className="text-[10px]">{col.year}</div> : <div className="text-[10px]">&nbsp;</div>}
          {col.label}
        </div>
      ))}
      {rows.map(row)}
      {section && section.rows.length > 0 && (
        <>
          <div className="col-span-full mt-2 border-t pt-2 text-xs font-medium text-muted-foreground">{section.title}</div>
          {section.rows.map(row)}
        </>
      )}
    </div>
  )
}
