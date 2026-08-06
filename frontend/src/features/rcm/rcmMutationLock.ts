// ICFR-PROMPT-envelope-required.md 6단계. 현재 생성/수정/삭제는 legacy `controls` 테이블에 기록되고
// 목록·상세는 resolve_controls(baseline/instance) 경유라, 저장해도 목록에 나타나지 않는 UX 버그를 막는다.
// Excel 업로드(mode=commit)도 동일하게 legacy 테이블에 쓰므로 함께 잠근다.
// TODO(2-A-4): mutation 연결 시 이 플래그와 참조 전부 제거
export const RCM_MUTATION_LOCKED = true

export const RCM_MUTATION_LOCKED_MESSAGE = '백엔드 이관 작업 중입니다. 통제 등록·수정은 잠시 후 가능합니다.'
