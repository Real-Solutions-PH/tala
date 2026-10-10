import { useState, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { makeQueryClient } from './api/queries'
import { ToastProvider } from './components/Toast'
import { LockProvider } from './features/lock/useLock'
import { useStoredTheme } from './features/settings/theme'
import { useStoredTextScale } from './features/settings/textScale'
import { I18nProvider } from './i18n'
import { routes } from './routes'

/** Everything above the router: data cache, language, toasts and the unlocked profile. */
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient)
  useStoredTextScale()
  useStoredTheme()
  return (
    <QueryClientProvider client={client}>
      <I18nProvider>
        <ToastProvider>
          <LockProvider>{children}</LockProvider>
        </ToastProvider>
      </I18nProvider>
    </QueryClientProvider>
  )
}

export default function App() {
  const [router] = useState(() => createBrowserRouter(routes))
  return (
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  )
}
