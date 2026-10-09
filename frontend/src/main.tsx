import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './design/base.css'
import App from './App.tsx'
import { I18nProvider } from './i18n'
import { ToastProvider } from './components/Toast'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </I18nProvider>
  </StrictMode>,
)
