import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import WidgetPage from '~/pages/widget.vue'
import { fill, messagesOf, OTHER_LANGUAGES } from '../fixtures/catalogs'

// the page's $fetch, passed through to the real one unless a test makes it fail where nothing answered,
// which no endpoint can do
const lookup = vi.hoisted(() => ({ fetch: undefined as unknown as ReturnType<typeof vi.fn> }))
mockNuxtImport('$fetch', original => (lookup.fetch = vi.fn(original)))

describe('widget Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    const wrapper = await mountSuspended(WidgetPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('shows a hint when no station query param is given', async () => {
    const wrapper = await mountSuspended(WidgetPage)
    expect(wrapper.text()).toContain('No station specified')
  })

  it('loads the station and forecast when ?station= is present', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    const vm = wrapper.vm as any
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(vm.station?.station_id).toBe('00001')
  })

  it('shows an error when the station lookup fails', async () => {
    onTestFinished(registerEndpoint('/api/stations', () => new Response('not found', { status: 404 })))

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=99999' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    // a body without a detail is left out
    await vi.waitFor(() => expect(vm.error).toMatch(/^Backend error 404/))
    expect(wrapper.text()).not.toContain('not found')
  })

  it('tells a failed forecast by the backend\'s detail', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response(JSON.stringify({ detail: 'No forecast for station 00001' }), { status: 404, statusText: 'Not Found' }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 404: No forecast for station 00001'))
    expect(wrapper.text()).toContain('Backend error 404: No forecast for station 00001')
  })

  it('tells a failed forecast by its status when the body gives no detail', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    // a proxy's error page: its status text is told, its body left out
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response('<html>proxy page</html>', { status: 502, statusText: 'Bad Gateway' }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 502 Bad Gateway'))
    expect(wrapper.text()).not.toContain('proxy page')
  })

  it('applies the theme query param to color mode', async () => {
    registerEndpoint('/api/stations', () => ({ stations: [] }))

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?theme=dark' })
    const vm = wrapper.vm as any
    await wrapper.vm.$nextTick()

    expect(vm.colorMode.preference).toBe('dark')
  })

  it('links back to the full meteogram page', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('/meteogram?station=00001')
  })
})

describe('widget Page station lookup answered with a 500', () => {
  it('asks /api/stations once', async () => {
    // counted at the endpoint, which a request reaches however it is made
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    }))
    globalThis.fetch = vi.fn()
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => wrapper.unmount())
    // set once the lookup has failed, which a request asked again does after its second answer
    await vi.waitFor(() => expect((wrapper.vm as any).error).not.toBeNull())
    expect(asked).toBe(1)
  })
})

describe('widget Page station lookup answered with a 503 once', () => {
  it('asks /api/stations once more, and shows the station that answer brings', async () => {
    // a 503 the first time only, as a proxy gives while the backend restarts
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      if (asked === 1) {
        setResponseStatus(event, 503)
        return { detail: 'Service Unavailable' }
      }
      return { stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }] }
    }))
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.station?.station_id).toBe('00001'))
    expect(asked).toBe(2)
    expect(vm.error).toBeNull()
  })
})

// what the backend answers a failure of its own: the exception's type, never its text (GH-2767)
const backendDetail = 'Internal server error (RuntimeError). The cause is in the server log.'

describe('widget Page station lookup', () => {
  it('tells a failed lookup by the backend\'s detail, not as a station not found', async () => {
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      setResponseStatus(event, 500)
      return { detail: backendDetail }
    }))
    globalThis.fetch = vi.fn()
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=01001' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(vm.error).toBe(`Backend error 500: ${backendDetail}`))
    expect(wrapper.text()).toContain(`Backend error 500: ${backendDetail}`)
    expect(wrapper.text()).not.toContain('Station not found')
  })

  it('tells a failed lookup by its status when the body gives no detail', async () => {
    // a proxy's error page: its status text is told, its body left out
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      setResponseStatus(event, 502, 'Bad Gateway')
      return '<html>proxy page</html>'
    }))
    globalThis.fetch = vi.fn()
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=01001' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(vm.error).toBe('Backend error 502 Bad Gateway'))
    expect(wrapper.text()).not.toContain('proxy page')
    expect(wrapper.text()).not.toContain('Station not found')
  })

  it('says the station is not found when the answer holds no station', async () => {
    onTestFinished(registerEndpoint('/api/stations', () => ({ stations: [] })))
    globalThis.fetch = vi.fn()
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=99999' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(vm.error).toBe('Station not found'))
    expect(vm.station).toBeNull()
    expect(wrapper.text()).toContain('Station not found')
  })

  it('tells a lookup nothing answered by the error, not as a station not found', async () => {
    // what ofetch throws where no answer came: no response on it, its request in front of the message
    const unanswered = new TypeError('[GET] "/api/stations?stations=01001": <no response> Failed to fetch')
    lookup.fetch.mockRejectedValueOnce(unanswered)
    // back to the real $fetch should the failure not be asked for, so it cannot reach a later test
    onTestFinished(() => {
      lookup.fetch.mockReset()
    })
    globalThis.fetch = vi.fn()
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=01001' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any

    await vi.waitFor(() => expect(vm.error).toBe('Failed to fetch'))
    expect(wrapper.text()).not.toContain('Station not found')
  })

  it('shows a found station without an error', async () => {
    onTestFinished(registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '01001', name: 'Jan Mayen', latitude: 70.9, longitude: -8.7 }],
    })))
    globalThis.fetch = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=01001' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any

    // set once the forecast has been asked for, which follows the found station
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    await vi.waitFor(() => expect(vm.pending).toBe(false))
    expect(vm.station?.station_id).toBe('01001')
    expect(vm.error).toBeNull()
    expect(wrapper.text()).toContain('Jan Mayen')
    expect(wrapper.text()).not.toContain('Station not found')
  })
})

describe('widget Page values request', () => {
  it('asks for the layout and units the meteogram reads, whatever the server\'s WD_TS_* say', async () => {
    onTestFinished(registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '01001', name: 'Jan Mayen', latitude: 70.9, longitude: -8.7 }],
    })))
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=01001' })
    onTestFinished(() => wrapper.unmount())
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/values?')))

    const asked = vi.mocked(globalThis.fetch).mock.calls.map(([input]) => String(input)).find(input => input.includes('/api/values?'))!
    const query = new URL(asked, 'http://localhost').searchParams
    expect(query.get('stations')).toBe('01001')
    expect(query.get('shape')).toBe('long')
    expect(query.get('humanize')).toBe('true')
    expect(query.get('convert_units')).toBe('true')
    expect(query.get('skip_empty')).toBe('false')
    // each quantity the charts give a unit for, as the server's own targets are merged into the request's
    expect(JSON.parse(query.get('unit_targets')!)).toEqual({
      angle: 'degree',
      fraction: 'decimal',
      precipitation: 'millimeter',
      pressure: 'hectopascal',
      speed: 'meter_per_second',
      temperature: 'degree_celsius',
    })
  })
})

describe('widget Page failures in the active language', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
  })

  // the language switched to for the test, and back (GH-2971)
  async function inLanguage(language: string) {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as any).setLocale(language)
    onTestFinished(async () => {
      await (harness.vm as any).setLocale('en')
      harness.unmount()
    })
  }

  it.each([
    ['en', 'Request failed'],
    ['de', 'Anfrage fehlgeschlagen'],
    ['fr', 'La requête a échoué'],
    ['pl', 'Żądanie nie powiodło się'],
  ])('says in %s that a request threw with no message', async (language, expected) => {
    await inLanguage(language)
    // a rejection that carries no message, as a request aborted by the browser can
    vi.mocked(globalThis.fetch).mockRejectedValue({})

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => wrapper.unmount())
    await vi.waitFor(() => expect((wrapper.vm as any).error).toBe(expected))
  })

  it.each([
    ['en', 'Backend error 404: No forecast', 'Backend error 502 Bad Gateway'],
    ['de', 'Backend-Fehler 404: No forecast', 'Backend-Fehler 502 Bad Gateway'],
    ['fr', 'Erreur du backend 404\u00A0: No forecast', 'Erreur du backend 502 Bad Gateway'],
    ['pl', 'Błąd backendu 404: No forecast', 'Błąd backendu 502 Bad Gateway'],
  ])('names the backend\'s error in %s', async (language, withDetail, withStatus) => {
    await inLanguage(language)
    vi.mocked(globalThis.fetch).mockImplementationOnce(async () =>
      new Response(JSON.stringify({ detail: 'No forecast' }), { status: 404, statusText: 'Not Found' }),
    )
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => wrapper.unmount())
    await vi.waitFor(() => expect((wrapper.vm as any).error).toBe(withDetail))

    vi.mocked(globalThis.fetch).mockImplementationOnce(async () =>
      new Response('<html>proxy page</html>', { status: 502, statusText: 'Bad Gateway' }),
    )
    const refused = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => refused.unmount())
    await vi.waitFor(() => expect((refused.vm as any).error).toBe(withStatus))
  })
})

// the failure on show is written again in the language switched to, not kept in the one it was made in (GH-3052)
describe('widget Page failure after a language switch', () => {
  const messages = (code: string) => messagesOf(code, 'common')
  const station = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }

  let harness: Awaited<ReturnType<typeof mountSuspended>> | undefined
  const setLocale = (code: string) => (harness!.vm as any).setLocale(code)

  beforeEach(async () => {
    globalThis.fetch = vi.fn()
    registerEndpoint('/api/stations', () => ({ stations: [station] }))
    harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await setLocale('en')
  })

  afterEach(async () => {
    await setLocale('en')
    harness?.unmount()
    harness = undefined
  })

  // the page shows the failure in English, the language is switched, and the same failure is shown again
  async function failedThenSwitched(code: string, answer: () => Promise<Response>) {
    vi.mocked(globalThis.fetch).mockImplementation(answer)
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.error).not.toBeNull())
    const before = vm.error
    await setLocale(code)
    await vi.waitFor(() => expect(wrapper.text()).toContain(vm.error))
    return { before, after: vm.error as string, requests: vi.mocked(globalThis.fetch).mock.calls.length }
  }

  it.each(OTHER_LANGUAGES)('writes the failure of a request with no message in %s', async (code) => {
    const { before, after, requests } = await failedThenSwitched(code, async () => Promise.reject(Object.assign(new Error('aborted'), { message: '' })))
    expect(before).toBe(messages('en').requestFailed)
    expect(after).toBe(messages(code).requestFailed)
    expect(after).not.toBe(before)
    // the message was translated, not asked for again
    expect(requests).toBe(1)
  })

  it.each(OTHER_LANGUAGES)('writes the backend\'s error with its reason in %s', async (code) => {
    const { before, after } = await failedThenSwitched(code, async () =>
      new Response(JSON.stringify({ detail: 'No forecast' }), { status: 404, statusText: 'Not Found' }))
    expect(before).toBe('Backend error 404: No forecast')
    expect(after).toBe(fill(messages(code).backendErrorDetail!, { status: '404', detail: 'No forecast' }))
    expect(after).not.toBe(before)
  })

  it.each(OTHER_LANGUAGES)('writes the backend\'s error with its status in %s, the status text as the server wrote it', async (code) => {
    const { before, after } = await failedThenSwitched(code, async () =>
      new Response('<html>proxy page</html>', { status: 502, statusText: 'Bad Gateway' }))
    expect(before).toBe('Backend error 502 Bad Gateway')
    expect(after).toBe(`${fill(messages(code).backendError!, { status: '502' })} Bad Gateway`)
    expect(after).not.toBe(before)
  })

  it.each(OTHER_LANGUAGES)('writes the failure of a station lookup that found no station in %s', async (code) => {
    registerEndpoint('/api/stations', () => ({ stations: [] }))
    const { before, after } = await failedThenSwitched(code, async () => new Response('{}'))
    expect(before).toBe('Station not found')
    expect(after).toBe(messagesOf(code, 'widget').stationNotFound)
    expect(after).not.toBe(before)
  })

  it('leaves a message of the browser\'s own as it is', async () => {
    const { before, after } = await failedThenSwitched('de', async () => Promise.reject(new TypeError('Failed to fetch')))
    expect(before).toBe('Failed to fetch')
    expect(after).toBe('Failed to fetch')
  })
})
