import { parseAcceptLanguage, pickLocale } from '../../shared/utils/language'
import { LANGUAGE_COOKIE } from '../../shared/utils/locales'
import { providerIdOfPath } from '../../shared/utils/seo'
import { useApiBase } from '../utils/apiBase'
import { applySeoHead, requestPath, seoHead } from '../utils/seoHead'
import { loadProviders } from '../utils/seoProviders'

// Puts the title, description, canonical link, `og:*` and `twitter:*` tags of the path into the shell, and a
// `<noscript>` text, for the crawler and the link preview that run no script (GH-3497, `server/utils/seoHead.ts`).
// It adds to the HTML Nitro is about to send, in the hook that nuxt-security's nonce plugin also uses, so the
// page stays one that is rendered for each request and carries its nonce: nothing here is a file that is served
// as it was built, which no nonce could be in.
//
// The head is in the language the app will show the visitor, chosen as the app chooses it (the `wd_lang` cookie,
// else the browser's language, else German; `shared/utils/language.ts`, GH-4106), so the raw HTML and the page
// agree about the language of the URL.
//
// The page of a provider (`/providers/dwd`) is told by its provider, which the backend's list says (GH-4119,
// `server/utils/seoProviders.ts`): a request for such a path reads the list, held in the process, and no other
// request asks for it. Where the list is not known the path is told as the site, as an id that is not in it is.
export default defineNitroPlugin((nitroApp) => {
  nitroApp.hooks.hook('render:html', async (html, { event }) => {
    const locale = pickLocale(getCookie(event, LANGUAGE_COOKIE), parseAcceptLanguage(getRequestHeader(event, 'accept-language')))
    const path = requestPath(event.path)
    const providers = providerIdOfPath(path) === undefined ? [] : await loadProviders(useApiBase())
    const head = seoHead(path, locale, useRuntimeConfig(event).public.siteUrl, providers)

    applySeoHead(html, head)
    // the language of the page depends on the cookie and on the header
    appendResponseHeader(event, 'vary', 'Cookie, Accept-Language')
    // the header says it for a client that asks only for that, and for the widget in every case
    if (head.noindex)
      setResponseHeader(event, 'x-robots-tag', 'noindex')
  })
})
