import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AboutPage from '~/pages/about.vue'

describe('about Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(AboutPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('describes the project, which the home page used to', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(AboutPage)
    const text = wrapper.text()

    expect(text).toContain('About Wetterdienst')
    expect(text).toContain('MIT')
  })

  it('gives the maintainer a write-up and the co-author a flat entry', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(AboutPage)
    const text = wrapper.text()

    expect(text).toContain('Benjamin Gutzmann')
    expect(text).toContain('Maintainer of Wetterdienst')
    expect(text).toContain('Hamburg')
    expect(text).toContain('benjamin@eobs.org')

    // Andreas is listed flat on purpose: name and contact, no write-up
    expect(text).toContain('Andreas Motl')
    expect(text).toContain('andreas.motl@panodata.org')
  })

  it('carries the maintainer\'s own account, not a placeholder', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(AboutPage)
    const text = wrapper.text()

    expect(text).toContain('Dresden')
    // the placeholder this replaced was marked with guillemets and shipped with a warning banner
    expect(text).not.toContain('«')
  })

  it('counts the age from the birthday rather than printing a fixed number', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )
    // only Date is faked: faking timers as well would stall the async mount
    vi.useFakeTimers({ toFake: ['Date'] })

    try {
      vi.setSystemTime(new Date('2026-11-27T12:00:00'))
      expect((await mountSuspended(AboutPage)).text()).toContain('32 years old')

      // the day itself counts
      vi.setSystemTime(new Date('2026-11-28T12:00:00'))
      expect((await mountSuspended(AboutPage)).text()).toContain('33 years old')
    }
    finally {
      vi.useRealTimers()
    }
  })

  it('links to the source, the docs and the package', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(AboutPage)
    const html = wrapper.html()

    expect(html).toContain('github.com/earthobservations/wetterdienst')
    expect(html).toContain('wetterdienst.readthedocs.io')
    expect(html).toContain('pypi.org/project/wetterdienst')
    expect(html).toContain('CONTRIBUTORS.md')
  })
})
