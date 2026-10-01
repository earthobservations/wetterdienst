import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Meteogram from '~/components/Meteogram.vue'

// Plotly draws nothing in the test's document: its calls are recorded
const plotly = vi.hoisted(() => ({
  newPlot: vi.fn(async () => {}),
  relayout: vi.fn(async () => {}),
  purge: vi.fn(),
}))
vi.mock('plotly.js-basic-dist-min', () => plotly)

// a day of hourly temperatures, which the meteogram draws as its temperature panel
const values = Array.from({ length: 24 }, (_, hour) => ({
  station_id: '10384',
  resolution: 'hourly',
  dataset: 'small',
  parameter: 'temperature_air_mean_2m',
  timestamp: `2026-10-01T${String(hour).padStart(2, '0')}:00:00+00:00`,
  value: 10 + hour / 4,
  quality: null,
}))

describe('meteogram chart that could not be drawn', () => {
  // the chart area's Retry button, and the alert beside it
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')
  const note = () => retry()?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  // mounted, then handed its values, as the meteogram page hands them once they are fetched
  async function showMeteogram() {
    wrapper = await mountSuspended(Meteogram, { props: { values: [], stationName: 'Berlin' }, attachTo: document.body })
    await wrapper.setProps({ values })
  }

  afterEach(() => {
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  it('says so where Plotly failed to load, and loads it again on Retry', async () => {
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    await showMeteogram()
    // the failing module loaded, which a busy runner can take a while over
    await vi.waitFor(() => expect(retry()).toBeDefined(), { timeout: 5000 })
    expect(note()).toBe('The chart could not be drawn')
    expect(logged).toHaveBeenCalledWith('The chart could not be drawn', expect.any(Error))

    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    retry()!.click()
    // the module loaded anew, which a busy runner can take a while over
    await vi.waitFor(() => expect(retry()).toBeUndefined(), { timeout: 5000 })
    expect(plotly.newPlot).toHaveBeenCalledOnce()
  })

  it('says so where drawing fails, and draws the chart on Retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    await showMeteogram()
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toBe('The chart could not be drawn')

    retry()!.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    expect(plotly.newPlot).toHaveBeenCalledTimes(2)
  })

  it('says nothing where a drawing fails that newer values have replaced, and the newer one draws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockClear()
    // the first drawing held, to fail once newer values have come in
    let fail!: (error: Error) => void
    plotly.newPlot.mockImplementationOnce(() => new Promise((_, reject) => {
      fail = reject
    }))
    await showMeteogram()
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce())
    await wrapper!.setProps({ values: values.slice(1) })
    fail(new Error('drawing failed'))

    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(2))
    await vi.waitFor(() => expect((wrapper!.vm as any).renderFailed).toBe(false))
    // never told: the alert was not mounted for it
    expect((wrapper!.vm as any).renderFailures).toBe(0)
    expect(retry()).toBeUndefined()
  })
})
