import { sitemapXml } from '../../shared/utils/seo'

// The sitemap of the pages that are in the index (GH-3497, `shared/utils/seo.ts`), with the addresses of the
// instance (`NUXT_PUBLIC_SITE_URL`). `robots.txt` names it.
export default defineEventHandler((event) => {
  setResponseHeader(event, 'content-type', 'application/xml; charset=utf-8')
  setResponseHeader(event, 'cache-control', 'public, max-age=3600')
  return sitemapXml(useRuntimeConfig(event).public.siteUrl)
})
