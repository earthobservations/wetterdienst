import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelection } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { UApp } from '#components'
import { useNuxtApp, useToast } from '#imports'
import DataViewer from '~/components/DataViewer.vue'

// The refusal of a limit is a state of the table area (GH-3457): the server's problem carries the numbers,
// and the page words them itself, in the language of the page

const settings: DataSettings = {
  humanize: true,
  convertUnits: true,
  unitTargets: {},
  shape: 'long',
  skipEmpty: false,
  skipThreshold: 0.95,
  skipCriteria: 'min',
  dropNulls: true,
  useNearbyStationDistance: 1,
  stationDistanceHomogeneous: 40,
  stationDistanceHeterogeneous: 20,
  useStationDistancePerParameter: {},
  minGainOfValuePairs: 0.1,
  numAdditionalStations: 3,
}

const parameterSelection: ParameterSelection = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily',
  dataset: 'climate_summary',
  parameters: ['temperature_air_mean_2m'],
}

const REFUSAL = {
  type: 'urn:wetterdienst:problem:limit-exceeded',
  title: 'Bad Request',
  status: 400,
  detail: 'This request would return about 614,866 rows, more than the 500,000 this server sends as one answer.',
  limit: 'rows',
  maximum: 500_000,
  requested: 614_866,
}

type Station = StationSelectionState['selection']['stations'][number]

// three stations with a record each, as the issue's example: daily data from 1891 on is more than the limit
function stationsWithRecords(): StationSelectionState {
  const stations = [
    { station_id: '00044', name: 'A', start_timestamp: '1891-01-01T00:00:00+00:00', end_timestamp: null },
    { station_id: '00071', name: 'B', start_timestamp: '1936-01-01T00:00:00+00:00', end_timestamp: null },
    { station_id: '00073', name: 'C', start_timestamp: '1949-01-01T00:00:00+00:00', end_timestamp: null },
  ] as Station[]
  return { mode: 'station', selection: { stations }, interpolation: { source: 'manual' }, dateRange: {} }
}

const mounted: { unmount: () => void }[] = []

async function mountViewer(selection: StationSelectionState = stationsWithRecords(), selectionParameters = parameterSelection) {
  const stationSelection = ref(selection)
  const wrapper = await mountSuspended(defineComponent({
    setup: () => () => h(UApp, null, {
      default: () => h(DataViewer, { parameterSelection: selectionParameters, stationSelection: stationSelection.value, settings }),
    }),
  }), { attachTo: document.body })
  mounted.push(wrapper)
  return { wrapper, viewer: wrapper.findComponent(DataViewer), stationSelection }
}

function fetchData(viewer: Awaited<ReturnType<typeof mountViewer>>['viewer']) {
  return (viewer.vm as unknown as { fetchData: () => Promise<void> }).fetchData()
}

function refuse(body: Record<string, unknown> = REFUSAL, endpoint = '/api/values') {
  registerEndpoint(endpoint, (event) => {
    setResponseStatus(event, 400)
    return body
  })
}

async function refused(selection?: StationSelectionState, body: Record<string, unknown> = REFUSAL, selectionParameters = parameterSelection) {
  refuse(body, selection?.mode === 'interpolation' ? '/api/interpolate' : '/api/values')
  const viewer = await mountViewer(selection, selectionParameters)
  await fetchData(viewer.viewer)
  await vi.waitFor(() => expect(viewer.wrapper.find('[data-testid="limit-notice"]').exists()).toBe(true))
  return viewer
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  useToast().clear()
  document.body.innerHTML = ''
})

describe('limit notice', () => {
  it('says it in the language of the page, with the numbers, where the server\'s text is English', async () => {
    const { wrapper } = await refused()
    const notice = wrapper.find('[data-testid="limit-notice"]')
    expect(notice.text()).toContain('Too many rows for one answer')
    expect(notice.text()).toContain('about 614,866 rows')
    expect(notice.text()).toContain('limit: 500,000')
    // what can be done, with what the selection holds
    expect(notice.text()).toContain('a shorter date range, fewer parameters or fewer stations')
    expect(notice.text()).toContain('3 stations and 1 parameter')
    // not the generic error, nor the server's words, nor a toast
    expect(wrapper.text()).not.toContain('Failed to load data')
    expect(document.body.textContent).not.toContain('This request would return')
    expect(document.body.textContent).not.toContain('Data request failed')
  })

  it('writes the numbers and the words as the language does', async () => {
    const { wrapper } = await refused()
    await useNuxtApp().$i18n.setLocale('de')
    try {
      await vi.waitFor(() => expect(wrapper.find('[data-testid="limit-notice"]').text()).toContain('etwa 614.866 Zeilen'))
      const text = wrapper.find('[data-testid="limit-notice"]').text()
      expect(text).toContain('Grenze: 500.000')
      expect(text).toContain('Ausgewählt sind 3 Stationen und 1 Parameter')
    }
    finally {
      await useNuxtApp().$i18n.setLocale('en')
    }
  })

  it('is an alert whose text holds no button, the buttons coming after it in the tab order', async () => {
    const { wrapper } = await refused()
    const notice = wrapper.find('[data-testid="limit-notice"]')
    const alert = notice.find('[role="alert"]')
    expect(alert.exists()).toBe(true)
    expect(alert.find('button, a').exists()).toBe(false)
    expect(notice.attributes('aria-labelledby')).toBeTruthy()
    const order = notice.findAll('button, a').map(control => control.attributes('data-testid'))
    expect(order).toEqual(['limit-apply', 'limit-download'])
  })

  it('offers the newest window that fits, as a button that names it and its rows', async () => {
    const { wrapper } = await refused()
    const button = wrapper.find('[data-testid="limit-apply"]')
    // 614,866 rows over 135 years: the newest part holds what 90 % of 500,000 allows
    expect(button.text()).toMatch(/^Show only the newest data \(\d+ years, about 4\d\d,000 rows\)$/)
  })

  it('hands the window to the page, which writes it to the date fields and asks again', async () => {
    const { wrapper, viewer } = await refused()
    await wrapper.find('[data-testid="limit-apply"]').trigger('click')
    const [range] = viewer.emitted('applyRange')![0] as [{ startDate: string, endDate: string }]
    expect(range.endDate).toBe(new Date().toISOString().slice(0, 10))
    expect(range.startDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(range.startDate < range.endDate).toBe(true)
  })

  it('offers the streamed CSV of the request that was refused, which the browser saves as it comes', async () => {
    const { wrapper } = await refused()
    const link = wrapper.find('[data-testid="limit-download"]')
    expect(link.text()).toBe('Download everything as CSV')
    const url = new URL(link.attributes('href')!, 'http://localhost')
    expect(url.pathname).toBe('/api/values')
    expect(url.searchParams.get('format')).toBe('csv')
    expect(url.searchParams.get('stations')).toBe('00044,00071,00073')
    expect(url.searchParams.get('provider')).toBe('dwd')
    expect(link.attributes('download')).toBe('values.csv')
    expect(wrapper.find('[data-testid="limit-notice"]').text()).toContain('streamed')
  })

  it('leaves the link to the browser: a click is no navigation of the app (the address is the proxy\'s, not a page)', async () => {
    const { wrapper } = await refused()
    const link = wrapper.find('[data-testid="limit-download"]')
    const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 })
    link.element.dispatchEvent(click)
    expect(click.defaultPrevented).toBe(false)
  })

  it('offers no CSV where the stream would be refused too', async () => {
    const { wrapper } = await refused(undefined, { ...REFUSAL, requested: 50_000_000 })
    expect(wrapper.find('[data-testid="limit-download"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(true)
  })

  it('says so where not even one day fits, and offers only what is left', async () => {
    const { wrapper } = await refused(undefined, { ...REFUSAL, maximum: 2 })
    expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="limit-no-window"]').text()).toContain('Not even the shortest date range fits')
    expect(wrapper.find('[data-testid="limit-download"]').exists()).toBe(true)
  })

  it('does not claim that no window fits where the page cannot count the span: no station publishes its record', async () => {
    const stations = [{ station_id: '00044', name: 'A', start_timestamp: null, end_timestamp: null }] as Station[]
    const { wrapper } = await refused({ mode: 'station', selection: { stations }, interpolation: { source: 'manual' }, dateRange: {} })
    expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="limit-no-window"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="limit-notice"]').text()).toContain('Too many rows for one answer')
  })

  it('words the stations limit as fewer stations, with no window and no CSV', async () => {
    const { wrapper } = await refused(undefined, { ...REFUSAL, limit: 'stations', maximum: 100, requested: 1284 })
    const notice = wrapper.find('[data-testid="limit-notice"]')
    expect(notice.text()).toContain('Too many stations for one request')
    expect(notice.text()).toContain('1,284 selected, 100 allowed')
    expect(notice.text()).toContain('Remove stations from the selection')
    expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="limit-download"]').exists()).toBe(false)
  })

  it('takes a point\'s rows to the date range alone, with no stations to name and no CSV', async () => {
    const point: StationSelectionState = {
      mode: 'interpolation',
      selection: { stations: [] },
      interpolation: { source: 'manual', latitude: 52, longitude: 13 },
      dateRange: { startDate: '1950-01-01', endDate: '2025-12-31' },
    }
    const { wrapper } = await refused(point, { ...REFUSAL, requested: 6_000_000 }, { ...parameterSelection, resolution: 'hourly' })
    const notice = wrapper.find('[data-testid="limit-notice"]')
    expect(notice.text()).toContain('choose a shorter date range or fewer parameters')
    expect(notice.text()).not.toContain('stations')
    expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="limit-download"]').exists()).toBe(false)
  })

  it('leaves the stations a point reaches as the error it is: the radius is the remedy, not the selection', async () => {
    const point: StationSelectionState = {
      mode: 'interpolation',
      selection: { stations: [] },
      interpolation: { source: 'manual', latitude: 52, longitude: 13 },
      dateRange: { startDate: '2020-01-01', endDate: '2020-01-31' },
    }
    const { viewer, wrapper } = await mountViewer(point)
    refuse({ ...REFUSAL, limit: 'stations', maximum: 100, requested: 300, detail: 'Narrow the radius' }, '/api/interpolate')
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Narrow the radius'))
    expect(wrapper.find('[data-testid="limit-notice"]').exists()).toBe(false)
  })

  it('leaves any other refusal as the error it is, with the server\'s own words', async () => {
    refuse({ type: 'urn:wetterdienst:problem:invalid-request', title: 'Bad Request', status: 400, detail: 'Unknown parameter foo' })
    const { wrapper, viewer } = await mountViewer()
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Unknown parameter foo'))
    expect(wrapper.find('[data-testid="limit-notice"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Failed to load data')
  })

  it('leaves the stream limit as an error, as the page asks for no stream', async () => {
    refuse({ ...REFUSAL, limit: 'stream_rows' })
    const { wrapper, viewer } = await mountViewer()
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Failed to load data'))
    expect(wrapper.find('[data-testid="limit-notice"]').exists()).toBe(false)
  })

  it('offers no window to a selection that has moved on since the refusal, which it was not fitted to', async () => {
    const { wrapper, stationSelection } = await refused()
    expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(true)
    // a station less: the request differs from the one refused. The viewer reads the selection from its props
    stationSelection.value = { ...stationSelection.value, selection: { stations: stationSelection.value.selection.stations.slice(0, 2) } }
    await vi.waitFor(() => expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(false))
    // what was refused can still be had as a stream
    expect(wrapper.find('[data-testid="limit-download"]').exists()).toBe(true)
  })

  it('gives the focus to the table area when the answer replaces the notice a button of which held it', async () => {
    const { wrapper, viewer } = await refused()
    const apply = wrapper.find('[data-testid="limit-apply"]').element as HTMLElement
    apply.focus()
    expect(document.activeElement).toBe(apply)
    registerEndpoint('/api/values', () => ({ values: [{ station_id: '00044', resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', timestamp: '2020-01-01T00:00:00Z', value: 1.5, quality_flags: null }] }))
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="limit-notice"]').exists()).toBe(false))
    await vi.waitFor(() => expect(wrapper.find('table').exists()).toBe(true))
    expect(document.activeElement?.tagName).not.toBe('BODY')
    expect(wrapper.element.contains(document.activeElement)).toBe(true)
  })

  it('keeps the focus in the table area when applying the window moves the selection and takes the button away', async () => {
    const { wrapper, viewer, stationSelection } = await refused()
    const apply = wrapper.find('[data-testid="limit-apply"]')
    ;(apply.element as HTMLElement).focus()
    await apply.trigger('click')
    // the page writes the dates before it asks again: the button is gone with the change, ahead of the request
    const [{ startDate, endDate }] = viewer.emitted('applyRange')![0] as [{ startDate: string, endDate: string }]
    stationSelection.value = { ...stationSelection.value, dateRange: { startDate, endDate } }
    await vi.waitFor(() => expect(wrapper.find('[data-testid="limit-apply"]').exists()).toBe(false))
    expect(document.activeElement?.tagName).not.toBe('BODY')
    expect(wrapper.element.contains(document.activeElement)).toBe(true)
  })
})
