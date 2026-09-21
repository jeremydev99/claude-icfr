import ApiOnlyPlaceholder from '../components/ApiOnlyPlaceholder'

export default function RoleAssignmentsPage() {
  return (
    <ApiOnlyPlaceholder
      title="역할 배정"
      description="통제·프로세스 단위 역할 배정(통제책임자·부서승인·평가자). 이해상충 조합은 사유를 남겨야 저장됩니다."
      endpoints={[
        'GET  /api/org/assignments',
        'POST /api/org/assignments (생성/교체)',
        'DELETE /api/org/assignments/{id}',
        'GET  /api/org/controls/{control_id}/roles (해석)',
      ]}
      note="내부회계관리자 전용 화면입니다. 현재 배정 0건 — 대시보드 통제 조직별이 미배정 93건인 이유입니다."
    />
  )
}
