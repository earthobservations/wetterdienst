import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import ProvidersPage from '~/pages/providers/index.vue'
import { providersResponse } from '../fixtures/providers'

// `useFetch` keys the answer by name, so the list and the detail page share one request: cleared
// between tests, or a later test is served the answer of the one before
const mounted: Array<{ unmount: () => void }> = []
let served: (event: H3Event) => unknown = () => providersResponse()
// registered once: re-registering the same path in a later test does not replace the handler
registerEndpoint('/api/providers', event => served(event))

async function mountProviders() {
  const wrapper = await mountSuspended(ProvidersPage)
  mounted.push(wrapper)
  await vi.waitFor(() => expect((wrapper.vm as any).pending).toBe(false), { timeout: 5000 })
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  served = () => providersResponse()
})

describe('providers Page', () => {
  it('lists each provider by name, with its country and a link to its page', async () => {
    const wrapper = await mountProviders()
    const text = wrapper.text()

    expect(text).toContain('Providers')
    for (const name of ['German Weather Service', 'State Meteorological Agency of Spain', 'Norwegian Meteorological Institute'])
      expect(text).toContain(name)
    // the provider's own name beside the English one, and the country as the backend names it
    expect(text).toContain('Deutscher Wetterdienst')
    expect(text).toContain('Germany')
    const links = wrapper.findAll('a').map(a => a.attributes('href'))
    expect(links).toContain('/providers/dwd')
    expect(links).toContain('/providers/aemet')
  })

  it('draws the flag of the country code, and a globe for a provider of several countries', async () => {
    const wrapper = await mountProviders()
    const text = wrapper.text()

    expect(text).toContain('🇩🇪')
    expect(text).toContain('🇪🇸')
    expect(text).toContain('🌐')
    expect(text).toContain('Several countries')
    // the flag is decoration: the country is written out beside it
    expect(wrapper.findAll('[aria-hidden="true"]').map(el => el.text())).toContain('🇩🇪')
  })

  it('sorts by the English name', async () => {
    const wrapper = await mountProviders()
    const shown = (wrapper.vm as any).providers.map((provider: { provider: string }) => provider.provider)

    // EUMETNET, Forecast Service, German Weather Service, Norwegian ..., State Meteorological ...
    expect(shown).toEqual(['eumetnet', 'mosmix', 'dwd', 'metno', 'aemet'])
  })

  it('tells the licence by its SPDX identifier, and says so when a provider states none', async () => {
    const wrapper = await mountProviders()
    const cards = wrapper.findAll('li')
    const card = (name: string) => cards.find(li => li.text().includes(name))!

    expect(card('German Weather Service').text()).toContain('CC-BY-4.0')
    expect(card('Norwegian Meteorological Institute').text()).toContain('CC-BY-4.0 OR NLOD-2.0')
    expect(card('State Meteorological Agency of Spain').text()).toContain('No licence stated')
  })

  it('marks the providers whose networks need credentials', async () => {
    const wrapper = await mountProviders()
    const withKey = wrapper.findAll('li').filter(li => li.text().includes('Credentials required'))

    expect(withKey.map(li => li.text())).toEqual([
      expect.stringContaining('Norwegian Meteorological Institute'),
      expect.stringContaining('State Meteorological Agency of Spain'),
    ])
  })

  it('counts the networks and parameters of each provider', async () => {
    const wrapper = await mountProviders()
    const dwd = wrapper.findAll('li').find(li => li.text().includes('German Weather Service'))!

    expect(dwd.text()).toContain('Networks: 2')
    expect(dwd.text()).toContain('Parameters: 12')
  })

  it('finds a provider by its id, either name, its country or the code of it', async () => {
    const wrapper = await mountProviders()
    const vm = wrapper.vm as any
    const found = async (term: string) => {
      vm.search = term
      await wrapper.vm.$nextTick()
      return vm.providers.map((provider: { provider: string }) => provider.provider)
    }

    expect(await found('DWD')).toEqual(['dwd'])
    expect(await found('wetterdienst')).toEqual(['dwd'])
    expect(await found('norway')).toEqual(['metno'])
    expect(await found('es')).toEqual(expect.arrayContaining(['aemet']))
    expect(await found(' LU ')).toEqual(['mosmix'])
  })

  it('narrows to the providers with a kind of network', async () => {
    const wrapper = await mountProviders()
    const vm = wrapper.vm as any

    vm.kind = 'radar'
    await wrapper.vm.$nextTick()
    expect(vm.providers.map((provider: { provider: string }) => provider.provider)).toEqual(['eumetnet', 'dwd'])
    // the options are the kinds there are, by the names the home page gives them
    expect(vm.kindItems.map((item: { label: string }) => item.label)).toEqual(
      expect.arrayContaining(['All kinds of data', 'Measurements', 'Forecasts', 'Radar']),
    )
    expect(vm.kindItems.map((item: { label: string }) => item.label)).not.toContain('Derived data')
  })

  it('says how many are shown of how many there are', async () => {
    const wrapper = await mountProviders()
    expect(wrapper.text()).toContain('Showing 5 of 5')

    ;(wrapper.vm as any).search = 'norway'
    await vi.waitFor(() => expect(wrapper.text()).toContain('Showing 1 of 5'))
  })

  it('says so when nothing matches', async () => {
    const wrapper = await mountProviders()

    ;(wrapper.vm as any).search = 'nowhere at all'
    await vi.waitFor(() => expect(wrapper.text()).toContain('No provider matches your search.'))
  })

  it('tells why the list is missing, with a way to ask again', async () => {
    served = (event) => {
      setResponseStatus(event, 502)
      return { type: 'urn:wetterdienst:problem:backend-unreachable', title: 'Bad Gateway', status: 502, detail: 'The backend could not be reached.' }
    }
    const wrapper = await mountProviders()

    expect(wrapper.text()).toContain('Request failed')
    expect(wrapper.text()).toContain('The backend could not be reached.')
    const retry = wrapper.findAll('button').find(button => button.text() === 'Retry')
    expect(retry).toBeDefined()

    served = () => providersResponse()
    await retry!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('German Weather Service'))
    expect(wrapper.text()).not.toContain('Request failed')
  })
})
