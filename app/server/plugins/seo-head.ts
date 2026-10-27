import { applySeoHead, pickLocale, requestPath, seoHead } from '../utils/seoHead'

// Puts the title, description, canonical link, `og:*` and `twitter:*` tags of the path into the shell, and a
// `<noscript>` text, for the crawler and the link preview that run no script (GH-3497, `server/utils/seoHead.ts`).
// It adds to the HTML Nitro is about to send, in the hook that nuxt-security's nonce plugin also uses, so the
// page stays one that is rendered for each request and carries its nonce: nothing here is a file that is served
// as it was built, which no nonce could be in.
export default defineNitroPlugin((nitroApp) => {
  nitroApp.hooks.hook('render:html', (html, { event }) => {
    const locale = pickLocale(getCookie(event, 'wd_lang'), getRequestHeader(event, 'accept-language'))
    const path = requestPath(event.path)
    const head = seoHead(path, locale, useRuntimeConfig(event).public.siteUrl)

    applySeoHead(html, head)
    // the language of the page depends on the cookie and on the header
    appendResponseHeader(event, 'vary', 'Cookie, Accept-Language')
    // the header says it for a client that asks only for that, and for the widget in every case
    if (head.noindex)
      setResponseHeader(event, 'x-robots-tag', 'noindex')
  })
})
