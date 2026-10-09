import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { I18nProvider } from '../i18n'
import { Button } from './Button'
import { EmptyState } from './EmptyState'
import { ToastProvider, useToast } from './Toast'
import { Inbox } from 'lucide-react'

afterEach(() => { cleanup(); vi.useRealTimers() })

describe('Button', () => {
  test('renders its label', () => {
    render(<Button>Save</Button>)
    expect(screen.getByRole('button', { name: 'Save' })).toBeTruthy()
  })
  test('is aria-busy and disabled while loading', () => {
    render(<Button loading>Save</Button>)
    const b = screen.getByRole('button', { name: /Save/ })
    expect(b.getAttribute('aria-busy')).toBe('true')
    expect((b as HTMLButtonElement).disabled).toBe(true)
  })
})

function Trigger() {
  const toast = useToast()
  return <button onClick={() => toast('Saved po')}>go</button>
}

describe('Toast', () => {
  test('is announced in the live region and disappears after 4 s', () => {
    vi.useFakeTimers()
    render(<I18nProvider><ToastProvider><Trigger /></ToastProvider></I18nProvider>)
    act(() => { screen.getByText('go').click() })
    const region = document.querySelector('[aria-live="polite"]')!
    expect(region).toBeTruthy()
    expect(region.textContent).toContain('Saved po')
    act(() => { vi.advanceTimersByTime(3900) })
    expect(region.textContent).toContain('Saved po')
    act(() => { vi.advanceTimersByTime(200) })
    expect(region.textContent).not.toContain('Saved po')
  })
})

describe('EmptyState', () => {
  test('renders its action button', async () => {
    const onClick = vi.fn()
    render(<EmptyState icon={Inbox} title="Wala pa po" body="Magdagdag ng record." action={{ label: 'Magdagdag', onClick }} />)
    expect(screen.getByRole('heading', { name: 'Wala pa po' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Magdagdag' }))
    expect(onClick).toHaveBeenCalledOnce()
  })
})
