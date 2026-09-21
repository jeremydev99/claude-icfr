import ApiOnlyPlaceholder from '../components/ApiOnlyPlaceholder'

export default function PoliciesPage() {
  return (
    <ApiOnlyPlaceholder
      title="정책 설정"
      description="부서승인 단계 사용 여부, 이해상충 조합 금지 토글, 증빙 편집 허용, 증빙 보존기간·크기 상한."
      endpoints={['GET /api/org/policies', 'PUT /api/org/policies (upsert)']}
      note="내부회계관리자 전용 화면입니다(서버가 require_icfr_manager 로 최종 판정)."
    />
  )
}
