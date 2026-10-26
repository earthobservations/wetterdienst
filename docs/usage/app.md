# Web app

The web app is the way into the data for anyone who would rather click than write code: pick a station on a map,
choose what to read, look at the numbers and download them. It is a single-page app (Nuxt 3, Vue 3, server-side
rendering off) that calls the [REST API](restapi.md) and nothing else, so everything it shows is what the API
answers, with the same [licence and credit line](restapi.md#response-metadata) for the data. Its server serves the
pages and proxies `/api`, `/mcp`, `/docs` and `/openapi.json` to the backend, so a browser only ever calls the
origin it loaded the page from.

The hosted instance, with the app and the backend, is at [wetterdienst.eobs.org](https://wetterdienst.eobs.org).
Its pages are shown in the language of the browser or the one chosen in the settings (English, German, French,
Spanish, Italian, Polish, Dutch, Czech, Danish, Luxembourgish and Hamburgisch).

## What is in it

| Page | What it does |
| --- | --- |
| Explorer | Pick a provider and network, a resolution, dataset and parameters, then stations on the map. Three modes: **Station** reads the measurements of the stations, **Interpolation** estimates the values of a point (see [Interpolation & Summary](interpolation.md)), **Summary** takes the nearest station with data at each timestamp. A data viewer shows the table and a chart and downloads the result as CSV, JSON or GeoJSON. |
| Forecast | The MOSMIX forecast of a DWD station as a meteogram: temperature and dew point, wind with barbs, precipitation by phase, cloud cover and pressure. `/widget?station=<id>` is the same chart without the page around it, for embedding (`&theme=dark` or `&theme=light` sets the colours). |
| Climate stripes | The warming stripes of a DWD station for temperature or precipitation, see [Climate Stripes](stripes.md). |
| History | The station history of DWD observation, see [Station history](station_history.md). |
| API | The endpoints, the formats and the [MCP](mcp.md) endpoint of the instance, with examples. |
| Providers | Who publishes the data: the country, the licence and the credit line to give, and what the networks offer, with a link into the explorer. |
| Glossary | What each parameter measures and the unit it comes back in, searchable by name and quantity. |
| Settings | Kept in the browser: the language, light or dark, plain-language labels for the parameters, and whether and in which units the values are converted. |

The settings of a request that the explorer offers are the [options](settings.md#options) of the library
(`humanize`, `convert_units`, `unit_targets`, `shape`, `skip_empty`, the interpolation distances), under the
names the REST API takes them by. The app does not have the weather warnings of DWD (see [Alerts](../data/provider/dwd/alerts/index.md)
for them) nor the radar products.

A request the backend refuses shows what the backend answered: one over a [limit](restapi.md#limits) says which
and how to narrow it, a provider that is down says so and the request can be made again. See
[Troubleshooting](troubleshooting.md) for what the answers mean.

## Run your own

The app needs a backend. The simplest is the Docker image of each, from the registry of the project, on a network
of their own so that the app can reach the backend by its name:

```bash
docker network create wetterdienst
docker run -d --network wetterdienst --name backend ghcr.io/earthobservations/wetterdienst
docker run -d --network wetterdienst --name app --publish=4000:4000 \
    --env NUXT_API_BASE=http://backend:7890/api \
    ghcr.io/earthobservations/wetterdienst-app
```

The app is then at <http://localhost:4000>. `NUXT_API_BASE` is the backend's `/api` (or `/api/v1`) URL, as the
app's server reaches it: only the server reads it (no page carries it), the browser only talks to the app, which
proxies `/api`, the interactive API reference at `/docs` and `/openapi.json`, and the [MCP endpoint](mcp.md)
`/mcp/v1` to the backend.
The image of the backend listens on port 7890, see [Docker](docker.md). Every other option below is an environment
variable too, read when the server starts: no rebuild.

```{note}
`NUXT_API_BASE` was `NUXT_PUBLIC_API_BASE` before the backend URL became private. The old name is still read when
`NUXT_API_BASE` is not set, and the server logs a warning when it starts; it will be removed in a future release.
Rename the variable in your deployment, the value stays the same.
```

From a checkout of the repository, Docker Compose builds both and reloads them when the sources change:

```bash
docker compose --profile full up       # backend on port 7890 and app on port 4000
docker compose --profile backend up    # the backend alone
docker compose --profile app up        # the app alone
```

The ports are published on `127.0.0.1`; `WETTERDIENST_BIND_HOST=0.0.0.0` in front of the command
opens them to the network, see [Docker](docker.md#docker-compose).

Without Docker, the backend is `wetterdienst restapi` (it listens on port 7890) and the app is run with Node 24 and
pnpm from the `app` directory (`pnpm install`, then `pnpm dev` for a development server or `pnpm build` and
`pnpm preview`):

```bash
cd app
pnpm install
pnpm dev    # port 4000 on localhost, looking for the backend at http://localhost:7890/api
```

The app looks for the backend at `http://localhost:7890/api` unless `NUXT_API_BASE` says otherwise.
The development server (with Nuxt DevTools) listens on `localhost`; `HOST=0.0.0.0 pnpm dev` opens it to the network.

The app is released on its own, with its own [changelog](https://github.com/earthobservations/wetterdienst/blob/main/CHANGELOG_APP.md),
as a pair with the backend: run versions of the two that were released together, as an app that is older than its
backend can fail on a request the backend has since changed.

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
Security Policy allows no script or worker from any other origin, and no `'unsafe-eval'`. The icons are the app's
own too (`/_nuxt_icon`). The app calls OpenStreetMap, GitHub and Cloudflare for map tiles, avatars and the map's
marker images.

The app does not forward the cookies or the `Authorization` of a client to the backend, on `/api` or on `/mcp`.
The `/api` and `/mcp` proxies are for their own path of the backend and nothing else: a request whose path resolves
to somewhere else (`/api/../health`, `/mcp/../health`) is a `404`, and the backend is not asked.
