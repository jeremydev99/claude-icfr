import ProposalPage from '@/features/proposals/ProposalPage'
import ControlLinksPage from '@/features/rcm/links/ControlLinksPage'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import AuthLayout from '@/layouts/AuthLayout'
import AppLayout from '@/layouts/AppLayout'
import PrivateRoute from './PrivateRoute'
import LoginPage from '@/pages/LoginPage'
import InvitePage from '@/features/auth/pages/InvitePage'
import DashboardPage from '@/pages/DashboardPage'
import SchedulePage from '@/features/schedule/pages/SchedulePage'
import ScopingPage from '@/features/scoping/pages/ScopingPage'
import FinancialStatementsPage from '@/features/financial-statements/pages/FinancialStatementsPage'
import RcmPage from '@/features/rcm/pages/RcmPage'
import EucPage from '@/features/euc/pages/EucPage'
import IucPage from '@/features/iuc/pages/IucPage'
import TestPage from '@/features/test/pages/TestPage'
import RemediationPage from '@/features/remediation/pages/RemediationPage'
import ReportPage from '@/features/report/pages/ReportPage'
import EvidencePage from '@/features/evidence/pages/EvidencePage'
import UsersPage from '@/features/users/pages/UsersPage'
import NotificationPage from '@/features/notification/pages/NotificationPage'
import DepartmentsPage from '@/features/admin/pages/DepartmentsPage'
import RoleAssignmentsPage from '@/features/admin/pages/RoleAssignmentsPage'
import PoliciesPage from '@/features/admin/pages/PoliciesPage'
import FiscalYearPage from '@/features/admin/pages/FiscalYearPage'
import AuditLogsPage from '@/features/admin/pages/AuditLogsPage'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <AuthLayout />,
    children: [{ index: true, element: <LoginPage /> }],
  },
  // 외부 사용자 초대 수락(ADR-0039) — 로그인 전 공개 화면
  {
    path: '/invite/:token',
    element: <AuthLayout />,
    children: [{ index: true, element: <InvitePage /> }],
  },
  {
    path: '/',
    element: (
      <PrivateRoute>
        <AppLayout />
      </PrivateRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'schedule', element: <SchedulePage /> },
      { path: 'financial-statements', element: <FinancialStatementsPage /> },
      { path: 'scoping', element: <ScopingPage /> },
      { path: 'rcm', element: <RcmPage /> },
      { path: 'rcm/links', element: <ControlLinksPage /> },
      { path: 'euc', element: <EucPage /> },
      { path: 'iuc', element: <IucPage /> },
      { path: 'test', element: <TestPage /> },
      { path: 'remediation', element: <RemediationPage /> },
      { path: 'report', element: <ReportPage /> },
      { path: 'evidence', element: <EvidencePage /> },
      { path: 'users', element: <UsersPage /> },
      { path: 'notification', element: <NotificationPage /> },
      // 관리자 기능 — 화면 미구현(API 있음). 접근 제한은 서버가 최종 판정한다.
      { path: 'admin/departments', element: <DepartmentsPage /> },
      { path: 'admin/role-assignments', element: <RoleAssignmentsPage /> },
      { path: 'admin/policies', element: <PoliciesPage /> },
      { path: 'admin/fiscal-year', element: <FiscalYearPage /> },
      { path: 'admin/audit-logs', element: <AuditLogsPage /> },
      { path: 'proposals/:id', element: <ProposalPage /> },
      { path: '*', element: <Navigate to="/dashboard" replace /> },
    ],
  },
])
