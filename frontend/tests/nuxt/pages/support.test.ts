import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SupportPage from '~/pages/support.vue'

describe('Support Page', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays support heading', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    const text = wrapper.text()
    
    expect(text).toContain('Support')
  })

  it('displays report issues section', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    const text = wrapper.text()
    
    expect(text).toContain('Report Issues')
    expect(text).toContain('Found a bug')
  })

  it('displays contribute section', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    const text = wrapper.text()
    
    expect(text).toContain('Contribute')
    expect(text).toContain('pull request')
  })

  it('displays discussions section', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    const text = wrapper.text()
    
    expect(text).toContain('Discussions')
  })

  it('displays donation options', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    const text = wrapper.text()
    
    expect(text).toContain('Support the Project')
  })

  it('contains GitHub sponsors link', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    const html = wrapper.html()
    
    expect(html).toContain('github.com/sponsors')
  })

  it('contains PayPal link', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(SupportPage)
    const html = wrapper.html()
    
    expect(html).toContain('paypal.me')
  })
})
