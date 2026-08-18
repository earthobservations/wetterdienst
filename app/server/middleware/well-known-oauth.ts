// MCP clients (e.g. Claude Desktop) probe `/.well-known/oauth-*` before connecting to `/mcp` to
// discover an OAuth authorization server. The wetterdienst `/mcp` server is open (no auth), so those
// paths must return 404 -- that is how a client concludes "no OAuth here" and connects anonymously.
//
// Without this, the Nuxt SPA catch-all answers `/.well-known/oauth-*` with a 200 `index.html`, which
// the client mistakes for OAuth metadata and then fails Dynamic Client Registration against (the
// "Registrierung beim Anmeldedienst ... fehlgeschlagen" error). Returning 404 fixes the connect flow.
export default defineEventHandler((event) => {
  if (event.path.startsWith('/.well-known/oauth-')) {
    throw createError({ statusCode: 404, statusMessage: 'Not Found' })
  }
})
