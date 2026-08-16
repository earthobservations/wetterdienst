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
    // Only reached when the backend is unreachable -- `sendProxy` raises a 502 with no upstream
    // response to forward, so we synthesize the FastAPI-compatible error shape ourselves.
    const fetchError = error as { statusCode?: number, status?: number, message?: string }
    const statusCode = fetchError?.statusCode || fetchError?.status || 502
    setResponseStatus(event, statusCode)

    return {
      detail: fetchError?.message || 'An error occurred',
    } satisfies ApiErrorResponse
  }
})
