# Web app

The web app is a Nuxt app (`app/`), published as the image `ghcr.io/earthobservations/wetterdienst-app` and
served at [wetterdienst.eobs.org](https://wetterdienst.eobs.org). Its server does two things: it serves the pages,
and it proxies `/api`, `/mcp`, `/docs` and `/openapi.json` to the backend, so a browser only ever calls the origin
it loaded the page from. This page is for whoever runs one.

```bash
docker run --rm --publish=4000:4000 --env NUXT_PUBLIC_API_BASE=http://backend:3000/api ghcr.io/earthobservations/wetterdienst-app
```

`NUXT_PUBLIC_API_BASE` is the backend's `/api` (or `/api/v1`) URL. Only the app's server reads it; the browser never
does. Every other option below is an environment variable too, read when the server starts: no rebuild.

## Rate limit

The server limits what costs something, per client. It counts the requests to

- `/api/values`, `/api/stations`, `/api/interpolate`, `/api/summarize`, `/api/stripes/*` and `/api/history`,
  and any other route under `/api` that is not one of the catalogue routes below, and
- `/mcp` (a session is many small calls),

and answers the one past the limit with `429 Too Many Requests` and a problem of the kind
`urn:wetterdienst:problem:rate-limited`, with `Retry-After` (seconds). It does not count the pages, the assets,
`/docs` and `/openapi.json`, nor the catalogue routes that every page asks for: `/api/version`, `/api/settings`,
`/api/providers`, `/api/coverage`, `/api/glossary`, `/api/auth` and `/api/health`. The routes count together, one
limit for a client.

Every counted answer carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` (when the window
ends, in seconds since the epoch).

| Variable | Default | |
|---|---|---|
| `NUXT_RATE_LIMIT_TOKENS` | `300` | Requests per client in a window |
| `NUXT_RATE_LIMIT_WINDOW_SECONDS` | `300` | The window: 300 in 300 seconds is 60 a minute |
| `NUXT_RATE_LIMIT_ENABLED` | `true` | `false` switches the limit off |
| `NUXT_RATE_LIMIT_CLIENT_IP_HEADER` | empty | See below |

The count is kept in the memory of the server process: a restart resets it, and several instances count
separately.

### Who the client is

By default the client is the **address of the connection**, the one thing a client cannot choose. That is right when
users reach the app directly; behind a reverse proxy or a load balancer (and on some container networks) it
is the proxy's address, and all users share one count.

Name the header your proxy sets with `NUXT_RATE_LIMIT_CLIENT_IP_HEADER` (for instance `x-forwarded-for`,
`x-real-ip`, `cf-connecting-ip`) and the app reads the client from it instead. **Only do so when every request
reaches the app through that proxy, and the proxy sets the header itself.** Any client can write any header: if the
app can be reached without the proxy, or the proxy passes on what the client sent, a client picks its own address
and the limit is gone. A list (`x-forwarded-for: a, b, c`) is read from its end, the address the nearest proxy saw,
so a proxy that appends is as good as one that overwrites, but one proxy only: with more in a chain, name the header
the outermost one sets alone. A request without the header is counted under the address of the connection.

A limit in the proxy in front of the app and the backend is the real protection: the app limits what passes through
it, and a backend that is also reachable directly has no limit of its own.

## Other origins (CORS)

The app answers **no** `Access-Control-Allow-Origin` unless told to: only its own pages can read it. The app used to
answer `*` on everything, which let any web page read the API through the app, and a local instance be read by every
page its user visited.

`NUXT_CORS_ALLOWED_ORIGINS` lists the origins whose pages may read the app, separated by commas
(`https://dashboard.example,https://other.example`), and the app then answers them and their preflights. `*` is the
old behaviour. **If a page of another origin reads your instance, set it, or that page gets a CORS error after the
update.**

## What the app serves itself

Nothing the browser runs comes from a CDN. The query panel's DuckDB-wasm (about 35 MB, about 5 MB over the wire)
and Swagger UI (about 1.6 MB) at `/docs` are files of the app (`/_nuxt/` and `/_swagger-ui/`), so the Content
Security Policy allows no script or worker from any other origin, and no `'unsafe-eval'`. The app calls Iconify
(`api.iconify.design`) for its icons, and OpenStreetMap, GitHub and Cloudflare for map tiles, avatars and the map's
marker images.

The app does not forward the cookies or the `Authorization` of a client to the backend, on `/api` or on `/mcp`.
