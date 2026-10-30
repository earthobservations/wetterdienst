import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { useChartTheme } from '~/composables/useChartTheme'

// The page's chart theme follows the class the colour mode puts on <html>, and is the light one for as
// long as the page is printed, whatever the screen shows (a saved or printed chart is light, GH-3528).
// The stylesheet is not in the test's document, so the colours are empty: the theme says only whether it is dark.
describe('useChartTheme', () => {
  afterEach(() => {
    document.documentElement.classList.remove('dark')
    window.dispatchEvent(new Event('afterprint'))
  })

  it('follows the class of <html>', async () => {
    const { theme, isDark } = useChartTheme()
    await flushPromises()
    expect(isDark.value).toBe(false)
    document.documentElement.classList.add('dark')
    await flushPromises()
    expect(theme.value.dark).toBe(true)
    document.documentElement.classList.remove('dark')
    await flushPromises()
    expect(isDark.value).toBe(false)
  })

  it('is light while the page is printed, from beforeprint to afterprint', async () => {
    const { theme, isDark } = useChartTheme()
    document.documentElement.classList.add('dark')
    await flushPromises()
    expect(isDark.value).toBe(true)

    window.dispatchEvent(new Event('beforeprint'))
    expect(isDark.value).toBe(false)
    // the page being switched to dark while it prints does not make the print dark
    expect(theme.value.dark).toBe(false)
    window.dispatchEvent(new Event('afterprint'))
    expect(isDark.value).toBe(true)
  })
})
