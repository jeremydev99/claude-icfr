import {
  LayoutDashboard,
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

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
  description: string
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
        icon: Calendar,
        description: '연간 ICFR 평가 일정 수립·진행률 추적',
      },
      {
        label: 'Scoping',
        path: '/scoping',
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
        icon: ShieldCheck,
        description: '리스크-통제 매트릭스 관리 (프로세스·리스크·통제·버전)',
      },
      {
        label: 'EUC',
        path: '/euc',
        icon: FileSpreadsheet,
        description: 'End User Computing 등록·테스트·변경관리',
      },
      {
        label: 'IUC',
        path: '/iuc',
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
        icon: CheckCircle2,
        description: '설계·운영평가 계획·샘플링·결과 입력·검토 워크플로',
      },
      {
        label: '개선계획',
        path: '/remediation',
        icon: Wrench,
        description: '미비점 등록·심각도 평가·개선계획·재테스트',
      },
    ],
  },
  {
    groupLabel: '보고',
    items: [
      {
        label: 'Report',
        path: '/report',
        icon: FileText,
        description: '이사회 보고서·외부감사 PBC 패키지 작성·결재·배포',
      },
      {
        label: '증빙 관리',
        path: '/evidence',
        icon: Paperclip,
        description: '평가·테스트 증빙 파일 업로드·연결·보존',
      },
    ],
  },
  {
    groupLabel: '시스템',
    items: [
      {
        label: '담당자/권한',
        path: '/users',
        icon: Users,
        description: '사용자·역할·권한·SoD 관리',
      },
      {
        label: '메일발송',
        path: '/notification',
        icon: Mail,
        description: '알림 템플릿·규칙·발송 이력 관리',
      },
    ],
  },
]
