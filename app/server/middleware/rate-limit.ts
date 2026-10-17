// Counts the requests that cost something (GH-3093): `values`, `stations`, `interpolate`, `summarize`,
// `stripes`, `history`, whatever else the backend serves but its catalogue, and the `/mcp` proxy, per client,
// and answers a 429 past the limit. The pages, the assets and the catalogue routes are not counted: an
// interactive session asks for those all the time. What is counted and how the client is told apart is in
// `~/server/utils/rateLimit`; the limit, its window and the header to read the client from are
// `runtimeConfig.rateLimit` (`nuxt.config.ts`), set at run time with `NUXT_RATE_LIMIT_*`.
//
// This replaces the limiter of nuxt-security (switched off in `nuxt.config.ts`), which counted every route
// in one bucket, and read the client from the leftmost `X-Forwarded-For` whoever sent it.
const limiter = createRateLimiter()

export default defineEventHandler((event) => {
  const { rateLimit } = useRuntimeConfig(event)
  // the options request of a preflight carries no work
  if (!rateLimit.enabled || event.method === 'OPTIONS' || !isLimited(event.path))
    return

  const tokens = positiveInteger(rateLimit.tokens, RATE_LIMIT_DEFAULTS.tokens)
  const windowMs = positiveInteger(rateLimit.windowSeconds, RATE_LIMIT_DEFAULTS.windowSeconds) * 1000
  const header = String(rateLimit.clientIpHeader ?? '').trim().toLowerCase()
  const key = clientKey(getRequestIP(event), header, header ? getRequestHeader(event, header) : undefined)

  const result = limiter.take(key, tokens, windowMs)
  setResponseHeader(event, 'x-ratelimit-limit', tokens)
  setResponseHeader(event, 'x-ratelimit-remaining', result.remaining)
  setResponseHeader(event, 'x-ratelimit-reset', Math.ceil(result.resetAt / 1000))
  if (result.allowed)
    return

  // a problem of the kind the app answers elsewhere (docs/usage/restapi.md, "Errors")
  const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
  const retryAfter = Math.max(1, Math.ceil((result.resetAt - Date.now()) / 1000))
  setResponseStatus(event, 429)
  setResponseHeader(event, 'content-type', 'application/problem+json')
  setResponseHeader(event, 'retry-after', retryAfter)
  setResponseHeader(event, 'x-request-id', requestId)
  return {
    type: 'urn:wetterdienst:problem:rate-limited',
    title: 'Too Many Requests',
    status: 429,
    detail: `This client sent more than ${tokens} requests for data in ${windowMs / 1000} seconds. Retry in ${retryAfter} seconds.`,
    instance: `urn:wetterdienst:request:${requestId}`,
    request_id: requestId,
  } satisfies ApiErrorResponse
})
