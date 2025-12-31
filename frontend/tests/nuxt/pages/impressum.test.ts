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

    expect(text).toContain('Legal Notice')
  })

  it('displays responsible person information', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ImpressumPage)
    const text = wrapper.text()

    expect(text).toContain('Responsible Person')
    expect(text).toContain('Benjamin Gutzmann')
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

    expect(text).toContain('Open Source')
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
