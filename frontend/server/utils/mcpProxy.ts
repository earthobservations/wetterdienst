// Shared handler that proxies the frontend's `/mcp` (and any sub-path) through to the backend's MCP
// endpoint so it is reachable on the frontend origin (e.g. https://wetterdienst.eobs.org/mcp).
//
// Unlike the JSON `/api/**` proxy, MCP uses the streamable-HTTP transport (POST for requests, GET for
// the SSE stream, DELETE to end a session, plus the `mcp-session-id` header), so this forwards the
// raw request/response with all methods, headers and streaming intact via `proxyRequest` rather than
// re-issuing a `$fetch`.

// The MCP streamable-HTTP transport requires this exact pair and does a literal check on the header.
const MCP_ACCEPT = 'application/json, text/event-stream'

export function mcpProxyHandler() {
  return defineEventHandler(async (event) => {
    const {
      public: { apiBase },
    } = useRuntimeConfig()
    // Forward faithfully to the backend origin, preserving the incoming path and query string so that
    // the exact `/mcp`, a trailing-slash `/mcp/`, and any future sub-path all reach the backend as-is.
    const target = `${new URL(apiBase).origin}${event.path}`
    // h3 strips the `accept` header when proxying, and the transport rejects a `*/*` (or missing)
    // Accept with 406. Pass through an SSE-aware Accept unchanged, otherwise send the required pair.
    const accept = getRequestHeader(event, 'accept') || ''
    return proxyRequest(event, target, {
      headers: {
        accept: accept.includes('text/event-stream') ? accept : MCP_ACCEPT,
      },
    })
  })
}
