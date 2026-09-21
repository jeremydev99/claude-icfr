import {
  Building2,
  CalendarRange,
  LayoutDashboard,
  SlidersHorizontal,
  UserCog,
  Calendar,
  Target,
  ShieldCheck,
  FileSpreadsheet,
  Database,
  CheckCircle2,
  Wrench,
  FileText,
  Paperclip,
  Users,
  Mail,
  type LucideIcon,
} from 'lucide-react'

/**
 * 모듈 구현 상태 (4-1 대시보드).
 *
 * **2026-09-18 실측으로 정한 값이다.** 사이드바 설명 문구("Phase 1에서 구현 예정")를
 * 근거로 삼지 않는다 — 실제로는 화면이 있는데 문구만 남아 있던 모듈이 4개였다
 * (`ClaudeICFR.md` 13.9-40). 현황판이 현황을 틀리게 말하면 만든 의미가 없다.
 *
 * - `live`  : 실데이터가 들어 있고 화면에서 그 데이터를 다룬다
 * - `ready` : 화면이 동작하나 아직 데이터가 없다(쓰기 시작하면 바로 `live`)
 * - `api`   : **백엔드 API 는 있고 화면이 아직 없다.** `todo` 와 구분한다 — 붙이기만 하면
 *             되는 것과 아무것도 없는 것은 남은 일의 크기가 다르다
 * - `todo`  : 빈 페이지. 메뉴 자리만 있다
 *
 * 값이 바뀌는 시점은 "데이터가 들어왔을 때"와 "화면이 붙었을 때"뿐이라 손으로 관리한다.
 */
export type ModuleStatus = 'live' | 'ready' | 'api' | 'todo'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
  description: string
  /** 대시보드 카드 배지. 대시보드(자기 자신)에는 없다. */
  status?: ModuleStatus
  /**
   * `icfr_manager` 만 쓸 수 있는 메뉴 (ADR-0031 §2.6).
   *
   * **`can_write` 로 막지 않는다** — `can_write` 는 `external_auditor` 판정이지
   * `icfr_manager` 판정이 아니다(`features/auth/permissions.pure.ts` 참조).
   */
  requiresIcfrManager?: boolean
}

export interface NavGroup {
  groupLabel: string | null
  items: NavItem[]
}

export const navigation: NavGroup[] = [
  {
    groupLabel: null,
    items: [
      {
        label: '대시보드',
        path: '/dashboard',
        icon: LayoutDashboard,
        description: '전체 ICFR 진행 현황 한눈에 보기',
      },
    ],
  },
  {
    groupLabel: '계획',
    items: [
      {
        label: '일정관리',
        path: '/schedule',
        status: 'todo',
        icon: Calendar,
        description: '연간 ICFR 평가 일정 수립·진행률 추적',
      },
      {
        label: 'Scoping',
        path: '/scoping',
        status: 'todo',
        icon: Target,
        description: '계정과목별 평가 대상 범위 결정 (정량·정성 기준)',
      },
    ],
  },
  {
    groupLabel: '통제',
    items: [
      {
        label: 'RCM 관리',
        path: '/rcm',
        status: 'live',
        icon: ShieldCheck,
        description: '리스크-통제 매트릭스 관리 (프로세스·리스크·통제·버전)',
      },
      {
        label: 'EUC',
        path: '/euc',
        status: 'todo',
        icon: FileSpreadsheet,
        description: 'End User Computing 등록·테스트·변경관리',
      },
      {
        label: 'IUC',
        path: '/iuc',
        status: 'todo',
        icon: Database,
        description: '통제에 사용된 정보(IUC/IPE) 완전성·정확성 검증',
      },
    ],
  },
  {
    groupLabel: '평가',
    items: [
      {
        label: 'Test',
        path: '/test',
        status: 'ready',
        icon: CheckCircle2,
        description: '설계·운영평가 계획·샘플링·결과 입력·검토 워크플로',
      },
      {
        label: '개선계획',
        path: '/remediation',
        status: 'ready',
        icon: Wrench,
        description: '미비점 등록·심각도 평가·개선계획·재테스트',
      },
      {
        label: '증빙 관리',
        path: '/evidence',
        status: 'ready',
        icon: Paperclip,
        description: '평가·테스트 증빙 파일 업로드·연결·보존',
      },
    ],
  },
  {
    groupLabel: '보고',
    items: [
      {
        label: 'Report',
        path: '/report',
        status: 'todo',
        icon: FileText,
        description: '이사회 보고서·외부감사 PBC 패키지 작성·결재·배포',
      },
    ],
  },
  {
    // 관리자 기능 — 백엔드 API 는 3-1(부서·배정·정책)에서 이미 만들었고 화면만 없다.
    // 자리를 먼저 만들어 두면 붙이기 쉽고, 대시보드의 "미배정 93건"과도 이어진다.
    groupLabel: '관리자 기능',
    items: [
      {
        label: '부서 관리',
        path: '/admin/departments',
        icon: Building2,
        description: '부서 등록·소속 인원·책임자 지정',
        status: 'ready',
        // **`requiresIcfrManager` 를 붙이지 않는다** — 조회는 누구나 할 수 있고(서버도 인증만),
        // 조직도를 보는 것 자체는 막을 이유가 없다. 화면 안에서 쓰기 버튼만 잠근다.
      },
      {
        label: '역할 배정',
        path: '/admin/role-assignments',
        icon: UserCog,
        description: '통제·프로세스 단위 역할 배정 (GET/POST /api/org/assignments)',
        status: 'api',
        requiresIcfrManager: true,
      },
      {
        label: '정책 설정',
        path: '/admin/policies',
        icon: SlidersHorizontal,
        description: '부서승인 토글·증빙 편집 토글·보존기간 (GET/PUT /api/org/policies)',
        status: 'api',
        requiresIcfrManager: true,
      },
      {
        label: '회계연도 시작월',
        path: '/admin/fiscal-year',
        icon: CalendarRange,
        description: '회계연도가 시작하는 달 (tenant_policies)',
        status: 'api',
      },
    ],
  },
  {
    groupLabel: '시스템',
    items: [
      {
        label: '담당자/권한',
        path: '/users',
        status: 'ready',
        icon: Users,
        description: '사용자·역할·권한·SoD 관리',
      },
      {
        label: '메일발송',
        path: '/notification',
        status: 'todo',
        icon: Mail,
        description: '알림 템플릿·규칙·발송 이력 관리',
      },
    ],
  },
]
