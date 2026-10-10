import { lazy, Suspense, useLayoutEffect } from 'react'
import { Navigate, Outlet, useNavigate, type RouteObject } from 'react-router'
import { ApiError, setOnUnauthorized } from './api/client'
import { useSummary } from './api/queries'
import { BottomNav } from './components/BottomNav'
import { ErrorState } from './components/ErrorState'
import { TopBar } from './components/TopBar'
import { useLock } from './features/lock/useLock'
import {
  ChatPage, ProfilePage, SettingsPage,
} from './pages/placeholders'
import { CardDetailPage, CardsPage } from './features/cards/CardsPage'
import { EmergencyPage } from './features/emergency/EmergencyPage'
import { LockScreen } from './features/lock/LockScreen'
import { MedsPage } from './features/meds/MedsPage'
import { DocumentViewer } from './features/records/DocumentViewer'
import { LabDetail } from './features/records/LabDetail'
import { RecordsPage } from './features/records/RecordsPage'

/** Router root: any 401 from the API forgets the profile and goes to /lock. */
function Root() {
  const navigate = useNavigate()
  const { forget } = useLock()
  useLayoutEffect(() => {
    setOnUnauthorized(() => { forget(); navigate('/lock', { replace: true }) })
    return () => setOnUnauthorized(null)
  }, [navigate, forget])
  return <Outlet />
}

/**
 * The locked layout. One plane: a 100dvh grid whose rows are the header, the scrolling main (the only
 * scroll container) and the bottom menu. Nothing is sticky or fixed.
 */
function Shell() {
  const { profileId } = useLock()
  // The summary doubles as the session check: a 401 redirects (in the client), a 403 shows the error state.
  const summary = useSummary(profileId)
  if (profileId == null) return <Navigate to="/lock" replace />
  const forbidden = summary.error instanceof ApiError && summary.error.status === 403
  return (
    <div className="shell">
      <TopBar />
      <main className="shell__main" id="main">
        {forbidden
          ? <div className="page"><ErrorState message="errors.notYourProfile" onRetry={() => { summary.refetch() }} /></div>
          : <Outlet />}
      </main>
      <BottomNav />
    </div>
  )
}

const Kitchen = import.meta.env.DEV ? lazy(() => import('./dev/Kitchen')) : null

export const routes: RouteObject[] = [
  {
    element: <Root />,
    children: [
      { path: '/lock', element: <LockScreen /> },
      { path: '/emergency/:pid', element: <EmergencyPage /> },
      {
        element: <Shell />,
        children: [
          { path: '/chat/:cid?', element: <ChatPage /> },
          { path: '/cards', element: <CardsPage /> },
          { path: '/cards/:id', element: <CardDetailPage /> },
          { path: '/meds', element: <MedsPage /> },
          { path: '/records', element: <RecordsPage /> },
          { path: '/records/labs/:code', element: <LabDetail /> },
          { path: '/records/documents/:id', element: <DocumentViewer /> },
          { path: '/settings', element: <SettingsPage /> },
          { path: '/profile', element: <ProfilePage /> },
        ],
      },
      ...(Kitchen ? [{ path: '/dev/kitchen', element: <Suspense><Kitchen /></Suspense> }] : []),
      { path: '/', element: <Navigate to="/chat" replace /> },
      { path: '*', element: <Navigate to="/chat" replace /> },
    ],
  },
]
