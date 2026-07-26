// Pass-through proxy for the backend's MCP endpoint so it is reachable on the frontend origin
// (e.g. https://wetterdienst.eobs.org/mcp). Unlike the JSON `/api/**` proxy, MCP uses the
// streamable-HTTP transport (POST for requests, GET for the SSE stream, DELETE to end a session,
// plus the `mcp-session-id` header), so this forwards the raw request/response with all methods,
// headers and streaming intact via `proxyRequest` rather than re-issuing a `$fetch`.
export default defineEventHandler(async (event) => {
  const {
    public: { apiBase },
  } = useRuntimeConfig()
  // apiBase points at the backend's `/api` root; the MCP endpoint lives at the backend origin's /mcp.
  const target = `${new URL(apiBase).origin}/mcp`
  // h3 strips the `accept` header when proxying, but the MCP streamable-HTTP transport requires
  // `Accept: application/json, text/event-stream`; re-add the client's accept header explicitly.
  return proxyRequest(event, target, {
    headers: {
      accept: getRequestHeader(event, 'accept') || 'application/json, text/event-stream',
    },
  })
})
