import { useState, useEffect } from 'react'
import { mockControls } from './mockData'
import type { Control, ControlListResponse, ControlSearchParams } from '../types'

let controlsState: Control[] = [...mockControls]
const subscribers = new Set<() => void>()

function notify() {
  subscribers.forEach((fn) => fn())
}

// TODO: replace with axios.post('/api/rcm/controls', payload)
export function addControl(payload: Omit<Control, 'id' | 'created_at'>): Control {
  const newControl: Control = {
    ...payload,
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
  }
  controlsState = [newControl, ...controlsState]
  notify()
  return newControl
}

// TODO: replace with axios.patch(`/api/rcm/controls/${id}`, payload)
export function updateControl(id: string, payload: Partial<Control>): Control | null {
  const idx = controlsState.findIndex((c) => c.id === id)
  if (idx === -1) return null
  controlsState[idx] = { ...controlsState[idx], ...payload }
  notify()
  return controlsState[idx]
}

function applyFiltersAndSort(state: Control[], params: ControlSearchParams): ControlListResponse {
  let filtered = [...state]

  if (params.q) {
    const lower = params.q.toLowerCase()
    filtered = filtered.filter(
      (c) =>
        c.code.toLowerCase().includes(lower) ||
        c.name.toLowerCase().includes(lower) ||
        (c.owner_name ?? '').toLowerCase().includes(lower),
    )
  }

  if (params.process_code) {
    filtered = filtered.filter((c) => c.process_code === params.process_code)
  }

  if (params.sub_process_code) {
    filtered = filtered.filter((c) => c.sub_process_code === params.sub_process_code)
  }

  if (params.risk_level) {
    filtered = filtered.filter((c) => c.risk_level === params.risk_level)
  }

  if (params.frequency) {
    filtered = filtered.filter((c) => c.frequency === params.frequency)
  }

  if (params.is_key_control !== undefined) {
    filtered = filtered.filter((c) => c.is_key_control === params.is_key_control)
  }

  if (params.auto_manual) {
    filtered = filtered.filter((c) => c.auto_manual === params.auto_manual)
  }

  if (params.preventive_detective) {
    filtered = filtered.filter((c) => c.preventive_detective === params.preventive_detective)
  }

  if (params.assertion) {
    filtered = filtered.filter((c) => c.assertions.includes(params.assertion!))
  }

  const sortBy = params.sort_by ?? 'code'
  const sortOrder = params.sort_order ?? 'asc'
  filtered.sort((a, b) => {
    const av = a[sortBy as keyof Control] ?? ''
    const bv = b[sortBy as keyof Control] ?? ''
    const cmp = String(av).localeCompare(String(bv))
    return sortOrder === 'desc' ? -cmp : cmp
  })

  const skip = params.skip ?? 0
  const limit = params.limit ?? 20
  const total = filtered.length
  const items = filtered.slice(skip, skip + limit)

  return { items, total, skip, limit }
}

export function useControls(params: ControlSearchParams): {
  data: ControlListResponse
  isLoading: boolean
} {
  const [, setVersion] = useState(0)

  useEffect(() => {
    const sub = () => setVersion((v) => v + 1)
    subscribers.add(sub)
    return () => {
      subscribers.delete(sub)
    }
  }, [])

  // No useMemo: compute fresh every render so controlsState changes are always reflected
  const data = applyFiltersAndSort(controlsState, params)

  return { data, isLoading: false }
}
