import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ApiPage from '~/pages/api.vue'

// the page asks the backend whether it serves an MCP endpoint, through `$fetch` rather than the
// global one, so the endpoint is registered instead of the fetch being stubbed. Registered once:
// re-registering the same path in a later test does not replace the handler
let backend = { version: '0.0.0', mcp_enabled: true }
registerEndpoint('/api/version', () => backend)

describe('aPI Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays API endpoints', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('REST API')
    expect(text).toContain('Endpoints')
  })

  it('lists all API endpoints', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('coverage')
    expect(text).toContain('stations')
    expect(text).toContain('values')
    expect(text).toContain('interpolate')
    expect(text).toContain('summarize')
  })

  it('displays API examples', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('Examples')
  })

  it('advertises the MCP endpoint on this origin when the backend serves one', async () => {
    backend = { version: '0.0.0', mcp_enabled: true }

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('MCP endpoint')
    // the whole point is that the URL follows the origin the page is served from rather than being
    // hard-coded to the hosted instance, so assert the origin this test runs under -- `/mcp` alone
    // would pass on a hard-coded wetterdienst.eobs.org too
    expect(text).toContain(`${window.location.origin}/mcp`)
    // and the config snippet a user pastes carries that same URL
    expect(text).toContain('mcpServers')
    expect(text).toContain(`"url": "${window.location.origin}/mcp"`)
  })

  it('says nothing about MCP when the backend has no such endpoint', async () => {
    // an instance installed without the [mcp] extra has no /mcp route, so a paste-ready client
    // config would send every user to a 404
    backend = { version: '0.0.0', mcp_enabled: false }

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('Endpoints')
    expect(text).not.toContain('MCP endpoint')
    expect(text).not.toContain('mcpServers')
  })
})
