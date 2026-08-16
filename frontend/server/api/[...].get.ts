type QueryValue = string | number | boolean | undefined | null
type QueryObject = Record<string, QueryValue | QueryValue[]>

function buildSearchParams(query: QueryObject): URLSearchParams {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, val]) => {
    if (val === undefined || val === null)
      return
    if (Array.isArray(val)) {
      val.forEach(v => params.append(key, String(v)))
    }
    else {
      params.append(key, String(val))
    }
  })
  return params
}

export default defineEventHandler(async (event): Promise<unknown> => {
  const { public: { apiBase } } = useRuntimeConfig()
  const fullPath = event.path.replace(/^\/api/, '') || '/'
  const path = fullPath.split('?')[0]
  const query = getQuery(event) as QueryObject

  const params = buildSearchParams(query)
  const queryString = params.toString()
  const url = `${apiBase}${path}${queryString ? `?${queryString}` : ''}`

  try {
    // Stream the upstream response straight through to the client. `$fetch` used to buffer the
    // whole body, parse it into JS objects and re-serialize it, so a proxied request cost roughly
    // three times the payload in heap -- and this route forwards anything under `/api`, so that
    // payload is bounded by what the backend will return, not by what the UI asks for.
    //
    // `sendProxy` rather than `proxyRequest`: the latter also forwards the client's request
    // headers (including `cookie` and `authorization`) to the backend, which `$fetch` never did.
    // This route is GET-only, so there is no request body to carry over either.
    //
    // Backend errors need no special handling anymore: FastAPI's error body is already the shape
    // we want, and `sendProxy` forwards a non-2xx status and body verbatim instead of throwing.
    return await sendProxy(event, url)
  }
  catch (error: unknown) {
    // A failure part-way through the body cannot be reported as an error. `sendProxy` writes the
    // status line with the first chunk, after which `setResponseStatus` is a no-op and h3 skips
    // `res.end()` for an already-handled event -- leaving the client on a truncated 200 that hangs
    // until it times out. Destroy the socket instead, so the transfer visibly breaks.
    if (event.handled) {
      event.node.res.destroy()
      return
    }

    // Backend unreachable. h3 wraps the connection failure as a 502 whose `message` is the constant
    // "Bad Gateway", so the diagnostic worth surfacing (ECONNREFUSED, DNS failure) is on `cause`.
    const fetchError = error as {
      statusCode?: number
      status?: number
      message?: string
      cause?: { message?: string }
    }
    const statusCode = fetchError?.statusCode || fetchError?.status || 502
    setResponseStatus(event, statusCode)

    return {
      detail: fetchError?.cause?.message || fetchError?.message || 'An error occurred',
    } satisfies ApiErrorResponse
  }
})
