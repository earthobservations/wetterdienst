// Starts Swagger UI on the page `server/routes/docs.ts` serves. A file of its own, not a script in the page, so
// that the page needs no inline script of the Content Security Policy's allowing.
window.ui = window.SwaggerUIBundle({
  url: '/openapi.json',
  dom_id: '#swagger-ui',
  layout: 'BaseLayout',
  deepLinking: true,
  showExtensions: true,
  showCommonExtensions: true,
  presets: [window.SwaggerUIBundle.presets.apis],
})
