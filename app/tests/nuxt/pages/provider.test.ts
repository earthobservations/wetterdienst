import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import ProviderPage from '~/pages/providers/[provider].vue'
import { dailyClimateSummaryCoverage } from '../fixtures/coverage'
import { providersAnswer } from '../fixtures/providers'

const mounted: Array<{ unmount: () => void }> = []
let served: (event: H3Event) => unknown = providersAnswer
// registered once: re-registering the same path in a later test does not replace the handler
registerEndpoint('/api/providers', event => served(event))
// the coverage of a network, asked for where its list is opened
let coverageServed: (event: H3Event) => unknown = () => dailyClimateSummaryCoverage()
registerEndpoint('/api/coverage', event => coverageServed(event))

async function mountProvider(provider: string) {
  const wrapper = await mountSuspended(ProviderPage, { route: `/providers/${provider}` })
  mounted.push(wrapper)
  await vi.waitFor(() => expect((wrapper.vm as any).pending).toBe(false), { timeout: 5000 })
  return wrapper
}

async function openDatasets(wrapper: Awaited<ReturnType<typeof mountProvider>>, network: string) {
  const item = wrapper.findAll('li').find(li => li.find('h3').exists() && li.find('h3').text() === network)!
  await item.findAll('button').find(button => button.text() === 'Show resolutions and datasets')!.trigger('click')
}

function hrefs(wrapper: { findAll: (selector: string) => Array<{ attributes: (name: string) => string | undefined }> }) {
  return wrapper.findAll('a').map(a => a.attributes('href'))
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  served = providersAnswer
  coverageServed = () => dailyClimateSummaryCoverage()
  Reflect.deleteProperty(navigator, 'clipboard')
})

describe('provider Page', () => {
  it('asks for the providers alone, and for the coverage of no network until its list is opened', async () => {
    const asked: Array<{ path: string, query: Record<string, unknown> }> = []
    served = (event) => {
      asked.push({ path: 'providers', query: getQuery(event) })
      return providersAnswer()
    }
    coverageServed = (event) => {
      asked.push({ path: 'coverage', query: getQuery(event) })
      return dailyClimateSummaryCoverage()
    }
    const wrapper = await mountProvider('dwd')

    expect(asked).toEqual([{ path: 'providers', query: {} }])
    expect(wrapper.text()).not.toContain('Climate summary')

    await openDatasets(wrapper, 'observation')

    // and then for the one network, which shows its resolutions and datasets by the names the app gives them
    await vi.waitFor(() => expect(wrapper.text()).toContain('Climate summary'))
    expect(asked).toEqual([
      { path: 'providers', query: {} },
      { path: 'coverage', query: { provider: 'dwd', network: 'observation' } },
    ])
  })

  it('names the provider, in English and in its own words, with its country', async () => {
    const wrapper = await mountProvider('dwd')
    const text = wrapper.text()

    expect(wrapper.find('h1').text()).toBe('German Weather Service')
    expect(text).toContain('Deutscher Wetterdienst')
    expect(text).toContain('Germany')
    expect(text).toContain('🇩🇪')
    // the id a request names it by
    expect(wrapper.find('code').text()).toBe('dwd')
  })

  it('links to the licence and gives the identifier, and the credit line to give', async () => {
    const wrapper = await mountProvider('dwd')

    const licence = wrapper.findAll('a').find(a => a.text() === 'Creative Commons Attribution 4.0 International')
    expect(licence?.attributes('href')).toBe('https://creativecommons.org/licenses/by/4.0/')
    expect(licence?.attributes('target')).toBe('_blank')
    expect(wrapper.text()).toContain('CC-BY-4.0')
    expect(wrapper.text()).toContain('Source: Deutscher Wetterdienst')
  })

  it('says so when the provider states no licence and no credit line', async () => {
    const wrapper = await mountProvider('aemet')
    const text = wrapper.text()

    expect(text).toContain('No licence stated')
    expect(text).toContain('The provider states no credit line.')
    expect(text).not.toContain('Copy')
  })

  it('copies the credit line', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    const wrapper = await mountProvider('dwd')

    const copy = wrapper.findAll('button').find(button => button.text() === 'Copy')!
    await copy.trigger('click')

    await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith('Source: Deutscher Wetterdienst'))
    await vi.waitFor(() => expect(wrapper.text()).toContain('Copied'))
  })

  it('lists the networks with their kind, source and what they offer', async () => {
    const wrapper = await mountProvider('dwd')
    const networks = wrapper.findAll('li').filter(li => li.find('h3').exists())
    const observation = networks.find(li => li.find('h3').text() === 'observation')!
    const text = observation.text()

    expect(text).toContain('Measurements')
    expect(text).toContain('© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)')
    expect(text).toContain('Parameters: 12')
    const source = observation.findAll('a').find(a => a.text() === 'Source')
    expect(source?.attributes('href')).toBe('https://opendata.dwd.de/climate_environment/CDC/')
  })

  it('lists the resolutions and datasets of a network, with the number of parameters of each', async () => {
    const wrapper = await mountProvider('dwd')
    await openDatasets(wrapper, 'observation')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Climate summary'))
    const observation = wrapper.findAll('li').find(li => li.find('h3').exists() && li.find('h3').text() === 'observation')!
    expect(observation.text()).toContain('Daily')
    expect(observation.text()).toContain('Climate summary')
    expect(observation.text()).toContain('(1)')
  })

  it('tells why the datasets of a network are missing, with a way to ask again, and the rest of the page stays', async () => {
    let asked = 0
    coverageServed = (event) => {
      asked++
      // a 404 is not asked again by itself, as a 502 is
      if (asked === 1) {
        setResponseStatus(event, 404)
        return { type: 'urn:wetterdienst:problem:unknown-network', title: 'Not Found', status: 404, detail: 'Coverage is not available for this network.' }
      }
      return dailyClimateSummaryCoverage()
    }
    const wrapper = await mountProvider('dwd')
    await openDatasets(wrapper, 'observation')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Coverage is not available for this network.'))
    expect(wrapper.find('h1').text()).toBe('German Weather Service')
    await wrapper.findAll('button').find(button => button.text() === 'Retry')!.trigger('click')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Climate summary'))
    expect(asked).toBe(2)
  })

  it('says a network without resolutions is no time series, and does not offer to explore it', async () => {
    const wrapper = await mountProvider('dwd')
    const radar = wrapper.findAll('li').find(li => li.find('h3').exists() && li.find('h3').text() === 'radar')!

    expect(radar.text()).toContain('Radar')
    expect(radar.text()).toContain('Not a time series: nothing to list here.')
    expect(radar.findAll('a').map(a => a.attributes('href'))).not.toContain('/explorer?provider=dwd&network=radar')
  })

  it('opens the explorer on the provider and network, and the station history only for DWD observation', async () => {
    const dwd = await mountProvider('dwd')
    const links = hrefs(dwd)
    expect(links).toContain('/explorer?provider=dwd&network=observation')
    expect(links.filter(href => href === '/history')).toHaveLength(1)

    const aemet = await mountProvider('aemet')
    expect(hrefs(aemet)).toContain('/explorer?provider=aemet&network=observation')
    expect(hrefs(aemet)).not.toContain('/history')
  })

  it('marks a network that needs credentials, and one that needs a date', async () => {
    const wrapper = await mountProvider('aemet')

    expect(wrapper.text()).toContain('Credentials required')
    expect(wrapper.text()).toContain('Date required')
    expect((await mountProvider('dwd')).text()).not.toContain('Credentials required')
  })

  it('writes a provider of several countries as that, not as a country', async () => {
    const wrapper = await mountProvider('eumetnet')

    expect(wrapper.text()).toContain('Several countries')
    expect(wrapper.text()).toContain('🌐')
    expect(wrapper.text()).not.toContain('Europe')
  })

  it('says so for a provider there is none of, and leads back to the list', async () => {
    const wrapper = await mountProvider('nowhere')

    expect(wrapper.text()).toContain('There is no provider called “nowhere”.')
    expect(hrefs(wrapper)).toContain('/providers')
  })

  it('tells why the page is missing, with a way to ask again', async () => {
    served = (event) => {
      setResponseStatus(event, 502)
      return { type: 'urn:wetterdienst:problem:backend-unreachable', title: 'Bad Gateway', status: 502, detail: 'The backend could not be reached.' }
    }
    const wrapper = await mountProvider('dwd')

    expect(wrapper.text()).toContain('Request failed')
    expect(wrapper.text()).toContain('The backend could not be reached.')
    expect(wrapper.text()).not.toContain('There is no provider')
  })
})
