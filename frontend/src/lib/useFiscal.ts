import { useFiscalStartMonth } from '@/features/schedule/api/useSchedule'
import { endMonthOf, fiscalEndKo, fiscalRange, fiscalRangeText, fiscalYearOfDate, fyLabel, fyShort } from './fiscalYear'

/** 회사 회계연도 설정을 읽어 표기 도우미를 준다 — 화면은 이 훅으로만 회계연도를 표시한다(lib/fiscalYear.ts) */
export function useFiscal() {
  const { data: startMonth = 1, isLoading } = useFiscalStartMonth()
  return {
    startMonth,
    endMonth: endMonthOf(startMonth),
    isLoading,
    /** 오늘이 속한 회계연도 — 기본 연도는 달력 연도(getFullYear)가 아니라 이 값(2026-10-12) */
    thisFy: fiscalYearOfDate(new Date(), startMonth),
    label: (fy: number) => fyLabel(fy, startMonth),
    short: (fy: number) => fyShort(fy, startMonth),
    range: (fy: number) => fiscalRange(fy, startMonth),
    rangeText: (fy: number) => fiscalRangeText(fy, startMonth),
    endKo: (fy: number) => fiscalEndKo(fy, startMonth),
  }
}
