import { useMutation } from '@tanstack/react-query'
import apiClient from '@/lib/axios'

export interface MfaSetup {
  secret: string
  otpauth_uri: string
  qr_svg: string
}

export interface MfaEnableResult {
  recovery_codes: string[]
  access_token: string | null
  refresh_token: string | null
}

/** 등록 시작 — 로그인 중이면 `mfaToken`, 로그인한 상태면 생략(Authorization 헤더) */
export function useMfaSetup() {
  return useMutation({
    mutationFn: async (mfaToken?: string | null) =>
      (await apiClient.post<MfaSetup>('/api/auth/mfa/setup', { mfa_token: mfaToken ?? null })).data,
  })
}

export function useMfaEnable() {
  return useMutation({
    mutationFn: async (body: { mfa_token?: string | null; code: string }) =>
      (await apiClient.post<MfaEnableResult>('/api/auth/mfa/enable', { mfa_token: body.mfa_token ?? null, code: body.code })).data,
  })
}

export const errDetail = (e: unknown): string | undefined =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
