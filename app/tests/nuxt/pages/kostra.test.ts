import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData, clearNuxtState, useRouter } from '#imports'
import KostraChart from '~/components/KostraChart.vue'
import PlaceField from '~/components/PlaceField.vue'
import UseMyLocation from '~/components/UseMyLocation.vue'
import KostraPage from '~/pages/kostra.vue'
import { cellCorners, KOSTRA_DURATIONS } from '~/utils/kostra'
import { depthOf, kostraAnswer, OUTSIDE_PROBLEM } from '../../helpers/kostra-answer'
import { providersAnswer } from '../fixtures/providers'
import { LOCATION_STATE } from '../fixtures/state'

// The Heavy-rainfall tool (GH-4500): the point of the link, the answer for it, the table, the chart, the 5 km cell on the map and the words
// for a point outside DWD's grid. The map itself (Leaflet, which draws nothing in the test's document) is a stand-in that takes the props the
// real one takes and raises the events it raises; the chart's library is a recorder.

const { stage } = vi.hoisted(() => ({ stage: { props: {} as Record<string, any>, emit: null as null | ((event: string, ...args: any[]) => void), mounts: 0 } }))
vi.mock('~/components/StationMap.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    __esModule: true,
    default: defineComponent({
      props: { stations: Array, selected: null, place: null, label: String, noFullscreen: Boolean, position: null, positionLabel: String, box: null, goTo: null },
      emits: ['pick', 'view'],
      setup(props, { emit }) {
        stage.props = props
        stage.emit = emit as any
        stage.mounts++
        return () => h('div', { 'data-testid': 'station-map', 'role': 'application', 'aria-label': props.label })
      },
    }),
  }
})
vi.mock('~/utils/echarts-loader', () => {
  const chart = { on: vi.fn(), resize: vi.fn(), setOption: vi.fn(), getDom: vi.fn(), dispose: vi.fn() }
  return { loadEcharts: () => ({ init: () => chart }) }
})

const { toastAdd } = vi.hoisted(() => ({ toastAdd: vi.fn() }))
mockNuxtImport('useToast', () => () => ({ add: toastAdd, clear: vi.fn() }))

const ZINNWALD = { lat: '50.7313', lon: '13.7516' }
const asked: Array<Record<string, string>> = []
let respond: (query: Record<string, string>) => unknown = () => kostraAnswer()
let status = 200
registerEndpoint('/api/kostra', (event) => {
  const query = getQuery(event) as Record<string, string>
  asked.push(query)
  const body = respond(query)
  if (status !== 200)
    setResponseStatus(event, status)
  return body
})
registerEndpoint('/api/providers', () => providersAnswer())

const mounted: Array<{ unmount: () => void }> = []
async function mountKostra(query = '') {
  const wrapper = await mountSuspended(KostraPage, { route: `/kostra${query}`, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
type Wrapper = Awaited<ReturnType<typeof mountKostra>>
const byId = (wrapper: Wrapper, id: string) => wrapper.find(`[data-testid="${id}"]`)
const text = (wrapper: Wrapper) => wrapper.text().replace(/\s+/g, ' ')
const queryOfRoute = () => useRouter().currentRoute.value.query
/** The map is loaded apart from the page (an async component in a client-only slot): its events are there once it is mounted */
const mapReady = () => vi.waitFor(() => expect(stage.emit).not.toBeNull(), { timeout: 5000 })
const shown = (wrapper: Wrapper) => vi.waitFor(() => expect(byId(wrapper, 'kostra-table').exists()).toBe(true), { timeout: 5000 })

/** A gate: an answer that is held until the test lets it go (a timer is no way to order two answers) */
function gate() {
  let open!: () => void
  const promise = new Promise<void>((resolve) => {
    open = resolve
  })
  return { promise, open }
}

beforeEach(() => {
  toastAdd.mockClear()
})

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  stage.props = {}
  stage.emit = null
  stage.mounts = 0
  asked.length = 0
  respond = () => kostraAnswer()
  status = 200
  clearNuxtData()
  clearNuxtState(LOCATION_STATE)
  delete (navigator as any).geolocation
  delete (navigator as any).permissions
})

describe('the page with no point', () => {
  it('is a page of its own: a title, what it is for, the point\'s panel and the map, and asks the backend for nothing', async () => {
    const wrapper = await mountKostra()
    expect(wrapper.find('h1').text()).toBe('Heavy rainfall')
    expect(text(wrapper)).toContain('DWD\'s design rainfall (KOSTRA) for a point in Germany')
    await vi.waitFor(() => expect(byId(wrapper, 'station-map').exists()).toBe(true))
    expect(stage.props.stations).toEqual([])
    expect(stage.props.noFullscreen).toBe(true)
    expect(stage.props.position).toBeNull()
    expect(stage.props.box).toBeNull()
    expect(asked).toEqual([])
  })

  it('shows the placeholder of the tool where the answer will be, with its own tile', async () => {
    const wrapper = await mountKostra()
    const placeholder = byId(wrapper, 'tool-placeholder')
    expect(placeholder.attributes('data-tool')).toBe('kostra')
    expect(placeholder.find('.tile').classes()).toContain('tile-lime')
    expect(byId(wrapper, 'kostra-table').exists()).toBe(false)
  })

  it('takes a point three ways: the name of a place, "Use my location" and a click on the map, and says so', async () => {
    const wrapper = await mountKostra()
    expect(wrapper.findComponent(PlaceField).exists()).toBe(true)
    expect(wrapper.findComponent(UseMyLocation).exists()).toBe(true)
    expect(wrapper.findComponent(UseMyLocation).props('use')).toBe('kostra')
    expect(byId(wrapper, 'kostra-map-hint').text()).toBe('Or click the map to choose a point.')
  })

  it.each([
    ['half a point', '?lat=50.7'],
    ['text', '?lat=north&lon=east'],
    ['a latitude beyond the globe', '?lat=91&lon=13'],
  ])('is the same for a link with %s: no request, the placeholder', async (_what, query) => {
    const wrapper = await mountKostra(query)
    expect(byId(wrapper, 'tool-placeholder').exists()).toBe(true)
    expect(asked).toEqual([])
  })
})

describe('the point of the link', () => {
  it('is asked for as it is written, with no duration and no return period, which gives the whole table', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    expect(asked).toEqual([{ latitude: '50.7313', longitude: '13.7516' }])
  })

  it('is on the map: the ring at the point, and the cell of DWD\'s grid outlined round the centre the answer gives, where the map opens', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    expect(stage.props.position).toEqual({ latitude: 50.7313, longitude: 13.7516 })
    expect(stage.props.positionLabel).toBe('Chosen point')
    expect(stage.props.box).toEqual(cellCorners({ latitude: 50.747211, longitude: 13.777738 }))
    expect(stage.props.box).toHaveLength(4)
    expect(stage.props.goTo).toMatchObject({ latitude: 50.7313, longitude: 13.7516, count: 1, zoom: 11 })
  })

  it('says which cell it is and where its centre is, and that the point is the link\'s', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    expect(byId(wrapper, 'kostra-cell').text()).toBe('DWD grid cell 144197, centre 50.7472, 13.7777')
    expect(byId(wrapper, 'kostra-point').text()).toBe('Chosen point: 50.7313, 13.7516')
  })

  it('goes round: a click on the map writes its point to the link, to four decimals, and the answer is asked for that point', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    stage.emit!('pick', { latitude: 52.520008, longitude: 13.404954, tolerance: 1, tap: 1, disc: 1 })
    await vi.waitFor(() => expect(queryOfRoute()).toMatchObject({ lat: '52.52', lon: '13.405' }))
    await vi.waitFor(() => expect(asked.at(-1)).toEqual({ latitude: '52.52', longitude: '13.405' }))
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 52.52, longitude: 13.405 }))
    expect(byId(wrapper, 'kostra-point').text()).toBe('Chosen point: On the map: 52.5200, 13.4050')
  })

  it('keeps what else the link says, and replaces the entry of the history instead of adding one', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}&lang=en`)
    await shown(wrapper)
    const length = history.length
    stage.emit!('pick', { latitude: 48.137, longitude: 11.575, tolerance: 1, tap: 1, disc: 1 })
    await vi.waitFor(() => expect(queryOfRoute().lat).toBe('48.137'))
    expect(queryOfRoute().lang).toBe('en')
    expect(history.length).toBe(length)
  })

  it('is asked for once for a link that changes in another way, not again for the same point', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    await useRouter().replace({ query: { ...queryOfRoute(), other: '1' } })
    await wrapper.vm.$nextTick()
    expect(asked).toHaveLength(1)
  })

  it('follows the link where it changes under the page (the back button): the point and the answer of the other point', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    await useRouter().replace({ query: { lat: '53.55', lon: '9.99' } })
    await vi.waitFor(() => expect(asked.at(-1)).toEqual({ latitude: '53.55', longitude: '9.99' }))
    expect(stage.props.position).toEqual({ latitude: 53.55, longitude: 9.99 })
    await useRouter().replace({ query: {} })
    await vi.waitFor(() => expect(byId(wrapper, 'tool-placeholder').exists()).toBe(true))
    expect(stage.props.box).toBeNull()
  })
})

describe('choosing a point', () => {
  it('by the name of a place: its point goes to the link, the map goes to it, and the panel says the place', async () => {
    const wrapper = await mountKostra()
    wrapper.findComponent(PlaceField).vm.$emit('pick', { id: 'N1', name: 'Dresden', kind: 'city', region: 'Saxony, Germany', latitude: 51.0493286, longitude: 13.7381437 })
    await vi.waitFor(() => expect(queryOfRoute()).toMatchObject({ lat: '51.0493', lon: '13.7381' }))
    await shown(wrapper)
    expect(asked).toEqual([{ latitude: '51.0493', longitude: '13.7381' }])
    expect(byId(wrapper, 'kostra-point').text()).toBe('Chosen point: Dresden, Saxony, Germany (51.0493, 13.7381)')
    expect(stage.props.goTo).toMatchObject({ latitude: 51.0493, longitude: 13.7381, zoom: 11 })
  })

  it('by "Use my location": the position (rounded by the browser) goes to the link, the map goes to it, and the status says so', async () => {
    const wrapper = await mountKostra()
    wrapper.findComponent(UseMyLocation).vm.$emit('position', { latitude: 50.73, longitude: 13.75 })
    await vi.waitFor(() => expect(queryOfRoute()).toMatchObject({ lat: '50.73', lon: '13.75' }))
    await shown(wrapper)
    expect(wrapper.findComponent(UseMyLocation).props('status')).toBe('Your position is the point now.')
    expect(byId(wrapper, 'kostra-point').text()).toBe('Chosen point: Your position, rounded: 50.7300, 13.7500')
    expect(stage.props.goTo).toMatchObject({ latitude: 50.73, longitude: 13.75 })
  })

  it('by a click: the status of the position is gone, since the point is no longer it', async () => {
    const wrapper = await mountKostra()
    wrapper.findComponent(UseMyLocation).vm.$emit('position', { latitude: 50.73, longitude: 13.75 })
    await shown(wrapper)
    stage.emit!('pick', { latitude: 53.55, longitude: 9.99, tolerance: 1, tap: 1, disc: 1 })
    await vi.waitFor(() => expect(wrapper.findComponent(UseMyLocation).props('status')).toBe(''))
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-point').text()).toBe('Chosen point: On the map: 53.5500, 9.9900'))
  })

  it('by a click far out on the map: the map comes in to where the 5 km cell is seen; nearer in it stays where it is', async () => {
    const wrapper = await mountKostra()
    await mapReady()
    stage.emit!('view', { latitude: 51.2, longitude: 10.4, zoom: 6 })
    stage.emit!('pick', { latitude: 53.55, longitude: 9.99, tolerance: 1, tap: 1, disc: 1 })
    await vi.waitFor(() => expect(stage.props.goTo).toMatchObject({ latitude: 53.55, longitude: 9.99, zoom: 9, count: 1 }))
    await shown(wrapper)
    stage.emit!('view', { latitude: 53.55, longitude: 9.99, zoom: 10 })
    stage.emit!('pick', { latitude: 53.56, longitude: 9.98, tolerance: 1, tap: 1, disc: 1 })
    await vi.waitFor(() => expect(queryOfRoute().lat).toBe('53.56'))
    expect(stage.props.goTo.count).toBe(1)
  })
})

describe('the answer', () => {
  it('says it is on its way while the table is read, in a status, and takes the old table away', async () => {
    const held = gate()
    respond = () => held.promise.then(() => kostraAnswer())
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-loading').exists()).toBe(true))
    expect(byId(wrapper, 'kostra-loading').attributes('role')).toBe('status')
    expect(byId(wrapper, 'kostra-loading').text()).toContain('the first request takes a few seconds')
    expect(byId(wrapper, 'kostra-result').attributes('aria-busy')).toBe('true')
    expect(byId(wrapper, 'kostra-table').exists()).toBe(false)
    held.open()
    await shown(wrapper)
    expect(byId(wrapper, 'kostra-loading').exists()).toBe(false)
    expect(byId(wrapper, 'kostra-result').attributes('aria-busy')).toBe('false')
  })

  it('is the answer of the point last chosen: an answer that comes late for an earlier point reaches nothing', async () => {
    const first = gate()
    const cells = {
      first: { index_rc: '144197', row: 144, column: 197, latitude: 50.747211, longitude: 13.777738 },
      second: { index_rc: '083144', row: 83, column: 144, latitude: 53.550184, longitude: 10.022628 },
    }
    respond = query => query.latitude === ZINNWALD.lat ? first.promise.then(() => kostraAnswer({ cell: cells.first })) : kostraAnswer({ cell: cells.second })
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await vi.waitFor(() => expect(asked).toHaveLength(1))
    await mapReady()
    stage.emit!('pick', { latitude: 53.55, longitude: 9.99, tolerance: 1, tap: 1, disc: 1 })
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-cell').text()).toContain('083144'))
    first.open()
    // the held answer is released: it has nothing to settle
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(byId(wrapper, 'kostra-cell').text()).toContain('083144')
    expect(stage.props.box).toEqual(cellCorners({ latitude: 53.550184, longitude: 10.022628 }))
  })

  it('is the table of 22 durations by 9 return periods, with the depth in mm and DWD\'s uncertainty, and the curves above it', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    expect(wrapper.findAll('[data-testid="kostra-table"] tbody tr')).toHaveLength(22)
    expect(wrapper.findAll('[data-testid="kostra-table"] thead th[data-years]')).toHaveLength(9)
    const cell = wrapper.find('tr[data-minutes="60"] td[data-years="100"]')
    expect(cell.find('.kostra-value').text()).toBe(depthOf(60, 100).toFixed(1))
    expect(cell.find('.kostra-uncertainty').text()).toContain('±12 %')
    expect(wrapper.findComponent(KostraChart).exists()).toBe(true)
    // the curves come before the table in the page
    const html = wrapper.html()
    expect(html.indexOf('data-testid="kostra-chart"')).toBeLessThan(html.indexOf('data-testid="kostra-table-scroll"'))
  })

  it('says that the values are DWD\'s estimates for the cell and no measurements at the point, and what the numbers under them are', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    expect(byId(wrapper, 'kostra-estimate').text()).toBe('These values are DWD\'s estimates for the 5 km cell that holds the point, not measurements at the point.')
    expect(byId(wrapper, 'kostra-uncertainty-note').text()).toContain('DWD\'s uncertainty in plus-minus percent')
    // and the chart is described by that sentence
    expect(byId(wrapper, 'kostra-stage').attributes('aria-describedby')).toBe(byId(wrapper, 'kostra-estimate').attributes('id'))
  })

  it('credits DWD with the licence of the answer\'s own terms, and says what wetterdienst did to the data', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    const credit = byId(wrapper, 'kostra-credit')
    expect(credit.find('[data-testid="provider-credit-line"]').text()).toContain('Source: Deutscher Wetterdienst')
    expect(credit.find('[data-testid="provider-credit-licence"]').attributes('href')).toBe('https://creativecommons.org/licenses/by/4.0/')
    expect(credit.find('[data-testid="processing-note"]').exists()).toBe(true)
  })
})

describe('depth and intensity', () => {
  const radio = (wrapper: Wrapper, name: string) => wrapper.findAll('[role="radio"]').find(button => button.text().startsWith(name))!

  it('is a switch of the two, in their units, with the depth chosen', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    const group = wrapper.find('[role="radiogroup"]')
    expect(group.attributes('aria-label')).toBe('Show the rain as')
    expect(group.findAll('[role="radio"]').map(button => [button.text(), button.attributes('aria-checked')])).toEqual([['Depth (mm)', 'true'], ['Intensity (l/(s·ha))', 'false']])
  })

  it('changes the table and the chart to the intensity, keeps DWD\'s uncertainty, and back', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    const cell = () => wrapper.find('tr[data-minutes="60"] td[data-years="100"]')
    const depth = cell().find('.kostra-value').text()
    await radio(wrapper, 'Intensity').trigger('click')
    await vi.waitFor(() => expect(cell().find('.kostra-value').text()).not.toBe(depth))
    expect(cell().find('.kostra-value').text()).toBe((depthOf(60, 100) / 60 * 10000 / 60).toFixed(1))
    expect(cell().find('.kostra-uncertainty').text()).toContain('±12 %')
    expect(wrapper.find('.kostra-corner-unit').text()).toBe('l/(s·ha)')
    expect(wrapper.findComponent(KostraChart).props('quantity')).toBe('intensity')
    expect(radio(wrapper, 'Intensity').attributes('aria-checked')).toBe('true')
    await radio(wrapper, 'Depth').trigger('click')
    await vi.waitFor(() => expect(cell().find('.kostra-value').text()).toBe(depth))
    expect(wrapper.findComponent(KostraChart).props('quantity')).toBe('depth')
  })

  it('does not ask the backend again: the table holds both', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    await radio(wrapper, 'Intensity').trigger('click')
    await wrapper.vm.$nextTick()
    expect(asked).toHaveLength(1)
  })

  it('stays where it was chosen when the point changes', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    await radio(wrapper, 'Intensity').trigger('click')
    stage.emit!('pick', { latitude: 53.55, longitude: 9.99, tolerance: 1, tap: 1, disc: 1 })
    await vi.waitFor(() => expect(asked).toHaveLength(2))
    await shown(wrapper)
    expect(radio(wrapper, 'Intensity').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('.kostra-corner-unit').text()).toBe('l/(s·ha)')
  })
})

describe('a point outside DWD\'s grid', () => {
  beforeEach(() => {
    status = 400
    respond = () => OUTSIDE_PROBLEM
  })

  it('is told in plain words, as a note and not as an error: no alert, no toast, no Retry', async () => {
    const wrapper = await mountKostra('?lat=40&lon=3')
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-outside').exists()).toBe(true))
    const note = byId(wrapper, 'kostra-outside')
    expect(note.text()).toBe('There is no design rainfall for this point. DWD\'s grid covers Germany and a border of about 10 km around it, and gives no values at sea. Choose another point.')
    expect(note.attributes('role')).toBe('status')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(byId(wrapper, 'kostra-failed').exists()).toBe(false)
    expect(byId(wrapper, 'kostra-retry').exists()).toBe(false)
    expect(toastAdd).not.toHaveBeenCalled()
    expect(byId(wrapper, 'kostra-table').exists()).toBe(false)
  })

  it('keeps the point on the map, with no cell, so that the reader sees what was chosen and can click another', async () => {
    const wrapper = await mountKostra('?lat=40&lon=3')
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-outside').exists()).toBe(true))
    expect(stage.props.position).toEqual({ latitude: 40, longitude: 3 })
    expect(stage.props.box).toBeNull()
  })

  it('is left by choosing a point inside it: the table comes', async () => {
    const wrapper = await mountKostra('?lat=40&lon=3')
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-outside').exists()).toBe(true))
    status = 200
    respond = () => kostraAnswer()
    stage.emit!('pick', { latitude: 50.7313, longitude: 13.7516, tolerance: 1, tap: 1, disc: 1 })
    await shown(wrapper)
    expect(byId(wrapper, 'kostra-outside').exists()).toBe(false)
  })
})

describe('a request that fails', () => {
  it('is told as an error, with what the backend said and a Retry that asks again', async () => {
    status = 502
    respond = () => ({ type: 'x', title: 'Bad Gateway', status: 502, detail: 'DWD could not be reached' })
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-failed').exists()).toBe(true))
    expect(byId(wrapper, 'kostra-failed').find('[role="alert"]').text()).toContain('The design rainfall could not be loaded.')
    expect(byId(wrapper, 'kostra-failed-detail').text()).toBe('DWD could not be reached')
    expect(byId(wrapper, 'kostra-outside').exists()).toBe(false)
    status = 200
    respond = () => kostraAnswer()
    await byId(wrapper, 'kostra-retry').trigger('click')
    await shown(wrapper)
    expect(byId(wrapper, 'kostra-failed').exists()).toBe(false)
  })

  it('is no table for an answer that is not one (a proxy\'s page)', async () => {
    respond = () => ({ hello: 'world' })
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await vi.waitFor(() => expect(byId(wrapper, 'kostra-failed').exists()).toBe(true))
    expect(byId(wrapper, 'kostra-table').exists()).toBe(false)
  })
})

describe('the tool in the app', () => {
  it('has a duration for each row that is the table\'s: 22 of them, 5 min to 7 d', async () => {
    const wrapper = await mountKostra(`?lat=${ZINNWALD.lat}&lon=${ZINNWALD.lon}`)
    await shown(wrapper)
    const labels = wrapper.findAll('[data-testid="kostra-table"] tbody th').map(th => th.text())
    expect(labels).toHaveLength(KOSTRA_DURATIONS.length)
    expect(labels[0]).toBe('5 min')
    expect(labels.at(-1)).toBe('7 d')
  })
})
