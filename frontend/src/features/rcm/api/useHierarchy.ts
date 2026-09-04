// 상위 3계층 CRUD 훅 — useControls.ts의 통제 CRUD 훅과 동일 패턴 미러링.
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchProcessList,
  createProcess,
  updateProcessById,
  deleteProcess,
  fetchSubProcessList,
  createSubProcess,
  updateSubProcessById,
  deleteSubProcess,
  fetchRiskList,
  createRisk,
  updateRiskById,
  deleteRisk,
} from './hierarchyApi'
import type {
  ProcessItem,
  ProcessUpdatePayload,
  SubProcessItem,
  SubProcessUpdatePayload,
  RiskItem,
  RiskUpdatePayload,
} from '../types'
import type { ProcessItemDto, SubProcessItemDto, RiskItemDto } from './dto'
import { toProcessItems, toSubProcessItems, toRiskItems } from './controlsAdapter'
import { queryKeys } from '@/lib/queryKeys'
import { useActiveTenantId } from '@/features/auth/store'

// ── Process ────────────────────────────────────────────────

export function useProcessList() {
  const tenantId = useActiveTenantId()
  return useQuery<{ items: ProcessItemDto[] }, Error, { items: ProcessItem[] }>({
    queryKey: queryKeys.rcm.processes(tenantId),
    queryFn: fetchProcessList,
    select: toProcessItems,
    staleTime: 1000 * 30,
  })
}

export function useCreateProcess() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: createProcess,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.processes(tenantId) })
    },
  })
}

export function useUpdateProcess() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProcessUpdatePayload }) =>
      updateProcessById(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.processes(tenantId) })
    },
  })
}

export function useDeleteProcess() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: deleteProcess,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.processes(tenantId) })
      // 프로세스 삭제는 하위 계층 cascade 노출에도 영향을 준다(조회 시점 계산, ADR-0029 §2.2).
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.subProcessesAll(tenantId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.risksAll(tenantId) })
    },
  })
}

// ── SubProcess ─────────────────────────────────────────────

export function useSubProcessList() {
  const tenantId = useActiveTenantId()
  return useQuery<{ items: SubProcessItemDto[] }, Error, { items: SubProcessItem[] }>({
    queryKey: queryKeys.rcm.subProcessesAll(tenantId),
    queryFn: fetchSubProcessList,
    select: toSubProcessItems,
    staleTime: 1000 * 30,
  })
}

export function useCreateSubProcess() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: createSubProcess,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.subProcessesAll(tenantId) })
    },
  })
}

export function useUpdateSubProcess() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SubProcessUpdatePayload }) =>
      updateSubProcessById(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.subProcessesAll(tenantId) })
    },
  })
}

export function useDeleteSubProcess() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: deleteSubProcess,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.subProcessesAll(tenantId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.risksAll(tenantId) })
    },
  })
}

// ── Risk ───────────────────────────────────────────────────

export function useRiskList() {
  const tenantId = useActiveTenantId()
  return useQuery<{ items: RiskItemDto[] }, Error, { items: RiskItem[] }>({
    queryKey: queryKeys.rcm.risksAll(tenantId),
    queryFn: fetchRiskList,
    select: toRiskItems,
    staleTime: 1000 * 30,
  })
}

export function useCreateRisk() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: createRisk,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.risksAll(tenantId) })
    },
  })
}

export function useUpdateRisk() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RiskUpdatePayload }) =>
      updateRiskById(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.risksAll(tenantId) })
    },
  })
}

export function useDeleteRisk() {
  const queryClient = useQueryClient()
  const tenantId = useActiveTenantId()
  return useMutation({
    mutationFn: deleteRisk,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rcm.risksAll(tenantId) })
    },
  })
}
