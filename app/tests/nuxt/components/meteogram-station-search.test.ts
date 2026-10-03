import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { describe, expect, it, vi } from 'vitest'
import MeteogramStationSearch from '~/components/MeteogramStationSearch.vue'

describe('the meteogram\'s station search whose list could not be fetched', () => {
  it('asks /api/stations once for a request answered with a 500', async () => {
    // counted at the endpoint, which a request reaches however it is made
    let asked = 0
    registerEndpoint('/api/stations', (event) => {
      asked++
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    })
    const wrapper = await mountSuspended(MeteogramStationSearch)
    const vm = wrapper.vm as any
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked).toBeGreaterThan(0)
      expect(vm.pending).toBe(false)
    })
    expect(asked).toBe(1)
    wrapper.unmount()
  })
})
