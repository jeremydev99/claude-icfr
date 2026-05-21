import { createBrowserRouter, Navigate } from 'react-router-dom'
import AuthLayout from '@/layouts/AuthLayout'
import AppLayout from '@/layouts/AppLayout'
import PrivateRoute from './PrivateRoute'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import SchedulePage from '@/features/schedule/pages/SchedulePage'
import ScopingPage from '@/features/scoping/pages/ScopingPage'
import RcmPage from '@/features/rcm/pages/RcmPage'
import EucPage from '@/features/euc/pages/EucPage'
import IucPage from '@/features/iuc/pages/IucPage'
import TestPage from '@/features/test/pages/TestPage'
import RemediationPage from '@/features/remediation/pages/RemediationPage'
import ReportPage from '@/features/report/pages/ReportPage'
import EvidencePage from '@/features/evidence/pages/EvidencePage'
import UsersPage from '@/features/users/pages/UsersPage'
import NotificationPage from '@/features/notification/pages/NotificationPage'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <AuthLayout />,
    children: [{ index: true, element: <LoginPage /> }],
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
      { path: 'scoping', element: <ScopingPage /> },
      { path: 'rcm', element: <RcmPage /> },
      { path: 'euc', element: <EucPage /> },
      { path: 'iuc', element: <IucPage /> },
      { path: 'test', element: <TestPage /> },
      { path: 'remediation', element: <RemediationPage /> },
      { path: 'report', element: <ReportPage /> },
      { path: 'evidence', element: <EvidencePage /> },
      { path: 'users', element: <UsersPage /> },
      { path: 'notification', element: <NotificationPage /> },
      { path: '*', element: <Navigate to="/dashboard" replace /> },
    ],
  },
])
