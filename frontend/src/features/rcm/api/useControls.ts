import { useMemo } from 'react'
import { mockControls } from './mockData'
import type { Control, ControlListResponse, ControlSearchParams } from '../types'

// TODO: replace with axios — swap this function body to:
//   const { data } = useQuery({ queryKey: ['controls', params], queryFn: () =>
//     axios.get<ControlListResponse>('/api/rcm/controls/search', { params }).then(r => r.data) })
export function useControls(params: ControlSearchParams): {
  data: ControlListResponse
  isLoading: boolean
} {
  const data = useMemo(() => {
    let filtered: Control[] = [...mockControls]

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
  }, [params])

  return { data, isLoading: false }
}
