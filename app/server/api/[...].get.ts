import { useApiBase } from '../utils/apiBase'

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

// The problem the app answers with when it cannot reach the backend, as the backend's own are written
// (docs/usage/restapi.md, "Errors"): a `type` that names the kind, `instance` and `request_id`, and the
// `Retry-After` of a 502, 503 or 504. The kind is the app's, not one of the backend's: the backend is what
// could not be reached, so it cannot answer it. It is always a 502, as `sendProxy` answers every failure to
// reach the backend, and a kind keeps its status.
const BACKEND_UNREACHABLE_TYPE = 'urn:wetterdienst:problem:backend-unreachable'
const RETRY_AFTER_SECONDS = 30
// the id of a client that is let through, as the backend lets it: plain, short text
const REQUEST_ID = /^[\w.~-]{1,128}$/

function requestIdOf(sent: string | undefined): string {
  return sent && REQUEST_ID.test(sent) ? sent : globalThis.crypto.randomUUID().replaceAll('-', '')
}

export default defineEventHandler(async (event): Promise<unknown> => {
  const apiBase = useApiBase()
  const fullPath = event.path.replace(/^\/api/, '') || '/'
  const path = fullPath.split('?')[0]
  const query = getQuery(event) as QueryObject

  const params = buildSearchParams(query)
  const queryString = params.toString()
  // The client's own request id, if it sent one, goes on to the backend, which answers with it and logs
  // its failures by it. Only that header: `sendProxy` forwards none of the client's others (cookies included).
  const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))

  // The proxy's contract is everything under `apiBase`. The path is the client's, and a URL is normalised when it
  // is fetched: `/api/../health` is the backend's `/health`, and `%2e%2e` is `..` as well. So the URL is
  // resolved here, and one that does not stay under `apiBase` is a 404 and is not fetched.
  const target = new URL(`${apiBase}${path}${queryString ? `?${queryString}` : ''}`)
  const base = new URL(apiBase).pathname.replace(/\/$/, '')
  if (target.pathname !== base && !target.pathname.startsWith(`${base}/`)) {
    setResponseStatus(event, 404)
    setResponseHeader(event, 'content-type', 'application/problem+json')
    setResponseHeader(event, 'x-request-id', requestId)
    return {
      type: 'urn:wetterdienst:problem:not-found',
      title: 'Not Found',
      status: 404,
      detail: 'Not Found',
      instance: `urn:wetterdienst:request:${requestId}`,
      request_id: requestId,
    } satisfies ApiErrorResponse
  }
  const url = target.href

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
    // Backend errors need no special handling anymore: the backend's error body (an RFC 9457
    // problem) is already the shape we want, and `sendProxy` forwards a non-2xx status and body
    // verbatim instead of throwing.
    return await sendProxy(event, url, {
      headers: { 'x-request-id': requestId },
      // Streaming also relays the backend's response headers, which buffering never did. Most are
      // harmless, but a few are the backend's to own rather than ours to republish under this
      // origin. `onResponse` runs after `sendProxy` has set them and before the first chunk, so
      // they can still be removed.
      onResponse() {
        // The backend sets no cookies today, but if that ever changes they would land scoped to the
        // app's origin instead of the backend's -- a session boundary we should not move by
        // accident.
        event.node.res.removeHeader('set-cookie')
        // Advertises HTTP/3 for whatever origin serves the response, so relaying it here would
        // claim support on the app's behalf.
        event.node.res.removeHeader('alt-svc')
        // No reason to tell clients which server stack sits behind the proxy.
        event.node.res.removeHeader('server')
      },
    })
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
    // "Bad Gateway"; the diagnostic worth having (ECONNREFUSED, DNS failure) is on `cause`, and it
    // names the backend's host and port. That is for whoever runs this app, so it goes to the server
    // log with the request id, and the client is answered a fixed text, as the backend answers its own 500s.
    const fetchError = error as { cause?: unknown }
    console.error(`Request ${requestId} to the backend for ${path} failed:`, fetchError?.cause ?? error)
    setResponseStatus(event, 502)
    setResponseHeader(event, 'content-type', 'application/problem+json')
    setResponseHeader(event, 'x-request-id', requestId)
    setResponseHeader(event, 'retry-after', RETRY_AFTER_SECONDS)

    return {
      type: BACKEND_UNREACHABLE_TYPE,
      title: 'Bad Gateway',
      status: 502,
      detail: 'The backend could not be reached. The cause is in the server log.',
      instance: `urn:wetterdienst:request:${requestId}`,
      request_id: requestId,
    } satisfies ApiErrorResponse
  }
})
