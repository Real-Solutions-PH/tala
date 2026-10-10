import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'
import type { WalletCard } from '../../api/types'
import { I18nProvider } from '../../i18n'
import { CardViewer } from './CardViewer'

const CARD: WalletCard = {
  id: 3, kind: 'philhealth', label: 'PhilHealth', number_masked: '••••0000',
  front_url: '/api/files/3/front', back_url: '/api/files/3/back', expires: null,
}

function renderViewer(card = CARD, onClose = vi.fn()) {
  render(<I18nProvider initialLang="tl"><CardViewer card={card} onClose={onClose} /></I18nProvider>)
  return onClose
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('CardViewer', () => {
  test('toggles between front and back', async () => {
    renderViewer()
    const img = () => screen.getByRole('img') as HTMLImageElement
    expect(img().getAttribute('src')).toBe('/api/files/3/front')
    const back = screen.getByRole('button', { name: 'Likod' })
    await userEvent.click(back)
    expect(img().getAttribute('src')).toBe('/api/files/3/back')
    expect(back.getAttribute('aria-pressed')).toBe('true')
    await userEvent.click(screen.getByRole('button', { name: 'Harap' }))
    expect(img().getAttribute('src')).toBe('/api/files/3/front')
  })

  test('closes on Escape and with the labelled Close button', async () => {
    const onClose = renderViewer()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Isara' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  test('traps focus: Close is focused on open, Tab from the last control wraps to Close, Shift+Tab wraps back', async () => {
    renderViewer()
    const close = screen.getByRole('button', { name: 'Isara' })
    expect(document.activeElement).toBe(close)
    const back = screen.getByRole('button', { name: 'Likod' })
    back.focus()
    await userEvent.tab()
    expect(document.activeElement).toBe(close)
    await userEvent.tab({ shift: true })
    expect(document.activeElement).toBe(back)
  })

  test('hides the side toggle when there is no back photo', () => {
    renderViewer({ ...CARD, back_url: null })
    expect(screen.queryByRole('button', { name: 'Likod' })).toBeNull()
  })

  test('asks for the screen wake lock when available and releases it on close', async () => {
    const release = vi.fn(async () => {})
    const request = vi.fn(async () => ({ release }))
    vi.stubGlobal('navigator', { ...navigator, wakeLock: { request } })
    renderViewer()
    expect(request).toHaveBeenCalledWith('screen')
    await Promise.resolve()
    cleanup()
    await vi.waitFor(() => expect(release).toHaveBeenCalled())
  })
})
