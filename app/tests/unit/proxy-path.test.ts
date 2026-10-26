import { describe, expect, it } from 'vitest'
import { urlUnder } from '../../server/utils/proxyPath'

// `urlUnder` is what the `/mcp` proxy asks before it fetches: the URL of the client's path at the backend, if the
// path still is under the proxy's own once it is resolved as a URL is when it is fetched.
const ORIGIN = 'http://backend:7890'

describe('urlUnder', () => {
  it.each([
    ['/mcp', 'http://backend:7890/mcp'],
    ['/mcp/', 'http://backend:7890/mcp/'],
    ['/mcp/v1', 'http://backend:7890/mcp/v1'],
    ['/mcp/v1?a=b&c=d', 'http://backend:7890/mcp/v1?a=b&c=d'],
    ['/mcp/v2/../v1', 'http://backend:7890/mcp/v1'],
    ['/mcp/./v1', 'http://backend:7890/mcp/v1'],
    ['/mcp/..%2fhealth', 'http://backend:7890/mcp/..%2fhealth'],
  ])('keeps %s', (path, expected) => {
    expect(urlUnder(ORIGIN, path, '/mcp')).toBe(expected)
  })

  it.each([
    '/mcp/..',
    '/mcp/../health',
    '/mcp/%2e%2e/health',
    '/mcp/%2E%2E/health',
    '/mcp/v1/../../health',
    '/mcp/..\\health',
    '/mcp/../mcp2',
    '/mcp2',
    '/mcpx/v1',
    '/health',
  ])('refuses %s', (path) => {
    expect(urlUnder(ORIGIN, path, '/mcp')).toBeUndefined()
  })

  it('keeps the host, whatever the path is made of', () => {
    expect(urlUnder(ORIGIN, '/mcp/@evil.example/x', '/mcp')).toBe('http://backend:7890/mcp/@evil.example/x')
    expect(urlUnder(ORIGIN, '/mcp//evil.example/x', '/mcp')).toBe('http://backend:7890/mcp//evil.example/x')
  })
})
