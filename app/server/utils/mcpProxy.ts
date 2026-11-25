import type { H3Event } from 'h3'
import { Buffer } from 'node:buffer'
import { useApiBase } from './apiBase'
import { answerInternalError, answerNotFound, answerPayloadTooLarge, urlUnder } from './proxyPath'
import { requestIdOf } from './requestId'

// Shared handler that proxies the app's `/mcp` and `/mcp/v1` (and any sub-path) through to the backend's MCP
// endpoint so it is reachable on the app origin (e.g. https://wetterdienst.eobs.org/mcp/v1).
//
// Unlike the JSON `/api/**` proxy, MCP uses the streamable-HTTP transport (POST for requests, GET for
// the SSE stream, DELETE to end a session, plus the `mcp-session-id` header), so this forwards the
// raw request/response with all methods and streaming intact via `sendProxy` rather than
// re-issuing a `$fetch`.

// The MCP streamable-HTTP transport requires this exact pair and does a literal check on the header.
const MCP_ACCEPT = 'application/json, text/event-stream'

// What of the client's request goes on to the backend: the headers the transport itself uses (the session, the
// protocol version, the resumption point of a stream, the body's type) and the request id. Nothing else of the
// client is the backend's business, `cookie` and `authorization` least (GH-3095): `proxyRequest` forwarded all
// of them, and a backend that one day reads either would have taken the credentials of a client of this app for
// its own.
const FORWARDED_HEADERS = ['content-type', 'mcp-session-id', 'mcp-protocol-version', 'last-event-id', 'x-request-id']

// The largest request body the proxy takes, the backend's own: the MCP SDK's `DEFAULT_MAX_REQUEST_BODY_SIZE`
// (4 MiB), which its `RequestBodyLimitMiddleware` refuses a body over. The proxy refuses it first, since it holds
// a body in memory to forward it, and a caller must not make it hold one of any size (GH-4362).
//
// A client gets this limit, and no other, because `/mcp` has no `requestSizeLimiter` of nuxt-security's (its
// 2,000,000 bytes would answer 413 first, with an h3 error body, and for a body of 2 to 4 MiB that the backend
// takes), see `routeRules` of `nuxt.config.ts`, and the app has no `xssValidator` (it read a whole POST body before
// this handler ran, so nothing here could limit it, GH-4364): see `security` there.
export const MAX_BODY_BYTES = 4 * 1024 * 1024

// h3's mark on a request whose body `readBody` or `readRawBody` has read (and cached)
const RAW_BODY = Symbol.for('h3RawBody')

const PAYLOAD_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

/**
 * Reads the body of the request, never more than `limit` bytes of it.
 *
 * A declared `Content-Length` over `limit` is answered without reading a byte. For a chunked body, the read
 * stops when it passes `limit`, which closes the connection: the 413 is best effort there, and a client that is
 * still sending may see the connection reset instead (the body is not drained, since a client of MCP sends its
 * length). The request is paused, not destroyed, and the answer closes the connection.
 *
 * @param event The request
 * @param limit The most bytes to take
 * @returns The body, `undefined` if there is none (or it cannot be read), `'too-large'` over `limit`, or
 * `'consumed'` if something in front of the handler has read the stream already (its bytes are gone from it, and
 * forwarding what is left would send an empty body)
 */
async function readBodyUpTo(event: H3Event, limit: number): Promise<Uint8Array<ArrayBuffer> | undefined | 'too-large' | 'consumed'> {
  const req = event.node.req
  if (RAW_BODY in req || req.readableEnded)
    return 'consumed'
  const declared = Number(getRequestHeader(event, 'content-length'))
  if (declared > limit)
    return 'too-large'
  // Listeners, not `for await`: leaving that loop early destroys the request, and nitro's graceful shutdown
  // (`res.on('finish', () => { req.socket._isIdle = true })`) then meets a null socket and throws an uncaught
  // exception for every oversized body. Here the request is only paused, and the socket closes after the 413.
  return new Promise((resolve) => {
    const chunks: Buffer[] = []
    let size = 0
    function done(result: Uint8Array<ArrayBuffer> | undefined | 'too-large'): void {
      req.off('data', onData)
      req.off('end', onEnd)
      req.off('error', onError)
      req.off('close', onError)
      if (result === 'too-large')
        req.pause()
      resolve(result)
    }
    function onData(chunk: Buffer): void {
      size += chunk.length
      if (size > limit)
        return done('too-large')
      chunks.push(chunk)
    }
    function onEnd(): void {
      done(size ? new Uint8Array(Buffer.concat(chunks)) : undefined)
    }
    function onError(): void {
      done(undefined)
    }
    req.on('data', onData)
    req.on('end', onEnd)
    req.on('error', onError)
    req.on('close', onError)
  })
}

export function mcpProxyHandler() {
  return defineEventHandler(async (event) => {
    const apiBase = useApiBase()
    // Forward to the backend origin with the incoming path and query string, so that the exact `/mcp`, `/mcp/v1`
    // (and a later `/mcp/v2`), a trailing slash, and any future sub-path reach the backend. The path is resolved
    // first, as a URL is when it is fetched: the proxy is for what is under `/mcp`, and a path that resolves to
    // anything else (`/mcp/../health`) is a 404 and is not fetched.
    const target = urlUnder(new URL(apiBase).origin, event.path, '/mcp')
    if (!target)
      return answerNotFound(event, requestIdOf(getRequestHeader(event, 'x-request-id')))
    const headers: Record<string, string> = {}
    for (const name of FORWARDED_HEADERS) {
      const value = getRequestHeader(event, name)
      if (value)
        headers[name] = value
    }
    // The transport rejects a `*/*` (or missing) Accept with 406. Pass through an SSE-aware Accept unchanged,
    // otherwise send the required pair.
    const accept = getRequestHeader(event, 'accept') || ''
    headers.accept = accept.includes('text/event-stream') ? accept : MCP_ACCEPT
    const body = PAYLOAD_METHODS.has(event.method) ? await readBodyUpTo(event, MAX_BODY_BYTES) : undefined
    if (body === 'too-large')
      return answerPayloadTooLarge(event, requestIdOf(getRequestHeader(event, 'x-request-id')), MAX_BODY_BYTES)
    if (body === 'consumed') {
      // Never forward an empty body for one that was sent: a middleware reads the stream before this handler
      // (nuxt-security's `xssValidator` did, and `security` of `nuxt.config.ts` switches it off)
      const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
      console.error(`Request ${requestId} to ${event.path}: a middleware read the body before the /mcp proxy, which cannot forward it.`)
      return answerInternalError(event, requestId)
    }
    return sendProxy(event, target, {
      fetchOptions: { method: event.method, body, headers },
      onResponse() {
        // These describe the backend, not this origin, and are the backend's to own (as for the `/api` proxy)
        event.node.res.removeHeader('set-cookie')
        event.node.res.removeHeader('alt-svc')
        event.node.res.removeHeader('server')
      },
    })
  })
}
