// Proxies the backend's own OpenAPI pages -- `/docs` and `/openapi.json` -- onto this origin, so
// the hosted app can point at an interactive API reference of its own rather than at a page that
// only exists on the backend, which is not published. `/api/**` is proxied for data and `/mcp` for
// the agent transport; these two are the same idea for the documentation.
//
// GET-only and no request headers forwarded, like the `/api` proxy: there is nothing to send but a
// path, and the client's cookies are none of the backend's business.
export function backendDocsProxyHandler() {
  return defineEventHandler(async (event) => {
    const { public: { apiBase } } = useRuntimeConfig()
    // `apiBase` ends in /api; the docs live at the backend root next to it.
    const target = `${new URL(apiBase).origin}${event.path}`
    return sendProxy(event, target, {
      onResponse() {
        // Same hygiene as the data proxy: these headers describe the backend, not this origin.
        event.node.res.removeHeader('set-cookie')
        event.node.res.removeHeader('alt-svc')
        event.node.res.removeHeader('server')
      },
    })
  })
}
