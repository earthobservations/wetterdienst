// Swagger UI on this origin: the page of the REST API's reference, which reads `/openapi.json` (proxied from the
// backend, see ~/server/routes/openapi.json). The page and the two files it loads are the app's own
// (`modules/swagger-ui.ts`), so the page runs no script from anywhere else (GH-3094); it was the backend's page,
// proxied, which loaded Swagger UI from a CDN.
const PAGE = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wetterdienst REST API</title>
<link rel="icon" href="/favicon.ico">
<link rel="stylesheet" href="/_swagger-ui/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="/_swagger-ui/swagger-ui-bundle.js"></script>
<script src="/_swagger-ui/init.js"></script>
</body>
</html>
`

// The page's own policy, the app's does not reach a route that is no page of the app. Scripts and styles of this
// origin only (Swagger UI sets inline styles), images of it and data URLs, and calls to it: `/openapi.json` and
// the API a request is tried against.
const POLICY = [
  'default-src \'none\'',
  'script-src \'self\'',
  'style-src \'self\' \'unsafe-inline\'',
  'img-src \'self\' data:',
  'font-src \'self\' data:',
  'connect-src \'self\'',
  'base-uri \'none\'',
  'form-action \'self\'',
  'frame-ancestors \'self\'',
].join('; ')

export default defineEventHandler((event) => {
  setResponseHeader(event, 'content-type', 'text/html; charset=utf-8')
  setResponseHeader(event, 'content-security-policy', POLICY)
  return PAGE
})
