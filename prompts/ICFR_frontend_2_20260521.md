# ICFR_frontend_2_20260521.md — Phase 0 작업5: 11개 모듈 메뉴·라우트·빈 페이지 골조

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-21 |
| 작업 유형 | 프론트엔드 모듈 골조 (11개 모듈 메뉴 + 라우트 + 빈 페이지 + TanStack Query 클라이언트) |
| 담당 | Regina |
| Phase | Phase 0 — 작업 단위 5 |
| 결정 출처 | claude.ai 사전 승인 (2026-05-21) |
| 예상 작업 시간 | 1~1.5시간 |
| 영향 파일 | `frontend/src/` 내 신규 약 13개 파일 + AppLayout 수정 |
| 커밋 메시지 제안 | `feat(frontend): 11개 모듈 메뉴·라우트·빈 페이지 골조 (Phase 0 작업5)` |
| 브랜치 | `feature/fe-phase0-modules` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 메뉴 정렬 기준 | 업무 흐름 순 (계획 → 통제 → 평가 → 보고 → 시스템) |
| 그룹화 방식 | 5개 카테고리 그룹화 (대시보드 + 5그룹) |
| 페이지 내용 | "준비중" 안내 + 모듈 한 줄 설명 |
| 메뉴 아이콘 | lucide-react |
| 사이드바 고정 | sticky (스크롤 시 따라옴) |
| 그룹 동작 | 기본 펼침, 그룹명 클릭으로 접기/펼치기 가능 |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4 모듈별 명세, 섹션 12 진행 상태, ADR-0017·0018),
`CLAUDE.md` (섹션 9 명세 동기화 체크)를 먼저 확인하고, 아래 모듈 골조를 순서대로 생성해줘.

**작업 시작 전 필수 체크 (CLAUDE.md 섹션 9)**:
1. `git fetch origin` 으로 원격 최신 상태 가져오기
2. `git checkout main && git pull` 후 `feature/fe-phase0-modules` 브랜치 새로 생성
3. 기존 `frontend/` 골조 정상 동작 확인 (`npm run build` 통과)

---

## 1. 메뉴 구조 (확정)

```
📊 대시보드 (단독, 그룹 없음)

📋 계획 (Planning)
  ├─ 일정관리      /schedule
  └─ Scoping       /scoping

🎯 통제 (Control)
  ├─ RCM 관리      /rcm
  ├─ EUC           /euc
  └─ IUC           /iuc

✓ 평가 (Assessment)
  ├─ Test (평가)   /test
  └─ 개선계획      /remediation

📄 보고 (Reporting)
  ├─ Report        /report
  └─ 증빙 관리     /evidence

⚙️ 시스템 (System)
  ├─ 담당자/권한   /users
  └─ 메일발송      /notification
```

총 11개 모듈 + 1개 대시보드 = 12개 메뉴 항목, 5개 그룹.

---

## 2. 추가 생성 파일 구조

```
frontend/src/
├── config/
│   └── navigation.ts            ← 메뉴 구조 단일 정의 (그룹·아이콘·경로)
├── features/
│   ├── schedule/
│   │   └── pages/SchedulePage.tsx
│   ├── scoping/
│   │   └── pages/ScopingPage.tsx
│   ├── rcm/
│   │   └── pages/RcmPage.tsx
│   ├── euc/
│   │   └── pages/EucPage.tsx
│   ├── iuc/
│   │   └── pages/IucPage.tsx
│   ├── test/
│   │   └── pages/TestPage.tsx
│   ├── remediation/
│   │   └── pages/RemediationPage.tsx
│   ├── report/
│   │   └── pages/ReportPage.tsx
│   ├── evidence/
│   │   └── pages/EvidencePage.tsx
│   ├── users/
│   │   └── pages/UsersPage.tsx
│   └── notification/
│       └── pages/NotificationPage.tsx
├── components/
│   └── common/
│       └── PlaceholderPage.tsx  ← 공용 "준비중" 컴포넌트
└── (수정) layouts/AppLayout.tsx ← 새 메뉴 구조 반영
└── (수정) routes/index.tsx      ← 11개 모듈 라우트 추가
```

---

## 3. 핵심 파일 구현 내용

### 3.1 config/navigation.ts

메뉴 구조 단일 진실 공급원. 사이드바와 라우트가 이 파일을 참조해서 자동 생성하도록.

```typescript
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
  description: string  // PlaceholderPage에서 사용
}

export interface NavGroup {
  groupLabel: string | null  // null이면 단독 항목 (대시보드)
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
```

### 3.2 components/common/PlaceholderPage.tsx

각 모듈 페이지에서 공통으로 사용하는 "준비중" 컴포넌트.

```tsx
import { Construction } from 'lucide-react'

interface PlaceholderPageProps {
  title: string
  description: string
}

export default function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="mt-2 text-muted-foreground">{description}</p>
      </div>
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12">
        <Construction className="h-12 w-12 text-muted-foreground" />
        <p className="mt-4 text-sm text-muted-foreground">준비중입니다 — Phase 1에서 구현 예정입니다.</p>
      </div>
    </div>
  )
}
```

### 3.3 각 모듈 페이지 (11개)

모두 동일 패턴. 예시 — `features/rcm/pages/RcmPage.tsx`:

```tsx
import PlaceholderPage from '@/components/common/PlaceholderPage'

export default function RcmPage() {
  return (
    <PlaceholderPage
      title="RCM 관리"
      description="리스크-통제 매트릭스 관리 (프로세스·리스크·통제·버전)"
    />
  )
}
```

나머지 10개도 동일 구조로 생성. title·description은 `navigation.ts`의 값과 일치해야 함.

### 3.4 layouts/AppLayout.tsx 수정

기존 7개 빈 링크를 `navigation.ts` 기반으로 교체. 추가 요구사항:

- **사이드바 sticky 고정**: `position: sticky; top: 0; height: 100vh; overflow-y: auto;`
- **그룹 접기/펼치기**:
  - 그룹명 클릭 시 하위 메뉴 토글
  - 초기 상태: 모든 그룹 펼쳐짐 (`expanded: true`)
  - 접힌 상태 표시: 그룹명 우측에 chevron 아이콘 (`ChevronDown`/`ChevronRight`)
  - 그룹 펼침 상태는 컴포넌트 로컬 state로 관리 (localStorage 저장은 작업5 범위 외)
- **현재 경로 활성 표시**:
  - `useLocation()` 으로 현재 path 가져와서 일치하는 메뉴 항목에 강조 스타일 (`bg-accent`)
- **단독 항목 (대시보드)**: `groupLabel === null` 이면 그룹 헤더 없이 바로 메뉴 항목 렌더
- **아이콘 표시**: 각 메뉴 항목 좌측에 lucide 아이콘 (16px, `text-muted-foreground`)

레이아웃 골격:

```
┌─────────────────────────────────────────────┐
│ ┌─── Sidebar (240px, sticky) ───┐  Outlet  │
│ │ ICFR (로고)                    │          │
│ │                                │          │
│ │ 📊 대시보드                    │          │
│ │                                │          │
│ │ 계획 ▼                         │          │
│ │   📅 일정관리                  │          │
│ │   🎯 Scoping                   │          │
│ │                                │          │
│ │ 통제 ▼                         │          │
│ │   🛡 RCM 관리                  │          │
│ │   ...                          │          │
│ │                                │          │
│ │ ─────────────                  │          │
│ │ 👤 Regina (Admin)              │          │
│ │ [로그아웃]                     │          │
│ └────────────────────────────────┘          │
└─────────────────────────────────────────────┘
```

### 3.5 routes/index.tsx 수정

기존 `/dashboard` 라우트 외에 11개 모듈 라우트 추가. 모두 `<PrivateRoute><AppLayout>...</AppLayout></PrivateRoute>` 보호.

```tsx
/login        → LoginPage
/             → Navigate to /dashboard
/dashboard    → DashboardPage
/schedule     → SchedulePage
/scoping      → ScopingPage
/rcm          → RcmPage
/euc          → EucPage
/iuc          → IucPage
/test         → TestPage
/remediation  → RemediationPage
/report       → ReportPage
/evidence     → EvidencePage
/users        → UsersPage
/notification → NotificationPage
*             → Navigate to /dashboard (404 처리)
```

---

## 4. 완료 후 필수 작업

### 4.1 ClaudeICFR.md 업데이트
- **섹션 12.1**: Phase 0 작업5 → ✅ + 완료일 기입 (작업 단위 9의 진행 상태 메모 갱신)
- **섹션 12.2**: 11개 모듈 FE 컬럼 → `🔄 골조` 유지 (작업4에서 이미 변경됨, 추가 변경 없음). 단, 비고에 "메뉴·라우트 연결" 표시 가능
- **섹션 14**: 변경 로그에 "Regina: Phase 0 작업5 완료 — 11개 모듈 메뉴·라우트·빈 페이지 골조" 한 줄 추가
- **섹션 18.2**: 일일 진행 로그 추가 (2026-05-21)

### 4.2 git 작업 (커밋 전 사용자 OK 확인 필수)

```bash
git checkout -b feature/fe-phase0-modules
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_2_20260521.md
git commit -m "feat(frontend): 11개 모듈 메뉴·라우트·빈 페이지 골조 (Phase 0 작업5)"
git push -u origin feature/fe-phase0-modules
```

### 4.3 동작 확인 체크리스트
- [ ] `npm run build` 통과 (TypeScript 오류 없음)
- [ ] `npm run dev` → `http://localhost:5173` 로그인 후 `/dashboard` 이동
- [ ] 사이드바에 대시보드 + 5개 그룹 + 11개 메뉴 모두 표시
- [ ] 각 메뉴 클릭 → 해당 경로 이동 + 페이지 제목·설명·"준비중" 박스 표시
- [ ] 그룹명 클릭 → 하위 메뉴 접기/펼치기 동작
- [ ] 현재 경로의 메뉴 항목이 강조 표시됨
- [ ] 페이지 스크롤 시 사이드바 sticky 고정 동작
- [ ] 존재하지 않는 경로 (`/foo`) 접근 → `/dashboard` 로 리다이렉트
- [ ] 미인증 상태 모든 모듈 경로 접근 → `/login` 리다이렉트

---

## 5. 작업 외 (작업6 이후로 미룸)

다음 항목은 이번 작업에서 다루지 않음:
- TanStack Query 클라이언트 실제 API 호출 (각 모듈별 데이터 로드 — Phase 1)
- 사이드바 모바일 반응형 토글 (Phase 1)
- 그룹 펼침 상태 localStorage 영속화 (필요 시 작업6)
- 권한 기반 메뉴 숨김 (Phase 1)

---

## 6. 참조

- 모듈별 명세: `ClaudeICFR.md` 섹션 4 (4.1 ~ 4.11)
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_1_20260520.md` (작업4 프론트엔드 골조)
- 다음 작업: 작업6 (시드 데이터, TrustBuilder 담당) 또는 Phase 1 진입
