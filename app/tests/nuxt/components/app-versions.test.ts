import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import AppVersions from '~/components/AppVersions.vue'
import pkg from '../../../package.json'

// The line under the settings of the navigation (GH-3518): the app's own version and the backend's, which the app
// asks `/api/version`. Registered once; what it answers is `served`, cleared between tests with the fetch's data.
let served: (event: H3Event) => unknown = () => ({ version: '0.178.0' })
registerEndpoint('/api/version', event => served(event))

const mounted: Array<{ unmount: () => void }> = []
async function mountVersions() {
  const wrapper = await mountSuspended(AppVersions)
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  served = () => ({ version: '0.178.0' })
})

describe('the versions under the settings', () => {
  it('names the app, from its package, and the backend, from its answer', async () => {
    const wrapper = await mountVersions()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Backend 0.178.0'))

    expect(wrapper.text()).toBe(`App ${pkg.version} · Backend 0.178.0`)
  })

  it('is a line of text for a screen reader, not a control', async () => {
    const wrapper = await mountVersions()

    expect(wrapper.element.tagName).toBe('P')
    expect(wrapper.find('a, button').exists()).toBe(false)
  })

  it('says "unknown" for the backend where it cannot be reached, and keeps the app\'s version', async () => {
    served = (event) => {
      setResponseStatus(event, 502)
      return { type: 'urn:wetterdienst:problem:backend-unreachable', title: 'Bad Gateway', status: 502 }
    }
    const wrapper = await mountVersions()
    await vi.waitFor(() => expect(wrapper.text()).toContain('unknown'))

    expect(wrapper.text()).toBe(`App ${pkg.version} · Backend unknown`)
  })

  it('says "unknown" for an answer that carries no version', async () => {
    served = () => ({})
    const wrapper = await mountVersions()
    await vi.waitFor(() => expect(wrapper.text()).toContain('unknown'))

    expect(wrapper.text()).toBe(`App ${pkg.version} · Backend unknown`)
  })

  it('holds the place of the backend\'s version until it has answered', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    served = async () => {
      await gate
      return { version: '0.178.0' }
    }
    const wrapper = await mountVersions()

    expect(wrapper.text()).toBe(`App ${pkg.version} · Backend …`)
    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Backend 0.178.0'))
  })
})
