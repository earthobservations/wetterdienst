import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import AskTheWeather from '~/components/AskTheWeather.vue'
import { DEFAULT_PLACE } from '~/composables/usePlace'
import { KIEL_MOSMIX, rainValues, summerValues, windValues } from '../../e2e/accessibility/ask-backend'
import { providersResponse } from '../fixtures/providers'

// Ask the weather (GH-3518): the suggestions of the home page as buttons that are pressed or not, the answer under
// them with its live region, the chart and the way into the tool, and the place the questions are about. The
// backend is the accessibility spec's answers (tests/e2e/accessibility/ask-backend.ts); the rules that turn them
// into a verdict are held by tests/unit/answers.test.ts.

const requests: Array<{ path: string, query: URLSearchParams }> = []
let failValues = false
function record(event: H3Event, path: string) {
  const query = new URL(event.path, 'http://localhost').searchParams
  requests.push({ path, query })
  return query
}
registerEndpoint('/api/providers', () => providersResponse())
registerEndpoint('/api/stations', (event) => {
  const query = record(event, 'stations')
  return { stations: query.get('network') === 'mosmix' ? [KIEL_MOSMIX] : [] }
})
registerEndpoint('/api/values', (event) => {
  const query = record(event, 'values')
  if (failValues) {
    setResponseStatus(event, 422)
    return { type: 'urn:wetterdienst:problem:invalid-request', title: 'Unprocessable', status: 422, detail: 'The request could not be processed.' }
  }
  const station = query.get('stations') ?? ''
  const parameters = query.get('parameters') ?? ''
  if (query.get('network') === 'mosmix')
    return { values: rainValues(station) }
  return { values: parameters.startsWith('monthly/') ? summerValues(station) : windValues(station, query.get('timestamp')) }
})
registerEndpoint('/api/coverage', () => ({
  hourly: { description: null, datasets: { temperature_air: { description: null, parameters: [{ name: 'temperature_air_mean_2m', name_original: 'tt_tu', unit_type: 'temperature', unit: 'degree_celsius', description: '' }] } } },
}))

const mounted: Array<{ unmount: () => void }> = []
async function mountAsk(route = '/') {
  const wrapper = await mountSuspended(AskTheWeather, { attachTo: document.body, route })
  mounted.push(wrapper)
  return wrapper
}
const chip = (wrapper: Awaited<ReturnType<typeof mountAsk>>, id: string) => wrapper.find(`[data-testid="question-${id}"]`)
const verdict = (wrapper: Awaited<ReturnType<typeof mountAsk>>) => wrapper.find('[data-testid="answer-verdict"]')
const asked = (path: string) => requests.filter(request => request.path === path)

beforeEach(() => {
  failValues = false
  usePlace().place.value = DEFAULT_PLACE
})
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  requests.length = 0
})

describe('the suggestions', () => {
  it('are a list of buttons that are none of them pressed, and nothing is asked of the backend until one is', async () => {
    const wrapper = await mountAsk()
    const list = wrapper.find('[data-testid="questions"]')
    expect(list.element.tagName).toBe('UL')
    expect(list.attributes('aria-label')).toBe('Questions')
    const buttons = list.findAll('li > button')
    expect(buttons).toHaveLength(4)
    expect(buttons.map(button => button.attributes('aria-pressed'))).toEqual(['false', 'false', 'false', 'false'])
    expect(buttons.map(button => button.attributes('type'))).toEqual(['button', 'button', 'button', 'button'])
    expect(buttons[0]!.text()).toBe('Will it rain in Kiel-Holtenau tomorrow?')
    expect(buttons[1]!.text()).toBe('Was last summer hotter than usual here?')
    expect(buttons[3]!.text()).toBe('Where can I download hourly temperatures?')
    expect(wrapper.find('[data-testid="ask-idle"]').text()).toBe('Pick a question and it is answered here, from live data.')
    expect(wrapper.find('[data-testid="answer"]').exists()).toBe(false)
    expect(requests).toEqual([])
  })

  it('carry no colour of a tile: the tiles are the tools\' marks, and only the links into the tools have one', async () => {
    const wrapper = await mountAsk()
    expect(wrapper.find('[data-testid="questions"] .tile').exists()).toBe(false)
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    // the monthly means open the Explorer (rain blue), the stripes the stripes (coral)
    const tiles = wrapper.findAll('[data-testid="answer-actions"] .tile').map(tile => tile.classes().find(name => name.startsWith('tile-') && name !== 'tile'))
    expect(tiles).toEqual(['tile-rain', 'tile-heat'])
  })

  it('answer the rain question from the forecast nearest the place, say it in a live region, and lead into the forecast', async () => {
    const wrapper = await mountAsk()
    await chip(wrapper, 'rain').trigger('click')
    await vi.waitFor(() => expect(chip(wrapper, 'rain').attributes('aria-pressed')).toBe('true'))
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Yes, rain is likely.'))
    const status = wrapper.find('[data-testid="answer-status"]')
    expect(status.attributes('role')).toBe('status')
    expect(status.text()).toBe('Yes, rain is likely.')
    const answer = wrapper.find('[data-testid="answer"]')
    expect(answer.find('h3').text()).toBe('Will it rain in Kiel-Holtenau tomorrow?')
    expect(answer.text()).toContain('Forecast for KIEL-HOLTENAU, the forecast point nearest to Kiel-Holtenau (0.6 km away).')
    expect(answer.find('figure figcaption').text()).toBe('Rain per hour tomorrow, in mm')
    expect(answer.findAll('figure tbody tr')).toHaveLength(24)
    expect(answer.findAll('a').map(link => link.attributes('href'))).toContain('/meteogram?station=10046')
    // the position of the place was asked, then the values of that point
    expect(asked('stations')[0]!.query.get('latitude')).toBe(String(DEFAULT_PLACE.latitude))
    expect(asked('values')[0]!.query.get('stations')).toBe('10046')
  })

  it('answer the summer, wind and download questions', async () => {
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toContain('warmer than usual'))
    expect(asked('values').at(-1)!.query.get('stations')).toBe('02564')

    await chip(wrapper, 'wind').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('#answer-day').exists()).toBe(true))
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    await vi.waitFor(() => expect(chip(wrapper, 'wind').attributes('aria-pressed')).toBe('true'))
    expect(chip(wrapper, 'summer').attributes('aria-pressed')).toBe('false')

    await chip(wrapper, 'download').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toMatch(/^Weather services that publish hourly air temperature: \d+\.$/))
    // one link for each service the verdict counts, the place's own (DWD) first
    const links = wrapper.findAll('[data-testid="answer-sources"] a').map(link => link.attributes('href'))
    expect(verdict(wrapper).text()).toContain(`: ${links.length}.`)
    expect(links.length).toBeGreaterThan(0)
    expect(links[0]).toContain('/explorer?')
    expect(links[0]).toContain('provider=dwd')
    expect(links[0]).toContain('resolution=hourly')
    expect(links[0]).toContain('stations=02564')
  })

  it('close when the one open is pressed again, and the link follows', async () => {
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(chip(wrapper, 'summer').attributes('aria-pressed')).toBe('true'))
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    expect(useRoute().query.ask).toBe('summer')
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="answer"]').exists()).toBe(false))
    expect(chip(wrapper, 'summer').attributes('aria-pressed')).toBe('false')
    expect(useRoute().query.ask).toBeUndefined()
    expect(wrapper.find('[data-testid="ask-idle"]').exists()).toBe(true)
  })

  it('open from a link that names the question, and the day of the wind one', async () => {
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    expect(chip(wrapper, 'wind').attributes('aria-pressed')).toBe('true')
    expect(chip(wrapper, 'wind').text()).toBe('How windy was it on 26 December?')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    expect(asked('values')[0]!.query.get('timestamp')).toBe('2025-12-19/2026-01-02')
  })

  it.each(['2025-13-45', '2025-02-30'])('keep the section, and the last Boxing Day, for a link whose day (%s) is no day', async (day) => {
    const wrapper = await mountAsk(`/?ask=wind&day=${day}`)
    expect(wrapper.find('[data-testid="ask"]').exists()).toBe(true)
    expect(chip(wrapper, 'wind').text()).toMatch(/^How windy was it on 26 December\?$/)
  })

  it('say that the answer could not be worked out, with a way to ask again', async () => {
    failValues = true
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('The answer could not be worked out.'))
    expect(wrapper.text()).toContain('The request could not be processed.')
    expect(wrapper.find('[data-testid="answer-status"]').text()).toBe('')
    failValues = false
    await wrapper.findAll('button').find(button => button.text() === 'Retry')!.trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toContain('warmer than usual'))
  })

  it('hand the focus from the Retry that worked to the heading of the question', async () => {
    failValues = true
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('The answer could not be worked out.'))
    const retry = wrapper.findAll('button').find(button => button.text() === 'Retry')!
    ;(retry.element as HTMLElement).focus()
    failValues = false
    await retry.trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toContain('warmer than usual'))
    expect(document.activeElement).toBe(wrapper.find('#answer-heading').element)
  })

  it('are about the place, which names them and which the answers are asked for', async () => {
    usePlace().setPlace({ id: '00183', name: 'Arkona', latitude: 54.68, longitude: 13.43, region: 'Mecklenburg-Vorpommern' })
    const wrapper = await mountAsk()
    expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Arkona')
    expect(chip(wrapper, 'rain').text()).toBe('Will it rain in Arkona tomorrow?')
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    expect(asked('values')[0]!.query.get('stations')).toBe('00183')
  })
})
