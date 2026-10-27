import { robotsTxt } from '../../shared/utils/seo'

// What `public/robots.txt` was, with the `Sitemap:` line of the instance's own address (GH-3497): a file of
// `public/` is the same on every instance, and one that names the hosted instance's sitemap on another is wrong.
export default defineEventHandler((event) => {
  setResponseHeader(event, 'content-type', 'text/plain; charset=utf-8')
  setResponseHeader(event, 'cache-control', 'public, max-age=3600')
  return robotsTxt(useRuntimeConfig(event).public.siteUrl)
})
