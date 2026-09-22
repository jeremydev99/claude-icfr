import ModuleCards from '@/features/dashboard/components/ModuleCards'
import RcmSummaryCard from '@/features/dashboard/components/RcmSummaryCard'
import EucIucSummaryCard from '@/features/dashboard/components/EucIucSummaryCard'
import ScopingSummaryCard from '@/features/dashboard/components/ScopingSummaryCard'

/**
 * 대시보드 = 개발 현황판 + RCM 실데이터 (4-1).
 *
 * **0 건도 0 으로 보여준다.** 배정 0건·회차 0건이 보이는 것 자체가 현황이고,
 * 다음에 무엇을 해야 하는지를 드러낸다 — "준비중"으로 가리면 현황판이 아니다.
 */
export default function DashboardPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">대시보드</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          모듈별 구현 현황과 RCM 실데이터 집계
        </p>
      </div>
      <ModuleCards />
      <ScopingSummaryCard />
      <RcmSummaryCard />
      <EucIucSummaryCard />
    </div>
  )
}
