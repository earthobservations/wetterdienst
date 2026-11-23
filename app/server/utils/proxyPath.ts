import type { H3Event } from 'h3'

// What the app's proxies share about the path of a request: the backend URL it names, and the answer when that
// URL is not one the proxy is for. A proxy is for everything under one path of the backend (`/api`, `/mcp`).
//
// The path is the client's, and a URL is normalised when it is fetched: `/mcp/../health` is the backend's
// `/health`, and `%2e%2e` is `..` as well. So the URL is resolved here, before anything is fetched.

/**
 * The URL of `path` (with its query) at `origin`, if it stays under `prefix` once it is resolved.
 *
 * @param origin The backend's origin, `scheme://host[:port]`
 * @param path The path and query of the request, as the client wrote them
 * @param prefix The path the proxy is for, without a trailing slash (`/mcp`)
 * @returns The URL to fetch, or `undefined` if the resolved path is `prefix` or below it no longer
 */
export function urlUnder(origin: string, path: string, prefix: string): string | undefined {
  const url = new URL(`${origin}${path}`)
  return url.pathname === prefix || url.pathname.startsWith(`${prefix}/`) ? url.href : undefined
}

/**
 * Answers a 404 problem, as the `/api` proxy does for a path that leaves `/api`, and returns its body.
 *
 * @param event The request
 * @param requestId The id the answer carries
 * @returns The problem, for the handler to return
 */
export function answerNotFound(event: H3Event, requestId: string): ApiErrorResponse {
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
  }
}

/**
 * Answers a 413 problem, for a request body over the limit of the backend behind the proxy, and returns its body.
 *
 * @param event The request
 * @param requestId The id the answer carries
 * @param limit The limit in bytes, named in the detail
 * @returns The problem, for the handler to return
 */
export function answerPayloadTooLarge(event: H3Event, requestId: string, limit: number): ApiErrorResponse {
  setResponseStatus(event, 413)
  setResponseHeader(event, 'content-type', 'application/problem+json')
  setResponseHeader(event, 'x-request-id', requestId)
  // The rest of the body is not read, so the connection is not kept for another request
  setResponseHeader(event, 'connection', 'close')
  return {
    type: 'urn:wetterdienst:problem:payload-too-large',
    title: 'Payload Too Large',
    status: 413,
    detail: `The request body is over ${limit} bytes`,
    instance: `urn:wetterdienst:request:${requestId}`,
    request_id: requestId,
  }
}
