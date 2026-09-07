// 상위 3계층(Process/SubProcess/Risk) 편집/삭제 버튼 노출 권한 seam.
// 역할 기반 판단은 아직 미확정(ADR-0031)이라 지금은 무조건 true를 반환한다 —
// 인라인 하드코딩 대신 이 헬퍼 뒤에 둬서, 역할 로직이 확정되면 여기 한 곳만 바꾼다.
export function canEditHierarchy(): boolean {
  return true
}
