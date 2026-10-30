import { flushPromises } from '@vue/test-utils'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { watch } from 'vue'
import { useChartTheme } from '~/composables/useChartTheme'

// The page's chart theme follows the class the colour mode puts on <html>, and is the light one for as
// long as the page is printed, whatever the screen shows (a saved or printed chart is light, GH-3528).
// The stylesheet is not in the test's document, so the colours are empty: the theme says only whether it is dark.

// the `print` media query, which a test document never answers: its listener is kept, to call
let printQuery: (event: { matches: boolean }) => void = () => {}
const matchMedia = window.matchMedia

describe('useChartTheme', () => {
  beforeAll(() => {
    // before the first use of the composable, which listens where it first runs
    window.matchMedia = ((query: string) => ({
      ...matchMedia.call(window, query),
      addEventListener: (_type: string, listener: typeof printQuery) => {
        if (query === 'print')
          printQuery = listener
      },
    })) as typeof window.matchMedia
    useChartTheme()
  })

  afterEach(() => {
    document.documentElement.classList.remove('dark')
    window.dispatchEvent(new Event('afterprint'))
    printQuery({ matches: false })
  })

  afterAll(() => {
    window.matchMedia = matchMedia
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
    window.dispatchEvent(new Event('afterprint'))
    expect(theme.value.dark).toBe(true)
  })

  it('stays light where the page is switched to dark while it prints', async () => {
    const { theme } = useChartTheme()
    await flushPromises()
    window.dispatchEvent(new Event('beforeprint'))
    document.documentElement.classList.add('dark')
    await flushPromises()
    expect(theme.value.dark).toBe(false)
    window.dispatchEvent(new Event('afterprint'))
    expect(theme.value.dark).toBe(true)
  })

  it('is light while the print media query matches, where a browser says no more', async () => {
    const { theme } = useChartTheme()
    document.documentElement.classList.add('dark')
    await flushPromises()
    printQuery({ matches: true })
    expect(theme.value.dark).toBe(false)
    printQuery({ matches: false })
    expect(theme.value.dark).toBe(true)
  })

  it('is the very theme the page shows where the page is light, so that a print redraws no chart', async () => {
    const { theme } = useChartTheme()
    await flushPromises()
    const shown = theme.value
    const changed = vi.fn()
    const stop = watch(theme, changed, { flush: 'sync' })
    window.dispatchEvent(new Event('beforeprint'))
    printQuery({ matches: true })
    await flushPromises()
    window.dispatchEvent(new Event('afterprint'))
    printQuery({ matches: false })
    await flushPromises()
    stop()
    expect(theme.value).toBe(shown)
    expect(changed).not.toHaveBeenCalled()
  })

  it('is another theme for a print of a page that is dark, which the charts redraw in', async () => {
    const { theme } = useChartTheme()
    document.documentElement.classList.add('dark')
    await flushPromises()
    const changed = vi.fn()
    const stop = watch(theme, changed, { flush: 'sync' })
    window.dispatchEvent(new Event('beforeprint'))
    window.dispatchEvent(new Event('afterprint'))
    stop()
    expect(changed).toHaveBeenCalledTimes(2)
  })
})
