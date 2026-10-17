# Web app

The web app is the way into the data for anyone who would rather click than write code: pick a station on a map,
choose what to read, look at the numbers and download them. It is a single-page app (Nuxt 3, Vue 3, server-side
rendering off) that calls the [REST API](restapi.md) and nothing else, so everything it shows is what the API
answers, with the same [licence and credit line](restapi.md#response-metadata) for the data.

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
| Providers | Who publishes the data: the country, the licence and the credit line to give, and what the networks offer, with a link into the explorer. |
| Glossary | What each parameter measures and the unit it comes back in, searchable by name and quantity. |
| API | The endpoints, the formats and the [MCP](mcp.md) endpoint of the instance, with examples. |
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
    --env NUXT_PUBLIC_API_BASE=http://backend:3000/api \
    ghcr.io/earthobservations/wetterdienst-app
```

The app is then at <http://localhost:4000>. `NUXT_PUBLIC_API_BASE` is the address of the backend's `/api`, as the
app's server reaches it (the browser only talks to the app: it proxies `/api`, the interactive API reference at
`/docs` and `/openapi.json`, and the [MCP endpoint](mcp.md) `/mcp/v1` to the backend). The image of the backend
listens on port 3000, see [Docker](docker.md).

From a checkout of the repository, Docker Compose builds both and reloads them when the sources change:

```bash
docker compose --profile full up       # backend on port 3000 and app on port 4000
docker compose --profile backend up    # the backend alone
docker compose --profile app up        # the app alone
```

Without Docker, the backend is `wetterdienst restapi` and the app is run with Node 24 and pnpm from the `app`
directory (`pnpm install`, then `pnpm dev` for a development server or `pnpm build` and `pnpm preview`):

```bash
cd app
pnpm install
NUXT_PUBLIC_API_BASE=http://localhost:7890/api pnpm dev    # port 4000
```

The app looks for the backend at `http://localhost:3000/api` unless `NUXT_PUBLIC_API_BASE` says otherwise, while
`wetterdienst restapi` listens on port 7890 unless told another with `--listen`: set the variable, or start the
backend with `wetterdienst restapi --listen 127.0.0.1:3000`.

The app is released on its own, with its own [changelog](https://github.com/earthobservations/wetterdienst/blob/main/CHANGELOG_APP.md),
as a pair with the backend: run versions of the two that were released together, as an app that is older than its
backend can fail on a request the backend has since changed.
