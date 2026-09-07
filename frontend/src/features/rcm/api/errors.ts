// 상위 3계층(Process/SubProcess/Risk) CRUD 공용 에러 핸들러.
// 409는 서버 detail을 그대로 노출한다 — 충돌 종류(baseline 중복/instance 중복 등)를 문자열로
// 매칭해 프론트가 재해석하지 않는다(rcm_상위3계층_crud_ui.md §1.5).
import { isAxiosError } from 'axios'

export function extractHierarchyErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const data = err.response?.data
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg: string }) => d.msg).join(', ')
    if (err.response?.status === 401) return '로그인이 필요합니다'
    if (err.response?.status === 404) return '대상을 찾을 수 없습니다'
    if (!err.response) return '서버에 연결할 수 없습니다'
  }
  return '알 수 없는 오류가 발생했습니다'
}
