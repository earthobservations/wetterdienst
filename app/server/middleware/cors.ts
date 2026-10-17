// Same origin unless named (GH-3095): see `~/server/utils/cors`. The app answers no CORS header to a page of
// another origin; `NUXT_CORS_ALLOWED_ORIGINS` (a list separated by commas, or `*` for the old behaviour) lists the
// origins whose pages may read it, and answers their preflights.
//
// The headers a page may read from an answer, and send, are those a client of the API uses.
const EXPOSED = 'x-request-id, retry-after, link, x-ratelimit-limit, x-ratelimit-remaining, x-ratelimit-reset, mcp-session-id'
const METHODS = 'GET, HEAD, POST, DELETE, OPTIONS'

export default defineEventHandler((event) => {
  const allowed = parseAllowedOrigins(useRuntimeConfig(event).corsAllowedOrigins)
  if (allowed.length === 0)
    return
  const origin = getRequestHeader(event, 'origin')
  const headers = corsHeaders(origin, allowed)
  for (const [name, value] of Object.entries(headers))
    appendResponseHeader(event, name, value)
  if (!headers['access-control-allow-origin'])
    return
  appendResponseHeader(event, 'access-control-expose-headers', EXPOSED)
  const preflight = event.method === 'OPTIONS' && !!getRequestHeader(event, 'access-control-request-method')
  if (preflight) {
    appendResponseHeader(event, 'access-control-allow-methods', METHODS)
    appendResponseHeader(event, 'access-control-allow-headers', getRequestHeader(event, 'access-control-request-headers') ?? '*')
    setResponseHeader(event, 'access-control-max-age', 600)
    setResponseStatus(event, 204)
    return ''
  }
})
