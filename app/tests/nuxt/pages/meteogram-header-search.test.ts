import type { VueWrapper } from '@vue/test-utils'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MeteogramPage from '~/pages/meteogram.vue'

// In a file of its own: the page's tests of the other file leave their pages mounted, and every one of them
// answers a change of the URL, which these tests count the requests of.

describe('the meteogram page followed to a station by the search of the header (GH-3518)', () => {
  const stations: Record<string, { station_id: string, name: string, latitude: number, longitude: number }> = {
    '01001': { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 },
    '10381': { station_id: '10381', name: 'BERLIN', latitude: 52.46, longitude: 13.31 },
  }
  let wrapper: VueWrapper | undefined
  const endpoints: Array<() => void> = []
  const stationRequests: string[] = []

  beforeEach(() => {
    stationRequests.length = 0
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    endpoints.push(registerEndpoint('/api/stations', (event) => {
      const id = String(getQuery(event).stations)
      stationRequests.push(id)
      const station = stations[id]
      return { stations: station ? [station] : [] }
    }))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
  })

  it('shows the station the URL names again after the page chose another one', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    // the reader picks another station in the page, which the page writes to the URL
    vm.selectedStation = stations['10381']
    await vi.waitFor(() => expect(useRoute().query.station).toBe('10381'))
    // and then searches the first one again in the header
    await navigateTo('/meteogram?station=01001')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
  })

  it('shows a station the reader chose and cleared when the header searches it', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram' })
    const vm = wrapper.vm as any
    vm.selectedStation = stations['10381']
    await vi.waitFor(() => expect(useRoute().query.station).toBe('10381'))
    vm.selectedStation = null
    await vi.waitFor(() => expect(useRoute().query.station).toBeUndefined())
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10381'))
  })

  it('does not carry the run chosen for one station over to the one the search names', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001&issue=2026-10-03T06:00:00' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    expect(vm.selectedIssue).toBe('2026-10-03T06:00:00')
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10381'))
    expect(vm.selectedIssue).toBe('')
    await vi.waitFor(() => expect(useRoute().query.issue).toBeUndefined())
  })

  it('fetches the values once for the station the search names, whatever run the one before had', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001&issue=2026-10-03T06:00:00' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await new Promise(resolve => setTimeout(resolve, 50))
    const valuesRequests = () => vi.mocked(globalThis.fetch).mock.calls.filter(([url]) => String(url).includes('/api/values?')).length
    const before = valuesRequests()
    await navigateTo('/meteogram?station=10381')
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('10381'))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(valuesRequests() - before).toBe(1)
  })

  it('asks again for a station that was not found, once the reader has moved the page on to a run', async () => {
    wrapper = await mountSuspended(MeteogramPage, { route: '/meteogram?station=01001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('01001'))
    await navigateTo('/meteogram?station=99999')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '99999')).toHaveLength(1))
    // the reader picks a run: the page writes the station it shows to the URL again
    vm.selectedIssue = '2026-10-03T06:00:00'
    await vi.waitFor(() => expect(useRoute().query.station).toBe('01001'))
    await navigateTo('/meteogram?station=99999')
    await vi.waitFor(() => expect(stationRequests.filter(id => id === '99999')).toHaveLength(2))
  })
})
