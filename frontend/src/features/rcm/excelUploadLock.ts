// Excel 업로드 전용 잠금 — 13.6 다중 헤더행 파싱 버그(0건 파싱) 해소 시까지 유지.
// Excel 업로드(mode=commit)는 legacy `controls` 테이블에 기록되고 목록·상세는
// resolve_controls(baseline/instance) 경유라, 업로드해도 목록에 나타나지 않는 UX 버그를 막는다.
// TODO(2-A-4-3): 13.6 버그 해소 시 이 플래그와 참조 전부 제거
export const EXCEL_UPLOAD_LOCKED = true

export const EXCEL_UPLOAD_LOCKED_MESSAGE = 'Excel 업로드는 다중 헤더행 파싱 버그 해소 후 가능합니다.'
