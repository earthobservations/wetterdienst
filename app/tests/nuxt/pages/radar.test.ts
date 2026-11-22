import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData, clearNuxtState, useState } from '#imports'
import RadarPage from '~/pages/radar.vue'
import { radarAnswer, runTime } from '../../helpers/radar-answer'
import { emptyScan, exampleScan } from '../../helpers/storm-cells-answer'
import { LOCATION_STATE } from '../fixtures/state'

// The Radar tool (GH-3788): the map of the map tool with no stations, DWD's precipitation radar over it as a loop of the last two
// hours and the forecast of the next two, the player, the legend, the credit, and the thunderstorm cells on top. The map itself (Leaflet,
// which draws nothing in the test's document) is a stand-in that takes the props the real one takes; the frames are images that the
// stand-in `Image` loads (or fails to load) at once.

const { stage } = vi.hoisted(() => ({ stage: { props: {} as Record<string, any>, mounts: 0 } }))
vi.mock('~/components/StationMap.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    __esModule: true,
    default: defineComponent({
      props: { stations: Array, selected: null, place: null, label: String, noFullscreen: Boolean, openOn: Array, overlay: null, cells: Array, cellsFaded: Boolean, credits: Array, centreOn: null, position: null, positionLabel: String, locate: Number },
      setup(props) {
        stage.props = props
        stage.mounts++
        return () => h('div', { 'data-testid': 'station-map', 'role': 'application', 'aria-label': props.label })
      },
    }),
  }
})

// the backend's answers, and what each endpoint was asked for
const framesAsked: Array<Record<string, string>> = []
let framesAnswer: () => unknown = () => radarAnswer()
let framesStatus = 200
registerEndpoint('/api/radar/frames', (event) => {
  framesAsked.push(getQuery(event) as Record<string, string>)
  if (framesStatus !== 200) {
    setResponseStatus(event, framesStatus)
    return { detail: 'DWD could not be reached' }
  }
  return framesAnswer()
})
const cellsAsked: Array<Record<string, string>> = []
let cellsScan: () => unknown = () => emptyScan()
registerEndpoint('/api/storm-cells', (event) => {
  cellsAsked.push(getQuery(event) as Record<string, string>)
  return cellsScan()
})

// the frames' images, which the player loads with `fetch`: answered at once (a moment later, so that more than one is open at once), a 503 for
// the addresses a test names, or held until the test lets them go
const imagesAsked: string[] = []
let failing: (url: string) => boolean = () => false
let held: (url: string) => boolean = () => false
let releases: Array<() => void> = []
let imagesOpen = 0
let imagesMostAtOnce = 0
const originalFetch = globalThis.fetch
function stubFetch() {
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input instanceof Request ? input.url : input)
    if (!/\/api\/radar\/frame\?/.test(url))
      return originalFetch(input, init)
    imagesAsked.push(url)
    imagesOpen++
    imagesMostAtOnce = Math.max(imagesMostAtOnce, imagesOpen)
    await new Promise<void>((resolve) => {
      if (held(url))
        releases.push(resolve)
      else
        setTimeout(resolve, 5)
    })
    imagesOpen--
    return failing(url) ? new Response('busy', { status: 503 }) : new Response(new Blob(['png'], { type: 'image/png' }), { status: 200 })
  }) as typeof fetch
}

function stubMediaQueries(options: { wide?: boolean, reducedMotion?: boolean } = {}) {
  window.matchMedia = ((query: string) => ({
    matches: /min-width:\s*72rem/.test(query) ? (options.wide ?? true) : /prefers-reduced-motion:\s*reduce/.test(query) ? (options.reducedMotion ?? false) : false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

const originalMatchMedia = window.matchMedia
const mounted: Array<{ unmount: () => void }> = []
async function mountRadar() {
  const wrapper = await mountSuspended(RadarPage, { route: '/radar', attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
type Wrapper = Awaited<ReturnType<typeof mountRadar>>
const byId = (wrapper: Wrapper, id: string) => wrapper.find(`[data-testid="${id}"]`)
const text = (wrapper: Wrapper) => wrapper.text().replace(/\s+/g, ' ')
/** The loop is settled once every frame is in: its status line says nothing more of loading */
async function loaded(wrapper: Wrapper) {
  await vi.waitFor(() => expect(byId(wrapper, 'radar-newest').exists()).toBe(true))
  await vi.waitFor(() => expect(stage.props.overlay).toBeTruthy())
  await vi.waitFor(() => expect(byId(wrapper, 'radar-frames-loading').exists()).toBe(false))
}

beforeEach(() => {
  stubMediaQueries()
  stubFetch()
})

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  stage.props = {}
  stage.mounts = 0
  framesAsked.length = cellsAsked.length = imagesAsked.length = 0
  framesAnswer = () => radarAnswer()
  framesStatus = 200
  cellsScan = () => emptyScan()
  failing = () => false
  held = () => false
  releases = []
  imagesOpen = imagesMostAtOnce = 0
  clearNuxtData()
  window.matchMedia = originalMatchMedia
  globalThis.fetch = originalFetch
  delete (navigator as any).geolocation
  delete (navigator as any).permissions
  clearNuxtState(LOCATION_STATE)
})

describe('the radar page', () => {
  it('is a page of its own: a title, what it is for, and the map with the radar over it, with no stations and no full-screen button', async () => {
    const wrapper = await mountRadar()
    expect(wrapper.find('h1').text()).toBe('Radar')
    expect(text(wrapper)).toContain('DWD\'s rain radar over Germany: the last two hours and the forecast for the next two.')
    await vi.waitFor(() => expect(byId(wrapper, 'station-map').exists()).toBe(true))
    expect(stage.props.stations).toEqual([])
    expect(stage.props.noFullscreen).toBe(true)
    expect(byId(wrapper, 'station-map').attributes('aria-label')).toBe('Precipitation radar over Germany')
    // it opens on Germany, whose radar this is
    expect(stage.props.openOn).toEqual([[47.2, 5.8], [55.1, 15.1]])
  })

  it('asks for the loop: the RV composite, the last 120 minutes and the forecast', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(framesAsked).toEqual([{ product: 'rv', past: '120', forecast: 'true' }])
  })

  it('lays the newest frame of the analysis over the bounds of the answer, with its run in the address so that it is cacheable', async () => {
    const answer = radarAnswer()
    framesAnswer = () => answer
    const wrapper = await mountRadar()
    await loaded(wrapper)
    // Leaflet's [[south, west], [north, east]], from the answer's {west, south, east, north}
    expect(stage.props.overlay.bounds).toEqual([[45.6823, 1.4633], [56.2194, 18.7316]])
    expect(stage.props.overlay.url).toBe(`/api/radar/frame?product=rv&time=${encodeURIComponent(answer.run)}&run=${encodeURIComponent(answer.run)}`)
    expect(stage.props.overlay.opacity).toBeGreaterThan(0)
    expect(stage.props.overlay.opacity).toBeLessThan(1)
  })
})

describe('loading the frames', () => {
  it('asks for all 49 frames, each once, and never more than 5 at a time (the server serves 32 at once)', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(new Set(imagesAsked).size).toBe(49)
    expect(imagesAsked).toHaveLength(49)
    expect(imagesMostAtOnce).toBe(5)
    // the forecast frames are of the newest run
    const forecast = imagesAsked.filter(url => url.includes(`run=${encodeURIComponent(radarAnswer().run)}`) && !url.includes(`time=${encodeURIComponent(radarAnswer().run)}&`))
    expect(forecast).toHaveLength(24)
  })

  it('drops a frame that fails from the loop and says how many were skipped, and the others play', async () => {
    const answer = radarAnswer()
    framesAnswer = () => answer
    const bad = answer.frames[30]!
    failing = url => url.includes(`time=${encodeURIComponent(bad.time)}&`)
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-skipped').exists()).toBe(true), { timeout: 12_000 })
    expect(byId(wrapper, 'radar-skipped').text()).toBe('Frames that could not be loaded and are skipped: 1')
    // the slider has one frame less
    expect(byId(wrapper, 'radar-slider').attributes('max')).toBe('47')
  })

  it('says how far it is while the frames come', async () => {
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-frames-loading').text()).toMatch(/^Loading frames: \d+ of 49$/))
  })
})

describe('the player', () => {
  it('stands on the newest observed frame with its time in words and observed marked, and has the loop of 49 frames', async () => {
    stubMediaQueries({ reducedMotion: true })
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(byId(wrapper, 'radar-slider').attributes('max')).toBe('48')
    expect((byId(wrapper, 'radar-slider').element as HTMLInputElement).value).toBe('24')
    expect(byId(wrapper, 'radar-kind').text()).toBe('Observed')
    expect(byId(wrapper, 'radar-chip').text()).toContain('Observed')
    // the chip on the map is for the eye: the player says the same to a screen reader
    expect(byId(wrapper, 'radar-chip').attributes('aria-hidden')).toBe('true')
  })

  it('starts by itself once every frame is in, and pauses on the button', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await vi.waitFor(() => expect(byId(wrapper, 'radar-play').attributes('aria-label')).toBe('Pause'))
    await byId(wrapper, 'radar-play').trigger('click')
    expect(byId(wrapper, 'radar-play').attributes('aria-label')).toBe('Play')
  })

  it('does not start by itself where the system asks for less motion, and says so', async () => {
    stubMediaQueries({ reducedMotion: true })
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await new Promise(resolve => setTimeout(resolve, 600))
    expect(byId(wrapper, 'radar-play').attributes('aria-label')).toBe('Play')
    expect((byId(wrapper, 'radar-slider').element as HTMLInputElement).value).toBe('24')
    expect(byId(wrapper, 'radar-reduced-motion').exists()).toBe(true)
  })

  it('moves to a forecast frame by the slider, marks it as forecast, and puts its image on the map', async () => {
    stubMediaQueries({ reducedMotion: true })
    const answer = radarAnswer()
    framesAnswer = () => answer
    const wrapper = await mountRadar()
    await loaded(wrapper)
    const slider = byId(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '31'
    await slider.trigger('input')
    expect(byId(wrapper, 'radar-kind').text()).toBe('Forecast, 35 min ahead')
    expect(byId(wrapper, 'radar-chip').text()).toContain('Forecast, 35 min ahead')
    const frame = answer.frames[31]!
    await vi.waitFor(() => expect(stage.props.overlay.url).toBe(`/api/radar/frame?product=rv&time=${encodeURIComponent(frame.time)}&run=${encodeURIComponent(frame.run)}`))
  })
})

describe('the frame on the map and the frame of the player (M1)', () => {
  it('describes on the chip the frame whose picture is on the map, and says on the player that its own frame is loading, until it is in hand', async () => {
    stubMediaQueries({ reducedMotion: true })
    const answer = radarAnswer()
    framesAnswer = () => answer
    const target = answer.frames[31]!
    held = url => url.includes(`time=${encodeURIComponent(target.time)}&`)
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(stage.props.overlay).toBeTruthy())
    const newest = answer.frames[24]!
    const slider = byId(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '31'
    await slider.trigger('input')
    // the player is at the forecast frame, whose image is on its way: it says so, and the map still shows the newest observed one
    expect(byId(wrapper, 'radar-kind').text()).toBe('Forecast, 35 min ahead')
    expect(byId(wrapper, 'radar-frame-loading').exists()).toBe(true)
    expect(byId(wrapper, 'radar-chip').attributes('data-kind')).toBe('observation')
    expect(byId(wrapper, 'radar-chip').text()).toContain('Observed')
    expect(stage.props.overlay.url).toContain(`time=${encodeURIComponent(newest.time)}&`)
    // the image comes: the map and the chip are the player's frame
    held = () => false
    releases.forEach(release => release())
    await vi.waitFor(() => expect(stage.props.overlay.url).toContain(`time=${encodeURIComponent(target.time)}&`))
    expect(byId(wrapper, 'radar-chip').attributes('data-kind')).toBe('forecast')
    expect(byId(wrapper, 'radar-chip').text()).toContain('Forecast, 35 min ahead')
    expect(byId(wrapper, 'radar-frame-loading').exists()).toBe(false)
  })

  it('has no picture where the list has no frame', async () => {
    framesAnswer = () => ({ ...radarAnswer(), frames: [] })
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-empty').exists()).toBe(true))
    expect(stage.props.overlay).toBeNull()
    expect(byId(wrapper, 'radar-chip').exists()).toBe(false)
  })
})

describe('a new list while the reader is on a forecast frame (N1)', () => {
  /** The tab goes to the background and comes back: the list is asked for again at once (`usePolledAnswer`), as it is every 5 minutes */
  async function refresh() {
    const set = (state: 'hidden' | 'visible') => {
      Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
      document.dispatchEvent(new Event('visibilitychange'))
    }
    set('hidden')
    await new Promise(resolve => setTimeout(resolve, 10))
    set('visible')
  }

  it('keeps the picture of the forecast frame on the map, with no blank, until the frame at the same time of the new run is in, and then replaces it', async () => {
    stubMediaQueries({ reducedMotion: true })
    const first = radarAnswer({ run: '2026-11-19T21:25:00Z' })
    framesAnswer = () => first
    const wrapper = await mountRadar()
    await loaded(wrapper)
    const slider = byId(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '31'
    await slider.trigger('input')
    const before = first.frames[31]!
    await vi.waitFor(() => expect(stage.props.overlay.url).toContain(`time=${encodeURIComponent(before.time)}&run=${encodeURIComponent(before.run)}`))
    // a new run: its forecast frames are other images (new keys), and they are slow
    const second = radarAnswer({ run: '2026-11-19T21:30:00Z' })
    framesAnswer = () => second
    held = url => url.includes(`run=${encodeURIComponent('2026-11-19T21:30:00Z')}`)
    await refresh()
    await vi.waitFor(() => expect(framesAsked.length).toBeGreaterThan(0))
    await vi.waitFor(() => expect(byId(wrapper, 'radar-frame-loading').exists()).toBe(true))
    // the map has not gone blank, and still shows the picture it had, whose frame is no longer in the list
    expect(stage.props.overlay).not.toBeNull()
    expect(stage.props.overlay.url).toContain(`time=${encodeURIComponent(before.time)}&run=${encodeURIComponent(before.run)}`)
    expect(byId(wrapper, 'radar-chip').exists()).toBe(true)
    // the successor at the same time comes, and takes its place
    held = () => false
    releases.forEach(release => release())
    const after = second.frames.find(frame => frame.time === before.time)!
    await vi.waitFor(() => expect(stage.props.overlay.url).toContain(`run=${encodeURIComponent(after.run)}`))
    expect(byId(wrapper, 'radar-frame-loading').exists()).toBe(false)
  })

  it('takes the picture off where the new list has no frame at all', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    framesAnswer = () => ({ ...radarAnswer(), frames: [] })
    await refresh()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-empty').exists()).toBe(true))
    expect(stage.props.overlay).toBeNull()
    expect(byId(wrapper, 'radar-chip').exists()).toBe(false)
  })
})

describe('what is told while the frames load (M2)', () => {
  it('has a counter that is no live region, and one live line that says it once at the start and once at the end', async () => {
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-frames-live').text()).not.toBe(''))
    const live = byId(wrapper, 'radar-frames-live')
    expect(live.attributes('role')).toBe('status')
    const said: string[] = [live.text()]
    const watching = setInterval(() => said.push(live.text()), 2)
    await loaded(wrapper)
    clearInterval(watching)
    // the last line too, which the 2 ms sampling misses when the frames load between two of its ticks
    said.push(live.text())
    expect(live.text()).toBe('The radar frames are loaded.')
    // told twice and never the count: "Loading the radar frames …", then "The radar frames are loaded."
    expect([...new Set(said)].filter(line => line !== '')).toEqual(['Loading the radar frames …', 'The radar frames are loaded.'])
    expect(wrapper.find('[data-testid="radar-frames-loading"]').exists()).toBe(false)
  })

  it('says a failure, not "loaded", where none of the frames came (N3)', async () => {
    failing = () => true
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-frames-live').text()).toBe('None of the radar frames could be loaded.'), { timeout: 13_000 })
  })

  it('has the visible counter without a role, so that its 49 changes are not announced', async () => {
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-frames-loading').exists()).toBe(true))
    expect(byId(wrapper, 'radar-frames-loading').attributes('role')).toBeUndefined()
  })
})

describe('the legend, the credit and the note', () => {
  it('has the legend of the answer in mm/h, with numbers', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    const legend = byId(wrapper, 'radar-legend')
    expect(legend.find('h2').text()).toBe('Precipitation rate in mm/h')
    expect(legend.findAll('[data-testid="radar-legend-class"]')).toHaveLength(7)
    expect(legend.text()).toContain('0.1–0.5')
    expect(legend.text()).toContain('25+')
  })

  it('has the credit line of DWD and its licence from the answer, and under it what wetterdienst did to the frames', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    const credit = byId(wrapper, 'radar-credit')
    expect(credit.text()).toContain('Radar: RV composite of the German Weather Service (DWD).')
    expect(credit.text()).toContain('Source: Deutscher Wetterdienst.')
    const link = credit.find('a')
    expect(link.text()).toBe('Creative Commons Attribution 4.0 International')
    expect(link.attributes('href')).toBe('https://creativecommons.org/licenses/by/4.0/')
    const note = credit.find('[data-testid="processing-note"]')
    expect(note.text()).toContain('Processed by wetterdienst')
    expect(note.text()).toContain('Each frame is DWD\'s RV composite')
  })

  it('gives the map the credit of the radar, with the licence as a link to its terms', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(stage.props.credits).toEqual([{ text: 'Source: Deutscher Wetterdienst', license: { label: 'CC-BY-4.0', url: 'https://creativecommons.org/licenses/by/4.0/' } }])
  })

  it('has an About text in plain words that names its sources', async () => {
    const wrapper = await mountRadar()
    // the About panel is opened by its button
    expect(wrapper.find('[data-testid="radar-sources"]').exists()).toBe(false)
    await wrapper.findAll('button').find(button => button.text() === 'About radar')!.trigger('click')
    const about = wrapper.find('[data-testid="radar-sources"]')
    expect(about.exists()).toBe(true)
    expect(about.text()).toContain('WMO-No. 8')
    expect(about.text()).toContain('Volume III, Chapter 7')
    expect(about.find('a').attributes('href')).toBe('https://www.dwd.de/EN/ourservices/radar_products/radar_products.html')
    expect(text(wrapper)).toContain('The forecast is no weather model')
  })
})

describe('when the radar is old or fails', () => {
  it('says so when DWD\'s newest run is over 20 minutes old, and still shows the loop', async () => {
    framesAnswer = () => radarAnswer({ run: runTime(Date.now(), 30), warnings: [{ code: 'radar-stale', message: 'old' }] })
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(byId(wrapper, 'radar-stale').text()).toContain('more than 20 minutes old')
    expect(stage.props.overlay).not.toBeNull()
  })

  it('says nothing of staleness for a fresh run', async () => {
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(byId(wrapper, 'radar-stale').exists()).toBe(false)
  })

  it('tells a list that could not be loaded, with a Retry that asks again', async () => {
    framesStatus = 502
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-failed').exists()).toBe(true))
    expect(byId(wrapper, 'radar-failed').attributes('role')).toBe('alert')
    expect(stage.props.overlay).toBeNull()
    framesStatus = 200
    await byId(wrapper, 'radar-retry').trigger('click')
    await loaded(wrapper)
    expect(byId(wrapper, 'radar-failed').exists()).toBe(false)
  })

  it('says there are no frames where DWD has published none', async () => {
    framesAnswer = () => radarAnswer({ past: 0, forecast: 0, run: runTime() })
    // a list with no frame at all
    framesAnswer = () => ({ ...radarAnswer(), frames: [] })
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-empty').exists()).toBe(true))
    expect(byId(wrapper, 'radar-play').attributes('disabled')).toBeDefined()
  })
})

describe('the cells and the frame (the cells are the latest scan\'s)', () => {
  it('shows the cells on the newest observed frame, which is within 15 minutes of the scan, with no note', async () => {
    cellsScan = () => exampleScan()
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(stage.props.cells).toHaveLength(4))
    await vi.waitFor(() => expect(stage.props.overlay).toBeTruthy())
    expect(stage.props.cellsFaded).toBe(false)
    expect(wrapper.find('[data-testid="radar-cells-faded"]').exists()).toBe(false)
  })

  it('fades them out on a frame of the forecast, with a note and without their credit, and shows them again on the frame they are for', async () => {
    stubMediaQueries({ reducedMotion: true })
    cellsScan = () => exampleScan()
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await vi.waitFor(() => expect(stage.props.cells).toHaveLength(4))
    const slider = byId(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '30'
    await slider.trigger('input')
    await vi.waitFor(() => expect(stage.props.cellsFaded).toBe(true))
    // the cells are still the map's (they fade, they are not taken away), and the note and the list say what is so
    expect(stage.props.cells).toHaveLength(4)
    expect(byId(wrapper, 'radar-cells-faded').text()).toMatch(/^The cells are hidden on this frame: they are from the scan of \d{2}:\d{2} \S+, and are shown only on frames within 15 minutes of it\.$/)
    expect(wrapper.findAll('[data-testid="radar-cells-item"]')).toHaveLength(4)
    ;(slider.element as HTMLInputElement).value = '24'
    await slider.trigger('input')
    await vi.waitFor(() => expect(stage.props.cellsFaded).toBe(false))
    expect(wrapper.find('[data-testid="radar-cells-faded"]').exists()).toBe(false)
  })

  it('fades them out on an observed frame more than 15 minutes older than the scan', async () => {
    stubMediaQueries({ reducedMotion: true })
    cellsScan = () => exampleScan()
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await vi.waitFor(() => expect(stage.props.cells).toHaveLength(4))
    const slider = byId(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '10'
    await slider.trigger('input')
    await vi.waitFor(() => expect(stage.props.cellsFaded).toBe(true))
  })
})

describe('a backend that has no radar (L4)', () => {
  it.each([404, 501])('says so for a %s, plainly, and has no Retry (it would not help)', async (status) => {
    framesStatus = status
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-unavailable').exists()).toBe(true))
    expect(byId(wrapper, 'radar-unavailable').text()).toBe('The radar is not available on this server.')
    expect(byId(wrapper, 'radar-unavailable').attributes('role')).toBe('alert')
    expect(wrapper.find('[data-testid="radar-retry"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="radar-failed"]').exists()).toBe(false)
  })
})

describe('the thunderstorm cells on top', () => {
  it('asks for the latest scan without the forecast track, and draws the cells on the map with their credit', async () => {
    cellsScan = () => exampleScan()
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(stage.props.cells).toHaveLength(4))
    expect(cellsAsked).toEqual([{ track: 'false' }])
    // DWD's, under the same terms: one line for the radar and the cells, with no product codes
    expect(stage.props.credits).toEqual([{ text: 'Source: Deutscher Wetterdienst', license: { label: 'CC-BY-4.0', url: 'https://creativecommons.org/licenses/by/4.0/' } }])
    expect(byId(wrapper, 'radar-cells-summary').text()).toBe('Thunderstorm cells in the latest scan: 4')
    expect(wrapper.findAll('[data-testid="radar-cells-item"]')).toHaveLength(4)
  })

  it('has a scan with no cell, the usual one, say so and draw none', async () => {
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(stage.props.cells).toEqual([]))
    expect(byId(wrapper, 'radar-cells-summary').text()).toBe('No thunderstorm cells in the latest scan')
  })

  it('centres the map on a cell of the list, once for each press, and says so', async () => {
    cellsScan = () => exampleScan()
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(wrapper.findAll('[data-testid="radar-cells-entry"]')).toHaveLength(4))
    expect(stage.props.centreOn).toBeNull()
    // the most severe first: cell 12, at 51.3 N, 12.4 E
    await wrapper.findAll('[data-testid="radar-cells-entry"]')[0]!.trigger('click')
    expect(stage.props.centreOn).toMatchObject({ count: 1, latitude: 51.3, longitude: 12.4 })
    expect(byId(wrapper, 'radar-panel-announcement').text()).toBe('Map centred on cell 12')
    await wrapper.findAll('[data-testid="radar-cells-entry"]')[1]!.trigger('click')
    expect(stage.props.centreOn.count).toBe(2)
  })

  it('does not draw the cells of a scan that is over 20 minutes old, and lists them with the note', async () => {
    cellsScan = () => exampleScan('2026-11-17T22:15:00.000000+00:00')
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-cells-outdated').exists()).toBe(true))
    expect(stage.props.cells).toBeUndefined()
    expect(wrapper.findAll('[data-testid="radar-cells-item"]')).toHaveLength(4)
  })

  it('stops asking for them and draws none with the switch off, and asks again when it is turned on', async () => {
    cellsScan = () => exampleScan()
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(stage.props.cells).toHaveLength(4))
    const control = byId(wrapper, 'radar-cells-switch')
    expect(control.attributes('role')).toBe('switch')
    expect(control.attributes('aria-checked')).toBe('true')
    await control.trigger('click')
    await vi.waitFor(() => expect(stage.props.cells).toBeUndefined())
    expect(byId(wrapper, 'radar-cells-list').exists()).toBe(false)
    const asked = cellsAsked.length
    await control.trigger('click')
    await vi.waitFor(() => expect(stage.props.cells).toHaveLength(4))
    expect(cellsAsked.length).toBeGreaterThan(asked)
  })

  it('says the cells are the latest scan\'s, whichever frame is shown', async () => {
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-cells-loop-note').exists()).toBe(true))
    expect(byId(wrapper, 'radar-cells-loop-note').text()).toContain('The cells are those of the latest scan.')
  })
})

describe('the order of the map and the panel', () => {
  it('has the panel first beside the map on a wide window, and the map first on a phone, in the order the window shows them', async () => {
    const wide = await mountRadar()
    const order = (wrapper: Wrapper) => wrapper.findAll('[data-testid="radar-panel"], [data-testid="radar-stage"]').map(part => part.attributes('data-testid'))
    expect(order(wide)).toEqual(['radar-panel', 'radar-stage'])
    wide.unmount()
    stubMediaQueries({ wide: false })
    const narrow = await mountRadar()
    expect(order(narrow)).toEqual(['radar-stage', 'radar-panel'])
  })
})

// The reader's own position on the radar (GH-4287): the map tool's "Use my location", whose position the map marks and centres on, with a
// way to hide the marker. The position goes to no request: the radar is the same for everyone. The browser's APIs are mocks.

/** The browser answers `fix` to the Geolocation API (each ask counted); its permission is `prompt` */
function mockBrowser(fix = { latitude: 51.3412, longitude: 12.3747 }) {
  const getCurrentPosition = vi.fn((success: (position: unknown) => void) => success({ coords: fix }))
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query: vi.fn(async () => ({ state: 'prompt' })) } })
  return getCurrentPosition
}
const press = (wrapper: Wrapper) => byId(wrapper, 'use-my-location-button').trigger('click')
const toggle = (wrapper: Wrapper) => byId(wrapper, 'radar-position-toggle')
const status = (wrapper: Wrapper) => byId(wrapper, 'use-my-location-status')

describe('the reader\'s own position', () => {
  it('is asked of nobody until the button is pressed: nothing is marked, the browser is not asked, and the map has no position', async () => {
    const getCurrentPosition = mockBrowser()
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(byId(wrapper, 'use-my-location-button').text()).toBe('Use my location')
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(stage.props.position).toBeNull()
    expect(stage.props.locate).toBe(0)
    expect(toggle(wrapper).exists()).toBe(false)
    // the map's mark has a name, which says what it is
    expect(stage.props.positionLabel).toBe('Your position, rounded to about 1 km')
  })

  it('marks the position rounded to about 1 km and has the map centre on it once for each press', async () => {
    const getCurrentPosition = mockBrowser()
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 51.34, longitude: 12.37 }))
    expect(getCurrentPosition).toHaveBeenCalledTimes(1)
    expect(stage.props.locate).toBe(1)
    expect(status(wrapper).text()).toBe('Your position is marked on the map, at about 51.34, 12.37.')
    await press(wrapper)
    await vi.waitFor(() => expect(stage.props.locate).toBe(2))
  })

  it('has the note of the radar: the position is only shown, no station is looked up', async () => {
    mockBrowser()
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(byId(wrapper, 'use-my-location-note').exists()).toBe(true))
    expect(byId(wrapper, 'use-my-location-note').text()).toContain('used only to show your position on the map')
    expect(byId(wrapper, 'use-my-location-note').text()).not.toContain('nearest station')
  })

  it('can be hidden and shown again, which does not move the map, and a press shows it again', async () => {
    mockBrowser()
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(toggle(wrapper).exists()).toBe(true))
    expect(toggle(wrapper).text()).toBe('Hide my position on the map')
    await toggle(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.position).toBeNull())
    expect(toggle(wrapper).text()).toBe('Show my position on the map')
    expect(status(wrapper).text()).toBe('Your position is hidden on the map.')
    await toggle(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 51.34, longitude: 12.37 }))
    // the count of the presses is the one thing that moves the map
    expect(stage.props.locate).toBe(1)
    await toggle(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.position).toBeNull())
    await press(wrapper)
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 51.34, longitude: 12.37 }))
    expect(stage.props.locate).toBe(2)
  })

  it('is told where it is outside the area of the radar, and then neither marked nor centred on, with nothing to hide', async () => {
    // Madrid: the box of the answer is 45.68 to 56.22 N, 1.46 to 18.73 E
    mockBrowser({ latitude: 40.4168, longitude: -3.7038 })
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(status(wrapper).text()).toBe('Your position is outside the radar picture, so the map stays where it is.'))
    expect(stage.props.position).toBeNull()
    expect(toggle(wrapper).exists()).toBe(false)
  })

  it('shows a remembered position on a press without asking the browser again, and shows none before it', async () => {
    const getCurrentPosition = mockBrowser()
    localStorage.setItem('wd-location', JSON.stringify({ latitude: 48.14, longitude: 11.58 }))
    const wrapper = await mountRadar()
    await loaded(wrapper)
    // remembered, but not shown: it is shown on a press
    expect(stage.props.position).toBeNull()
    expect(byId(wrapper, 'use-my-location-stored').exists()).toBe(true)
    expect(byId(wrapper, 'use-my-location-remember').exists()).toBe(false)
    await press(wrapper)
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 48.14, longitude: 11.58 }))
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(stage.props.locate).toBe(1)
  })

  it('is forgotten with "Forget": the marker goes with the position, and so does the way to hide it', async () => {
    mockBrowser()
    localStorage.setItem('wd-location', JSON.stringify({ latitude: 48.14, longitude: 11.58 }))
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(stage.props.position).not.toBeNull())
    await byId(wrapper, 'use-my-location-stored').trigger('click')
    await vi.waitFor(() => expect(document.body.querySelector('[data-testid="use-my-location-forget"]')).not.toBeNull())
    document.body.querySelector<HTMLButtonElement>('[data-testid="use-my-location-forget"]')!.click()
    await vi.waitFor(() => expect(stage.props.position).toBeNull())
    expect(toggle(wrapper).exists()).toBe(false)
    expect(localStorage.getItem('wd-location')).toBeNull()
    expect(status(wrapper).text()).toBe('')
  })

  it('tells a refusal in an alert, and marks nothing', async () => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (_ok: unknown, fail: (error: unknown) => void) => fail({ code: 1 }) } })
    Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query: vi.fn(async () => ({ state: 'prompt' })) } })
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(byId(wrapper, 'use-my-location-problem').exists()).toBe(true))
    expect(byId(wrapper, 'use-my-location-problem').attributes('role')).toBe('alert')
    expect(stage.props.position).toBeNull()
    expect(stage.props.locate).toBe(0)
  })

  it('goes to no request: not the list of the frames, the cells, a frame, nor any other', async () => {
    cellsScan = () => exampleScan()
    mockBrowser()
    const everything: string[] = []
    const fetchBefore = globalThis.fetch
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      everything.push(`${String(input instanceof Request ? input.url : input)} ${typeof init?.body === 'string' ? init.body : ''}`)
      return fetchBefore(input, init)
    }) as typeof fetch
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(stage.props.position).not.toBeNull())
    const asked = [...framesAsked, ...cellsAsked].map(query => JSON.stringify(query))
    expect(asked.length).toBeGreaterThan(0)
    expect(everything.length).toBeGreaterThan(0)
    for (const request of [...asked, ...imagesAsked, ...everything])
      expect(request, request).not.toMatch(/latitude|longitude|lat=|lon=|51\.34|12\.37/)
    for (const query of [...framesAsked, ...cellsAsked])
      expect(Object.keys(query).filter(key => /lat|lon|position/i.test(key))).toEqual([])
    expect(location.href).not.toMatch(/51\.34|12\.37|latitude/)
  })
})

describe('the position before the radar has answered', () => {
  const scrolled = vi.fn()
  const realScroll = Element.prototype.scrollIntoView
  beforeEach(() => {
    scrolled.mockClear()
    Element.prototype.scrollIntoView = scrolled
  })
  afterEach(() => {
    Element.prototype.scrollIntoView = realScroll
  })

  /** The list of the frames is held until the test lets it go */
  function holdFrames() {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    framesAnswer = () => held.then(() => radarAnswer())
    return release
  }

  it('is neither marked, nor centred on, nor scrolled to while the box of the radar is not known, and is when it turns out to be inside', async () => {
    stubMediaQueries({ wide: false })
    const release = holdFrames()
    mockBrowser()
    const wrapper = await mountRadar()
    await press(wrapper)
    await vi.waitFor(() => expect(byId(wrapper, 'use-my-location-note').exists()).toBe(true))
    expect(stage.props.position).toBeNull()
    expect(stage.props.locate).toBe(0)
    expect(toggle(wrapper).exists()).toBe(false)
    expect(scrolled).not.toHaveBeenCalled()
    // the wait is told once it is noticeable
    await vi.waitFor(() => expect(status(wrapper).text()).toBe('Waiting for the radar picture to check where your position lies …'), { timeout: 3000 })
    release()
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 51.34, longitude: 12.37 }))
    expect(stage.props.locate).toBe(1)
    expect(status(wrapper).text()).toBe('Your position is marked on the map, at about 51.34, 12.37.')
    await vi.waitFor(() => expect(scrolled).toHaveBeenCalledTimes(1))
    expect(toggle(wrapper).exists()).toBe(true)
    // the map is centred once, on the press, and no later change of the list centres it again
    expect(stage.props.locate).toBe(1)
  })

  it('leaves the map where it is, and says so truthfully, when it turns out to be outside', async () => {
    stubMediaQueries({ wide: false })
    const release = holdFrames()
    mockBrowser({ latitude: 40.4168, longitude: -3.7038 })
    const wrapper = await mountRadar()
    await press(wrapper)
    await vi.waitFor(() => expect(byId(wrapper, 'use-my-location-note').exists()).toBe(true))
    expect(stage.props.position).toBeNull()
    expect(stage.props.locate).toBe(0)
    release()
    await vi.waitFor(() => expect(status(wrapper).text()).toBe('Your position is outside the radar picture, so the map stays where it is.'))
    expect(stage.props.position).toBeNull()
    expect(stage.props.locate).toBe(0)
    expect(scrolled).not.toHaveBeenCalled()
    expect(toggle(wrapper).exists()).toBe(false)
  })

  it('says there is no radar to compare with, and neither marks nor centres, where the server has no radar', async () => {
    framesStatus = 404
    mockBrowser()
    const wrapper = await mountRadar()
    await vi.waitFor(() => expect(byId(wrapper, 'radar-unavailable').exists()).toBe(true))
    await press(wrapper)
    await vi.waitFor(() => expect(status(wrapper).text()).toBe('There is no radar picture to check your position against, so the map stays where it is.'))
    expect(stage.props.position).toBeNull()
    expect(stage.props.locate).toBe(0)
    expect(toggle(wrapper).exists()).toBe(false)
  })

  it('is centred on by the press alone: a position that was outside is marked, not centred on, when a later list has a box that holds it', async () => {
    mockBrowser({ latitude: 40.4168, longitude: -3.7038 })
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(status(wrapper).text()).toBe('Your position is outside the radar picture, so the map stays where it is.'))
    // the next list has a box that reaches Madrid
    const wider = radarAnswer()
    wider.image.bounds = { west: -10, south: 36, east: 19, north: 57 }
    framesAnswer = () => wider
    ;(wrapper.vm as any).radar.retry()
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 40.42, longitude: -3.7 }))
    expect(stage.props.locate).toBe(0)
  })

  it('moves the focus to "Use my location" when the hide button goes with the position', async () => {
    mockBrowser()
    localStorage.setItem('wd-location', JSON.stringify({ latitude: 48.14, longitude: 11.58 }))
    const wrapper = await mountRadar()
    await loaded(wrapper)
    await press(wrapper)
    await vi.waitFor(() => expect(toggle(wrapper).exists()).toBe(true))
    ;(toggle(wrapper).element as HTMLElement).focus()
    expect(document.activeElement).toBe(toggle(wrapper).element)
    // the box of the next list leaves the position outside
    const away = radarAnswer()
    away.image.bounds = { west: 1, south: 50, east: 5, north: 55 }
    framesAnswer = () => away
    ;(wrapper.vm as any).radar.retry()
    await vi.waitFor(() => expect(toggle(wrapper).exists()).toBe(false))
    await vi.waitFor(() => expect(document.activeElement).toBe(byId(wrapper, 'use-my-location-button').element))
  })
})

describe('the box that keeps the position, on the radar', () => {
  it('is offered only after a press on the radar, not for a position that came from another page this visit', async () => {
    mockBrowser()
    // the position of another page: in hand, not stored
    useState<{ latitude: number, longitude: number } | null>('wd-location-position', () => null).value = { latitude: 52.52, longitude: 13.4 }
    const wrapper = await mountRadar()
    await loaded(wrapper)
    expect(byId(wrapper, 'use-my-location-remember').exists()).toBe(false)
    expect(byId(wrapper, 'use-my-location-note').exists()).toBe(false)
    expect(stage.props.position).toBeNull()
    await press(wrapper)
    await vi.waitFor(() => expect(byId(wrapper, 'use-my-location-remember').exists()).toBe(true))
    expect(byId(wrapper, 'use-my-location-note').exists()).toBe(true)
  })
})
