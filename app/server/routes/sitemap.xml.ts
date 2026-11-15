import { providerIds, sitemapXml } from '../../shared/utils/seo'
import { useApiBase } from '../utils/apiBase'
import { loadProviders } from '../utils/seoProviders'

// The sitemap of the pages that are in the index (GH-3497, `shared/utils/seo.ts`), with the addresses of the
// instance (`NUXT_PUBLIC_SITE_URL`), and the page of each provider of the backend's list (GH-4119). `robots.txt`
// names it.
export default defineEventHandler(async (event) => {
  const providers = providerIds(await loadProviders(useApiBase()))
  setResponseHeader(event, 'content-type', 'application/xml; charset=utf-8')
  // a sitemap made while the backend could not be reached has the fixed pages only: it is asked for again soon
  setResponseHeader(event, 'cache-control', `public, max-age=${providers.length > 0 ? 3600 : 60}`)
  return sitemapXml(useRuntimeConfig(event).public.siteUrl, providers)
})
