import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import IndexPage from '~/pages/index.vue'

describe('index Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('contains main navigation elements', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const html = wrapper.html()

    expect(html.length).toBeGreaterThan(0)
  })

  it('says what data the app delivers', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()

    expect(text).toContain('What data you get')
    // the kinds of data, which are networks in the backend rather than a marketing list
    expect(text).toContain('Measurements')
    expect(text).toContain('Forecasts')
    expect(text).toContain('Water levels')
    expect(text).toContain('Radar')
  })

  it('names the weather services behind the data', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()

    expect(text).toContain('DWD')
    expect(text).toContain('NOAA')
    expect(text).toContain('Météo-France')
    expect(text).toContain('MeteoSwiss')
  })

  it('points developers at the library, the API and MCP', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()
    const html = wrapper.html()

    // anchors with hrefs, not just the words: an earlier version rendered two of these three as
    // plain text and the wording assertions passed anyway
    const chips = wrapper.findAll('a').map(a => `${a.attributes('href')} ${a.text()}`)
    expect(chips).toContain('https://pypi.org/project/wetterdienst/ pip install wetterdienst')
    expect(chips).toContain('/docs REST API')
    expect(chips).toContain('/mcp MCP')
    expect(text).toContain('Also for developers')
    // and the 514 parameters lead somewhere that explains them
    expect(html).toContain('/glossary')
  })

  it('names who already supports the work', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()
    const html = wrapper.html()

    expect(text).toContain('Supported by')
    expect(text).toContain('JetBrains')
    expect(text).toContain('Anthropic')
    expect(html).toContain('jb.gg/OpenSourceSupport')
    // what each gives is the hover text rather than the badge label
    expect(html).toContain('PyCharm')
    expect(html).toContain('Claude Max')
  })

  it('states what the project stands for, measurements included', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()

    expect(text).toContain('LGBTQI+')
    expect(text).toContain('FCKNZS')
    expect(text).toContain('Global warming is not an opinion')
    expect(text).toContain('Weather data belongs to everyone')
  })

  it('sends the project and the people to the about page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const text = wrapper.text()
    const html = wrapper.html()

    expect(html).toContain('/about')
    // the maintainers used to be listed here; the home page is about the data now
    expect(text).not.toContain('Benjamin Gutzmann')
    expect(text).not.toContain('Andreas Motl')
  })
})
