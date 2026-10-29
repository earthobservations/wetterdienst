import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import IndexPage from '~/pages/index.vue'
import { providersResponse } from '../fixtures/providers'

// The weather services are the backend's (`GET /api/providers`), which `useFetch` keys by name: cleared
// between tests, or a later test is served the answer of the one before. Registered once: re-registering the
// same path in a later test does not replace the handler.
let served: (event: H3Event) => unknown = () => providersResponse()
registerEndpoint('/api/providers', event => served(event))

const mounted: Array<{ unmount: () => void }> = []
async function mountHome() {
  const wrapper = await mountSuspended(IndexPage)
  mounted.push(wrapper)
  return wrapper
}
function tile(wrapper: Awaited<ReturnType<typeof mountHome>>, label: string) {
  return wrapper.findAll('.text-2xl').find(el => el.element.parentElement?.textContent?.includes(label))
}
function servicesTile(wrapper: Awaited<ReturnType<typeof mountHome>>) {
  return tile(wrapper, 'weather services')
}
function parametersTile(wrapper: Awaited<ReturnType<typeof mountHome>>) {
  return tile(wrapper, 'parameters')
}
function settled(wrapper: Awaited<ReturnType<typeof mountHome>>) {
  return vi.waitFor(() => expect((wrapper.vm as any).providersLoading).toBe(false), { timeout: 5000 })
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  served = () => providersResponse()
})

describe('index Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('contains main navigation elements', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const html = wrapper.html()

    expect(html.length).toBeGreaterThan(0)
  })

  it('says what data the app delivers', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()

    expect(text).toContain('What data you get')
    // the kinds of data, which are networks in the backend rather than a marketing list
    expect(text).toContain('Measurements')
    expect(text).toContain('Forecasts')
    expect(text).toContain('Water levels')
    expect(text).toContain('Radar')
  })

  it('names the weather services behind the data, as the backend lists them', async () => {
    const wrapper = await mountHome()
    await settled(wrapper)
    const chips = wrapper.findAll('[data-testid="home-providers"] a')

    // by short name, in the order of the page's language, each with the flag of its country (a globe for several)
    expect(chips.map(chip => chip.text())).toEqual(['🇪🇸 AEMET', '🇩🇪 DWD', '🌐 EUMETNET', '🇳🇴 met.no', '🇱🇺 MOSMIX'])
    // and each leads to the page of the provider
    expect(chips.map(chip => chip.attributes('href'))).toEqual(
      ['/providers/aemet', '/providers/dwd', '/providers/eumetnet', '/providers/metno', '/providers/mosmix'],
    )
    // the flag is decoration
    expect(wrapper.findAll('[data-testid="home-providers"] [aria-hidden="true"]').map(el => el.text())).toContain('🇩🇪')
  })

  it('counts the weather services from the answer, not from a number of its own', async () => {
    const wrapper = await mountHome()
    await settled(wrapper)
    expect(servicesTile(wrapper)?.text()).toBe('5')

    // one more provider upstream is one more chip and a number higher, with nothing changed in the app
    clearNuxtData()
    served = () => {
      const response = providersResponse()
      response.providers.pop()
      response.metadata.counts.providers = response.providers.length
      return response
    }
    const fewer = await mountHome()
    await settled(fewer)
    expect(fewer.findAll('[data-testid="home-providers"] a')).toHaveLength(4)
    expect(servicesTile(fewer)?.text()).toBe('4')
  })

  it('counts the parameters from the answer too, not from a number of its own', async () => {
    const wrapper = await mountHome()
    await settled(wrapper)
    expect(parametersTile(wrapper)?.text()).toBe('587')

    // a parameter more upstream is a number higher, with nothing changed in the app
    clearNuxtData()
    served = () => {
      const response = providersResponse()
      response.metadata.counts.parameters = 600
      return response
    }
    const more = await mountHome()
    await settled(more)
    expect(parametersTile(more)?.text()).toBe('600')
  })

  it('holds the place of the chips and the count until the backend has answered', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    served = async () => {
      await gate
      return providersResponse()
    }
    const wrapper = await mountHome()

    expect((wrapper.vm as any).providersLoading).toBe(true)
    // placeholders where the chips will be, and no number yet (nor a 0 that would be a claim)
    expect(wrapper.find('[role="status"][aria-busy="true"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="home-providers"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('EUMETNET')
    expect(wrapper.text()).not.toContain('No weather services')
    expect(servicesTile(wrapper)?.text()).toBe('')
    expect(parametersTile(wrapper)?.text()).toBe('')
    expect(parametersTile(wrapper)?.find('.animate-pulse').exists()).toBe(true)

    release()
    await settled(wrapper)
    expect(wrapper.find('[aria-busy="true"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('EUMETNET')
  })

  it('says so where the backend lists no weather service', async () => {
    served = () => {
      const response = providersResponse()
      response.providers = []
      response.metadata.counts.providers = 0
      return response
    }
    const wrapper = await mountHome()
    await settled(wrapper)

    expect(wrapper.text()).toContain('No weather services to show.')
    expect(wrapper.findAll('[data-testid="home-providers"]')).toHaveLength(0)
  })

  it('tells why the weather services are missing, with a way to ask again, and the rest of the page stays', async () => {
    served = (event) => {
      setResponseStatus(event, 502)
      return { type: 'urn:wetterdienst:problem:backend-unreachable', title: 'Bad Gateway', status: 502, detail: 'The backend could not be reached.' }
    }
    const wrapper = await mountHome()
    await settled(wrapper)

    expect(wrapper.text()).toContain('Request failed')
    expect(wrapper.text()).toContain('The backend could not be reached.')
    // the counts are not guessed at, and the numbers that do not come from the backend are there
    expect(servicesTile(wrapper)?.text()).toBe('–')
    expect(parametersTile(wrapper)?.text()).toBe('–')
    expect(wrapper.text()).toContain('0 €')
    // the one of the weather services' card: the answer above it has a Retry of its own
    const retry = wrapper.find('[data-testid="home-providers-card"]').findAll('button').find(button => button.text() === 'Retry')
    expect(retry).toBeDefined()

    served = () => providersResponse()
    await retry!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('EUMETNET'))
    expect(wrapper.text()).not.toContain('Request failed')
  })

  it('leads from the weather services to the page that says what each is', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const link = wrapper.findAll('a').find(a => a.attributes('href') === '/providers')

    expect(link?.text()).toBe('All providers, their licences and what they offer')
  })

  it('points developers at the library, the API and MCP', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()
    const html = wrapper.html()

    // anchors with hrefs, not just the words: an earlier version rendered two of these three as
    // plain text and the wording assertions passed anyway
    const chips = wrapper.findAll('a').map(a => `${a.attributes('href')} ${a.text()}`)
    expect(chips).toContain('https://pypi.org/project/wetterdienst/ pip install wetterdienst')
    expect(chips).toContain('/docs REST API')
    expect(chips).toContain('/mcp/v1 MCP')
    expect(text).toContain('Also for developers')
    // and the parameters lead somewhere that explains them
    expect(html).toContain('/glossary')
  })

  it('names who already supports the work', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()
    const html = wrapper.html()

    expect(text).toContain('Supported by')
    expect(text).toContain('JetBrains')
    expect(text).toContain('Anthropic')
    expect(html).toContain('jb.gg/OpenSourceSupport')
    // what each gives is the hover text rather than the badge label
    expect(html).toContain('PyCharm')
    expect(html).toContain('Claude Max')
  })

  it('states what the project stands for, measurements included', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()

    expect(text).toContain('LGBTQI+')
    expect(text).toContain('FCKNZS')
    expect(text).toContain('Global warming is not an opinion')
    expect(text).toContain('Weather data belongs to everyone')
  })

  it('sends the project and the people to the about page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()
    const html = wrapper.html()

    expect(html).toContain('/about')
    // the maintainers used to be listed here; the home page is about the data now
    expect(text).not.toContain('Benjamin Gutzmann')
    expect(text).not.toContain('Andreas Motl')
  })
})

// The questions the page opens on (GH-3518): each a link that names its question, the rain one open by default,
// and its answer worked out from the forecast nearest the place, with the way into the forecast filled in.
describe('the questions of the home page', () => {
  // three days of MOSMIX from this hour on: half a millimetre every hour, so tomorrow it rains
  const start = new Date()
  start.setUTCMinutes(0, 0, 0)
  registerEndpoint('/api/stations', () => ({
    stations: [{ station_id: '10046', name: 'KIEL-H.', region: null, latitude: 54.38, longitude: 10.15, elevation: 28, start_timestamp: null, end_timestamp: null, distance: 0.56 }],
  }))
  registerEndpoint('/api/values', () => ({
    values: Array.from({ length: 72 }, (_, hour) => ({
      station_id: '10046',
      resolution: 'hourly',
      dataset: 'large',
      parameter: 'precipitation_amount_significant_weather_last_1h',
      timestamp: new Date(start.getTime() + hour * 3_600_000).toISOString(),
      value: 0.5,
      quality_flags: null,
    })),
  }))

  it('lists the four questions about the place, each a link to its answer, the rain one open', async () => {
    const wrapper = await mountHome()
    const questions = ['rain', 'summer', 'wind', 'download'].map(id => wrapper.find(`[data-testid="question-${id}"]`))
    expect(questions.map(question => question.attributes('href'))).toEqual(['/?ask=rain', '/?ask=summer', '/?ask=wind', '/?ask=download'])
    expect(questions[0]!.text()).toContain('Will it rain in Kiel-Holtenau tomorrow?')
    expect(questions[0]!.attributes('aria-current')).toBe('true')
    expect(questions.slice(1).map(question => question.attributes('aria-current'))).toEqual([undefined, undefined, undefined])
    expect(wrapper.find('#answer-heading').text()).toBe('Will it rain in Kiel-Holtenau tomorrow?')
  })

  it('answers the rain question from the forecast nearest the place, with its chart and the forecast filled in', async () => {
    const wrapper = await mountHome()
    await vi.waitFor(() => expect(wrapper.find('[data-testid="answer-verdict"]').text()).toBe('Yes, rain is likely.'), { timeout: 5000 })
    const answer = wrapper.find('[data-testid="answer"]')
    expect(answer.text()).toContain('Forecast for KIEL-H., the forecast point nearest to Kiel-Holtenau (0.6 km away).')
    // the chart is a figure named by its caption, with its values as a table
    expect(answer.find('figure figcaption').text()).toBe('Rain per hour tomorrow, in mm')
    expect(answer.findAll('figure tbody tr').length).toBeGreaterThanOrEqual(23)
    expect(answer.findAll('a').map(link => link.attributes('href'))).toContain('/meteogram?station=10046')
  })
})
