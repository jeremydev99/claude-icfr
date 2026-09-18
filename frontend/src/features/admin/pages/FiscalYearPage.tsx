import ApiOnlyPlaceholder from '../components/ApiOnlyPlaceholder'

export default function FiscalYearPage() {
  return (
    <ApiOnlyPlaceholder
      title="회계연도 시작월"
      description="회계연도가 시작하는 달(1~12). 결산월이 아니라 시작월입니다 — 12월 결산 회사는 1, 3월 결산 회사는 4입니다."
      endpoints={['GET /api/org/policies', 'PUT /api/org/policies (policy_key: fiscal_year_start_month)']}
      note="평가 회차의 기간 계산이 이 값을 따릅니다(ADR-0032)."
    />
  )
}
