import { useFiscalStartMonth } from '@/features/schedule/api/useSchedule'
import { endMonthOf, fiscalEndKo, fiscalRange, fiscalRangeText, fyLabel, fyShort } from './fiscalYear'

/** 회사 회계연도 설정을 읽어 표기 도우미를 준다 — 화면은 이 훅으로만 회계연도를 표시한다(lib/fiscalYear.ts) */
export function useFiscal() {
  const { data: startMonth = 1, isLoading } = useFiscalStartMonth()
  return {
    startMonth,
    endMonth: endMonthOf(startMonth),
    isLoading,
    label: (fy: number) => fyLabel(fy, startMonth),
    short: (fy: number) => fyShort(fy, startMonth),
    range: (fy: number) => fiscalRange(fy, startMonth),
    rangeText: (fy: number) => fiscalRangeText(fy, startMonth),
    endKo: (fy: number) => fiscalEndKo(fy, startMonth),
  }
}
