import { isTextFilePath } from '../../shared/utils/seo'

// A path that ends in `.xml` or `.txt` is a file or a 404, never the app's shell (GH-3497). The shell answers every
// path it has no file or route for with a 200, and a crawler that asks for `/sitemap_index.xml` or `/ads.txt` read
// that HTML as the file. The files the app has (`/sitemap.xml` and `/robots.txt`, which are routes, and
// `/third-party-licenses.txt`, a file of the build) are not touched: see ALLOWED.
const ALLOWED = new Set(['/sitemap.xml', '/robots.txt', '/third-party-licenses.txt'])

export default defineEventHandler((event) => {
  if (event.method !== 'GET' && event.method !== 'HEAD')
    return
  const path = event.path.split('?', 1)[0] ?? ''
  if (isTextFilePath(path) && !ALLOWED.has(path))
    throw createError({ statusCode: 404, statusMessage: 'Not Found' })
})
