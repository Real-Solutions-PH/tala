import { afterEach, expect, test } from 'vitest'
import { applyTheme, readTheme, THEME_KEY } from './theme'

afterEach(() => { localStorage.clear(); delete document.documentElement.dataset.skin })

test('a chosen theme is applied as data-skin and remembered; Blue clears it', () => {
  expect(readTheme()).toBe('blue')
  applyTheme('navy')
  expect(document.documentElement.dataset.skin).toBe('navy')
  expect(readTheme()).toBe('navy')
  applyTheme('blue')
  expect(document.documentElement.dataset.skin).toBeUndefined()
  expect(localStorage.getItem(THEME_KEY)).toBe('blue')
})

test('an unknown stored value falls back to Blue', () => {
  localStorage.setItem(THEME_KEY, 'purple')
  expect(readTheme()).toBe('blue')
})
