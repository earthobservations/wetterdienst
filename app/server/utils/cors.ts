// Which web pages other than the app's own may read its answers (GH-3095).
//
// None, unless the operator names them. nuxt-security's `corsHandler` answered `access-control-allow-origin: *`
// on every response (also to a request with no `Origin`, which h3's `handleCors` does however it is configured),
// and its options are fixed when the app is built, so an image could not be given an origin at run time. The
// app's own page needs no CORS at all: it calls its own origin.

/** The origins of `NUXT_CORS_ALLOWED_ORIGINS`: a list separated by commas, each `scheme://host[:port]`, or `*` */
export function parseAllowedOrigins(value: unknown): string[] {
  return String(value ?? '')
    .split(',')
    .map(origin => origin.trim().replace(/\/+$/, ''))
    .filter(Boolean)
}

/**
 * What the response to a request from `origin` says about CORS.
 *
 * @param origin The request's `Origin` header, if any
 * @param allowed The origins the operator allows, as `parseAllowedOrigins` gives them
 * @returns The headers to set: none unless the origin is allowed. A list, even one that allows nobody the
 * request is from, is a reason for caches to tell the answers apart, so `vary` comes with it.
 */
export function corsHeaders(origin: string | undefined, allowed: string[]): Record<string, string> {
  if (allowed.length === 0)
    return {}
  const headers: Record<string, string> = { vary: 'Origin' }
  if (!origin)
    return headers
  if (allowed.includes('*'))
    return { 'access-control-allow-origin': '*', 'vary': 'Origin' }
  if (allowed.includes(origin))
    headers['access-control-allow-origin'] = origin
  return headers
}
