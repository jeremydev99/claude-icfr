import ApiOnlyPlaceholder from '../components/ApiOnlyPlaceholder'

export default function DepartmentsPage() {
  return (
    <ApiOnlyPlaceholder
      title="부서 관리"
      description="부서 등록·계층·책임자 지정. 통제책임자의 주 소속 부서가 대시보드의 통제 조직별 집계 기준이 됩니다."
      endpoints={[
        'GET  /api/org/departments',
        'POST /api/org/departments',
        'PATCH/DELETE /api/org/departments/{id}',
        'GET/POST /api/org/memberships (소속)',
      ]}
      note="현재 부서 0건 — 등록 전까지 통제 조직별 집계는 전부 미배정으로 나옵니다."
    />
  )
}
