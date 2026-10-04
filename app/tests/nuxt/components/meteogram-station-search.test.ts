import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import MeteogramStationSearch from '~/components/MeteogramStationSearch.vue'

describe('the meteogram\'s station search whose list could not be fetched', () => {
  it('asks /api/stations once for a request answered with a 500', async () => {
    // counted at the endpoint, which a request reaches however it is made
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    }))
    const wrapper = await mountSuspended(MeteogramStationSearch)
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked).toBeGreaterThan(0)
      expect(vm.pending).toBe(false)
    })
    expect(asked).toBe(1)
  })
})

describe('the meteogram\'s station search whose list was answered with a 503 once', () => {
  it('asks /api/stations once more, and offers what that answer brings', async () => {
    // a 503 the first time only, as a proxy gives while the backend restarts
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      if (asked === 1) {
        setResponseStatus(event, 503)
        return { detail: 'Service Unavailable' }
      }
      return { stations: [{ station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }] }
    }))
    const wrapper = await mountSuspended(MeteogramStationSearch)
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.data.stations).toHaveLength(1))
    expect(asked).toBe(2)
  })
})
