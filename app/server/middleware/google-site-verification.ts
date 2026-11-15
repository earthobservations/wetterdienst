import { verificationFile, verificationName } from '../utils/googleSiteVerification'

// Answers the file that Google Search Console asks for to verify the site (GH-4108): `GET` or `HEAD` of exactly
// `/<name>.html`, with the name of `NUXT_GOOGLE_SITE_VERIFICATION`. Every other request, and every request while the
// setting is empty or is no name (`server/plugins/google-site-verification.ts` says so at start), goes on to
// the next handler as it did: another `google<hex>.html` is the shell's 200 as before, not a file of ours.
// It answers before the shell is rendered, so `server/plugins/seo-head.ts` (the `render:html` hook) does not meet it.
export default defineEventHandler((event) => {
  if (event.method !== 'GET' && event.method !== 'HEAD')
    return
  const name = verificationName(useRuntimeConfig(event).googleSiteVerification)
  if (!name)
    return
  const { path, body } = verificationFile(name)
  if (event.path.split('?', 1)[0] !== path)
    return

  setResponseHeader(event, 'content-type', 'text/html; charset=utf-8')
  setResponseHeader(event, 'cache-control', 'public, max-age=3600')
  return body
})
