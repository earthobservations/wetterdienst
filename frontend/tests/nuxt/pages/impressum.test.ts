import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ImpressumPage from '~/pages/impressum.vue'

describe('impressum Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays legal notice heading', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    const text = wrapper.text()

    expect(text).toContain('Legal notice')
  })

  it('displays provider information pursuant to § 5 DDG', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    const text = wrapper.text()

    expect(text).toContain('§ 5 DDG')
    expect(text).toContain('Benjamin Gutzmann')
  })

  it('shows the operator address with no unfilled placeholders', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    const text = wrapper.text()

    // The operator details are filled in, so no «…» placeholders should remain.
    expect(text).not.toContain('«')
    expect(text).toContain('Falkenbergsweg 26')
    expect(text).toContain('21149 Hamburg')
    expect(text).toContain('§ 18 (2) MStV')
  })

  it('displays disclaimer section', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    const text = wrapper.text()

    expect(text).toContain('Disclaimer')
    expect(text).toContain('Content')
  })

  it('displays open source information', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    const text = wrapper.text()

    expect(text).toContain('Open source')
    expect(text).toContain('MIT License')
  })

  it('contains email contact link', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    const html = wrapper.html()

    expect(html).toContain('mailto:benjamin@eobs.org')
  })
})
