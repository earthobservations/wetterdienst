import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { computed, shallowRef } from 'vue'
import Meteogram from '~/components/Meteogram.vue'
import { EMPTY_CHART_THEME } from '~/utils/chart-theme'

// Plotly draws nothing in the test's document: its calls are recorded
const plotly = vi.hoisted(() => ({
  newPlot: vi.fn(async () => {}),
  relayout: vi.fn(async () => {}),
  purge: vi.fn(),
}))
vi.mock('plotly.js-basic-dist-min', () => plotly)

// the chart theme, which the test switches by hand
const { current } = vi.hoisted(() => ({ current: { value: null as unknown as { value: Record<string, unknown> } } }))
mockNuxtImport('useChartTheme', () => () => {
  current.value ??= shallowRef({ ...EMPTY_CHART_THEME, dark: true, textStrong: 'rgb(255, 255, 255)' }) as never
  const theme = computed(() => current.value.value) as never
  return { theme, isDark: computed(() => (theme as { value: { dark: boolean } }).value.dark) }
})

const wind = ['wind_speed', 'wind_direction', 'temperature_air_2m'].flatMap(parameter => Array.from({ length: 30 }, (_, hour) => ({
  station_id: '10384',
  resolution: 'hourly',
  dataset: 'small',
  parameter,
  timestamp: new Date(Date.UTC(2026, 9, 1, hour)).toISOString().replace('.000Z', '+00:00'),
  value: parameter === 'wind_direction' ? 270 : 6,
  quality_flags: null,
})))

// The wind barbs are painted on a canvas over the chart, in the colour the chart was drawn in. A switch of the
// colour scheme is drawn again a moment later, and a redraw of the barbs in that moment (a resize) keeps the
// chart's own colour, which is what lies under them.
describe('meteogram wind barbs in the colours of the chart', { timeout: 15_000 }, () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  it('are painted in the theme the chart was drawn in until it is drawn again', async () => {
    const colours: string[] = []
    const context = new Proxy({} as Record<string, unknown>, {
      get: (target, property: string) => (property in target ? target[property] : vi.fn()),
      set: (target, property: string, value) => {
        target[property] = value
        if (property === 'strokeStyle')
          colours.push(value)
        return true
      },
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((() => context) as any)
    plotly.newPlot.mockClear()
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values: wind })
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())
    await flushPromises()
    expect(colours.at(-1)).toBe('rgb(255, 255, 255)')

    // the page switched to light, and the chart is yet to be drawn again: its barbs are painted as the chart is
    current.value.value = { ...EMPTY_CHART_THEME, dark: false, textStrong: 'rgb(15, 23, 42)' }
    colours.length = 0
    window.dispatchEvent(new Event('resize'))
    expect(colours.length).toBeGreaterThan(0)
    expect(new Set(colours)).toEqual(new Set(['rgb(255, 255, 255)']))

    // and the chart drawn again is painted in the new ones
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(2))
    await flushPromises()
    colours.length = 0
    window.dispatchEvent(new Event('resize'))
    expect(new Set(colours)).toEqual(new Set(['rgb(15, 23, 42)']))
  })
})
