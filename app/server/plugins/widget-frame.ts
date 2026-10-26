import { isWidgetRequest, widgetPolicy } from '../utils/widgetFrame'

// Lets any origin frame `/widget`, and nothing else (GH-2607, see `server/utils/widgetFrame.ts`). `beforeResponse`
// is the last word on the headers of a response: it runs after nuxt-security has set its own, which it replaces
// for this one page.
export default defineNitroPlugin((nitroApp) => {
  nitroApp.hooks.hook('beforeResponse', (event) => {
    // `originalUrl` is the request line, which a mounted handler has not rewritten
    if (!isWidgetRequest(event.node.req.originalUrl ?? event.node.req.url))
      return
    const policy = widgetPolicy(event.node.res.getHeader('content-security-policy')?.toString())
    if (policy)
      event.node.res.setHeader('content-security-policy', policy)
    event.node.res.removeHeader('x-frame-options')
  })
})
