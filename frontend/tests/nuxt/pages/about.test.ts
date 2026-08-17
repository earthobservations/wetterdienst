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
