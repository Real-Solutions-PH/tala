import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, test } from 'vitest'
import { I18nProvider, type Lang } from '../i18n'
import { BottomNav } from './BottomNav'

function renderNav(path: string, lang: Lang = 'tl') {
  const router = createMemoryRouter(['/home', '/chat', '/cards', '/meds', '/records'].map(p => ({ path: p, element: <BottomNav /> })), { initialEntries: [path] })
  render(<I18nProvider initialLang={lang}><RouterProvider router={router} /></I18nProvider>)
  return router
}

afterEach(cleanup)

describe('BottomNav', () => {
  test('each tab shows a visible label (tl and en)', () => {
    renderNav('/chat')
    const nav = screen.getByRole('navigation')
    for (const name of ['Tahanan', 'Rekord', 'Pitaka', 'Gamot']) {
      const label = within(nav).getByText(name)
      expect(label.className).toBe('navitem__label')
      expect(label.closest('.sr-only')).toBeNull()
    }
    cleanup()
    renderNav('/chat', 'en')
    for (const name of ['Home', 'Records', 'Wallet', 'Medicines', 'Ask Kapiling']) expect(screen.getByRole('link', { name })).toBeTruthy()
  })

  test('aria-current marks only the active tab', () => {
    renderNav('/meds')
    expect(screen.getByRole('link', { name: 'Gamot' }).getAttribute('aria-current')).toBe('page')
    for (const name of ['Tahanan', 'Magtanong kay Kapiling', 'Pitaka', 'Rekord']) expect(screen.getByRole('link', { name }).getAttribute('aria-current')).toBeNull()
  })

  test('the whole tab column is the link: tapping the icon or the label navigates', async () => {
    const router = renderNav('/chat')
    const tab = screen.getByRole('link', { name: 'Rekord' })
    expect(tab.querySelector('svg')).toBeTruthy()
    await userEvent.click(tab.querySelector('.navitem__icon')!)
    expect(router.state.location.pathname).toBe('/records')
    await userEvent.click(within(screen.getByRole('link', { name: 'Pitaka' })).getByText('Pitaka'))
    expect(router.state.location.pathname).toBe('/cards')
    expect(screen.getByRole('link', { name: 'Pitaka' }).getAttribute('aria-current')).toBe('page')
  })
})
