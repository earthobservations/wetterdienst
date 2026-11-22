# Web app

The web app is the way into the data for anyone who would rather click than write code: pick a station on a map,
choose what to read, look at the numbers and download them. It is a single-page app (Nuxt, Vue 3, server-side
rendering off) that calls the [REST API](restapi.md) and nothing else, so everything it shows is what the API
answers, with the same [licence and credit line](restapi.md#response-metadata) for the data. Its server serves the
pages and proxies `/api`, `/mcp`, `/docs` and `/openapi.json` to the backend, so a browser only ever calls the
origin it loaded the page from.

The hosted instance, with the app and the backend, is at [wetterdienst.eobs.org](https://wetterdienst.eobs.org).
Its pages are shown in the language of the browser or the one chosen in the settings (English, German, French,
Spanish, Italian, Polish, Dutch, Czech, Danish, Luxembourgish and Hamburgisch).

## What is in it

The six tools, Forecast, Explorer, Climate stripes, Radar, History and Map, are tabs in the header; Providers, Glossary,
Measurement, Methods and API are under **Reference**; the project's pages (about, support, the legal notices, the documentation) are in the
footer, the same on every page. On a narrow screen (below 64 rem, 1024 px at the default text size) four of the tools
are a tab bar at the foot of the screen (under the header in a window lower than 30 rem, such as a phone on its side)
and its **Menu** opens the rest: a bar holds four tools and the Menu. Until you choose, the four are Forecast,
Explorer, Climate stripes and Radar, and History and the Map are in the Menu's sheet. **Arrange tools** (a link in the Menu,
and a card of the Settings) lets you choose which four, and in which order: a list of all the tools, the four of the
bar above a line and the ones that are only in the Menu below it, with a preview of the bar that follows the list.
The Menu lists the tools in that order, the four of the bar first, each with a short line in the bar's blue, then the
ones that are only in the Menu, each with a shorter, fainter line.
Drag a tool by its handle, or press the arrow buttons on its row (they do the same, by keyboard, screen reader or
single tap, and say what moved); a tool moved into the bar pushes the one at the line out of it, so the bar always has
four. The choice stays in the browser. The header of a wide screen shows all six tools as tabs in the same order, and there the
list is one list of six, with no bar and no Menu. The
Menu's tab is marked, as the page you are on, on every page that is in its sheet and has no tab: a tool that is not in
your bar, Providers, Glossary, Measurement, Methods and API, About, Support and the Settings. The home page and the legal notices mark
nothing, and a tool that is in the bar marks its own tab. **Search** (the button in the header, or Ctrl+K
or ⌘K) goes to any page, to the forecast of a DWD station by its name or to the map opened on it, or to a provider,
and sets the theme or the language.

**Measurement** (`/measurement`, "How weather is measured") explains how a quantity is measured, how a reading becomes
a value, what the number can and cannot tell and where providers differ, one entry for each quantity with an anchor
(`/measurement#wind`) and the sources it rests on: the WMO Guide to Instruments and Methods of Observation (WMO-No. 8:
Volumes I, II and III of 2024, Volume V of 2023, the current editions) by volume and chapter, and the providers' own files. The entries so far are air and soil temperature, pressure,
humidity and dew point, wind, precipitation, radiation, sunshine duration, visibility, evaporation, soil moisture,
present weather and the state of the ground, clouds, snow, automatic weather stations, urban stations, road weather
stations, how a value is formed (means, sums, maxima and minima), climate normals, time, and observation, forecast and
derived data. The
Glossary links each parameter it can to its entry ("How is this measured?"), and the entry links back to its
parameters (`/glossary?topic=wind`). The texts are written in German and English; in another language an entry is
shown in English, with a note (in German for Low German and Luxembourgish).

**Methods** (`/methods`, "How the answers are worked out") is the reference page behind **Ask the weather**: one section
for each of its questions, with an anchor (`/methods#summer`), written from the question's own definition, so a new
question appears on it with no edit of the page. A section has the method step by step, the formula where there is one,
every period, threshold, statistic and fallback rule with the published work it comes from (the WMO Guide to Instruments
and Methods of Observation, WMO-No. 8, Volume I, 2024; the WMO Guidelines on the Calculation of Climate Normals,
WMO-No. 1203, 2017; DWD's own pages and dataset descriptions) and the place in it, the data, the terms (linked to
"How weather is measured" and the Glossary instead of being written twice) and the limits of the answer. A choice that
no published work makes is marked **wetterdienst's own choice**, with the reasoning. The page ends with the list of the
works cited, each with what it is, who issues it and what the methods take from it. Under each answer a button, **How
was this worked out?** (`aria-expanded`, a region it controls), opens the same in short for that answer: the station and
its distance, the period and how many years or days it covers, the thresholds, the provider, dataset and licence with a
link that opens the same data in the Explorer, the terms and the limits, and links to the section and the works. The
texts are written in German and English, like those of Measurement; the titles of the works stay in their own language.

| Page | What it does |
| --- | --- |
| Home | The six tools, and **Ask the weather**: four suggestions (will it rain tomorrow, was last summer hotter than usual, how windy was a day, where hourly temperatures can be downloaded) that are answered on the page from live data, with the numbers and a chart behind the verdict, a link into the tool that holds the data and, under it, how the answer was worked out and what it rests on (see Methods). The place they are about is a DWD station that can be changed. Nothing is fetched until a question is picked, apart from the look-up of a place that the link names. |
| Explorer | Pick a provider and network, a resolution, dataset and parameters, then stations on the map. Three modes: **Station** reads the measurements of the stations, **Interpolation** estimates the values of a point (see [Interpolation & Summary](interpolation.md)), **Summary** takes the nearest station with data at each timestamp. A data viewer shows the table and a chart and downloads the result as CSV, JSON or GeoJSON. |
| Forecast | The MOSMIX forecast of a DWD station as a meteogram: temperature and dew point, wind with barbs, precipitation by phase, cloud cover and pressure, with Yr's weather symbols over the hours. Each panel has a fixed height and each hour a fixed width, so on a phone the chart scrolls sideways with its axes in view; a dragged box, a pinch or the buttons zoom all panels at once, and the arrow keys step through the hours (`+`, `-` and `0` zoom and reset). `/widget?station=<id>` is the same chart without the page around it, for embedding (`&theme=dark` or `&theme=light` sets the colours). |
| Climate stripes | The warming stripes of a DWD station or of a station of NOAA's GHCN daily, for temperature or precipitation, which the app makes itself of the annual values of the API (see "What the app serves itself" below). |
| Radar | DWD's precipitation radar over Germany on the map: a loop of the last two hours and DWD's forecast of the next two, with a player, the legend in mm/h and DWD's thunderstorm cells on top. |
| History | The station history of DWD observation, see [Station history](station_history.md). |
| Map | DWD's stations on a map, with a panel beside it (a sheet under it on a phone). Chips over the map choose the layer: the **forecast stations** (MOSMIX) or the **DWD measurements**, whose resolution and dataset are chosen beside the chips. Pick a station, or click any point: the panel shows the forecast of the nearest forecast station as day rows and the climate stripes of the nearest station that has them, and links to the measurements in the Explorer and to the station history, each at the nearest station of the layer's resolution and dataset, already chosen. **Which station is offered:** the nearest within 100 km of the place; one that still reports before one that has stopped, and the nearest closed one only where none that reports is within reach, with the years it measured. A station reports where the REST API's `end_timestamp` of it, the day of its last value, is within 90 days of the newest end of the list it is in (that list is the clock of its dataset: the daily climate summary is a day or two behind today, the solar radiation 38 days, the snow water equivalent 215 days, the annual datasets about 300), and the list itself is running, its newest end no more than 450 days ago (a list that ended long ago has every station closed). A station with no end has an unknown status: it is not taken for one that reports, and no "since" is told for it. The clock is one station's end: a single end far ahead of the others, but not later than today, takes the stations that are behind it out of the tolerance, which the lists do not show today. A click is on a station's dot, and is that station whatever its status, within the dot as it is drawn and 2 px more, and a click on the yellow disc of the station picked (10.5 px, and 2 px more) keeps it; a tap of a finger (a coarse pointer) reaches 12 px, and in that ring a station that reports comes before the nearest dot. Closed stations stay on the map. Where no station is within 100 km, the panel says so. Changing the layer or the dataset keeps the place, not the number of the station (a forecast point and a measuring station can share a number): the station for the place is picked again in the new list. The panel finds a station by name or number and lists the ones near the centre of the map; by keyboard the arrow keys move the map and **Pick the centre of the map** picks the station within half a kilometre of the centre, else the station for the place at it (the same as a click of a mouse that is not on a dot). The address holds what is shown (`?layer=`, `resolution`, `dataset`, `station`, `lat`, `lon`), so a link opens the same map. Search finds stations, not towns. The tiles are OpenStreetMap's, as on the station pickers. |
| API | The endpoints, the formats and the [MCP](mcp.md) endpoint of the instance, with examples. |
| Providers | Who publishes the data: the country, the licence and the credit line to cite, and what the networks offer (their resolutions and datasets, shown when you ask for them), with a link into the explorer. |
| Glossary | What each parameter measures and the unit it comes back in, searchable by name and quantity. |
| Settings | Kept in the browser: the language, light or dark, which four tools are in the tab bar of a phone (see above), plain-language labels for the parameters, and whether and in which units the values are converted. Where the browser refuses its storage the settings hold for the visit and are the defaults at the next. |

The settings of a request that the explorer offers are the [options](settings.md#options) of the library
(`shape`, `skip_empty`, `drop_nulls`, the interpolation distances), under the names the REST API takes them by.
Its `humanize`, `convert_units` and `unit_targets` are the app's Settings page's (plain-language labels, whether
values are converted, and the unit of each type), which the Explorer names in one line with a link to the page;
every request names all three, so the unit of a type does not depend on the server's `WD_TS_UNIT_TARGETS`. An
Explorer link of an earlier version may carry `humanize` and `convertUnits`: where they differ from the Settings
page they apply to that view over it, and "Use my app settings" in the Explorer's Settings drops them; a link copied
now carries neither, so its recipient's settings apply. A visitor with no saved settings starts from the server's
(`GET /api/settings`: `humanize`, `convert_units`, and the `unit_targets` of the types the page lists); the page is
not held for the answer, and where it is slow or fails the defaults of the app apply. The next load tries again, field
by field and only for a setting still at the app's default, until the server has answered (its settings, or a 404);
from then on the settings are the visitor's own, whatever the server says. A link of an earlier version is compared
with the settings once the server has answered for them. **Reset** on the Settings page goes back to the server's
settings where it has answered in that load, and else to the defaults of the app, and the next load asks the server
again. The climate stripes, on their page and in the map's panel, ask for the unit the Settings page chooses for
their kind (`unit_targets` of `/api/values`, or of the app's own `/_ghcn/annual` for GHCN daily) and write the unit the answer names in the sentence, the table
and the hover texts; the colours are relative and do not change with it. The forecast, its widget, the
forecast in the map's panel, and the home page's questions ask in the units the Settings page chooses too (and for
the values as the source has them where conversion is off), and write the unit the answer reports for each
parameter (`with_metadata`) in their axes, tables and sentences. What they compare a value with (rain or snow, the
weather of a day, the wind barbs, "hotter than usual", "stormy") is judged in millimetres, degrees Celsius and metres
per second, so a verdict is the same in every unit. The widget has no unit parameter in its address: it takes the
units from the settings of the browser it runs in.

The app does not have the weather warnings of DWD (see [Alerts](../data/provider/dwd/alerts/index.md)
for them) nor the radar products.

### Large selections

The Explorer asks the REST API, so a request it makes is held to the [limits](restapi.md#limits) of the backend, and it
meets them in three ways:

- **It starts a range that fits.** A selection of stations whose whole record is more than 90 % of what the server
  sends as one answer (500,000 rows by default) starts with the newest window that fits in the date range: at most
  that 90 %, rounded down to whole days, months or years. A note under the date fields says so ("Default range: the newest data
  (8 months, about 440,000 rows) ..."). **Clear date range** empties the range and keeps it empty (`range=all` in
  the link), to ask for everything. Dates you type, apply or share in a link are never replaced, as long as the selection stays within one
  dataset (another dataset starts over). For the values of stations, a range that is required (1, 5 and 10 minute
  data) starts with the newest window of at most 100,000 values, which its form accepts, where one day of it fits
  (otherwise the whole span, which the form asks you to narrow); a range that is required has no button to clear it.
- **It shows a refusal as a state of the table.** A request the server refuses over its limit (too many rows for one
  answer, or too many stations for a series of stations) is not a red error: the table area says, in the language of
  the page, how many rows (or stations) the request comes to against the limit, and what can be narrowed (a shorter
  date range, fewer parameters, fewer stations; an interpolation or a summary names no stations). For the rows it
  offers, where one fits, **Show only the newest data (...)**, which applies the newest window that fits to the date
  range and asks again, and, for the values of stations, **Download everything as CSV**.
- **It streams a CSV.** The download is the request again as `format=csv`, which the server holds to the higher
  `stream_rows` limit (10,000,000 by default) instead of `rows`, and it is offered where the rows fit that. The browser
  saves the file as it arrives, so the app does not hold it in memory, and the app does not read it: whether a refused
  or a cut download is saved is the browser's decision (Chrome reports both as failed). An interpolation or a summary
  has no stream and no such button.

Any other answer that is not data (a provider that is down, a limit the page has no wording for) shows what the backend
answered, and the request can be made again. See [Troubleshooting](troubleshooting.md) for what the answers mean. To
get more than a limit allows, see [Getting more than the limit](large-requests.md#from-the-app).

## Embed the forecast on another site

`/widget` is the one page of the app that another site may put in a frame; every other page answers
`frame-ancestors 'self'`. It shows the MOSMIX forecast of one station and nothing else: it reads the data, and the
only things in it that can be clicked are its two links (the full forecast and the project), which open in a new tab,
and the buttons that draw the chart again or reload the frame if it could not be drawn. Pick the station on the
Forecast page: its address ends in `?station=<station-id>`. Then put this on your page, with the address of your
instance in place of the hosted one if you run your own (`/widget` is open to every site on any instance, there is no
setting for it):

```html
<iframe
  src="https://wetterdienst.eobs.org/widget?station=<station-id>&theme=light"
  title="Weather forecast"
  width="100%" height="1050"
  style="border: 0"
  loading="lazy"
  referrerpolicy="strict-origin-when-cross-origin"></iframe>
```

- The height of the frame depends on what the forecast shows. In a frame wider than 40 rem (640 px at the usual text
  size) the widget draws the chart, whose height is that of the panels it shows: 674 px for the wind, the
  precipitation, the cloud cover, the temperature and the pressure with the weather symbols above them, and 744 px
  where a thunderstorm has a probability of 10 % or more in the forecast, which adds a panel of 70 px (its plot and
  the gap above it). With the frame's header, the credits and the legend under the chart, the provider's credit line
  and the processing note under it, and the footer, the document is about 900 px high without that panel and about
  1000 px with it (measured in Chrome at 641 to 1280 px), and about 1020 px where the credit and the note wrap to
  two lines, as in German and French just above 640 px, a little more where the browser shows scroll bars or the
  legend wraps: `height="1050"` holds all of them. In a frame of 40 rem or less the widget shows the day cards (about
  350 px high), and the document is about 450 px high at 640 px and about 500 px at 320 px, where the credit takes
  more lines. The widget picks the chart or the cards once, when it loads, and keeps
  them when the frame is resized later, so a frame whose width can change (a phone turned) needs the chart's height.
  A larger text size in the visitor's browser makes the text under the chart taller.
- `theme=dark` or `theme=light` sets the colours; leave it out to follow the visitor's setting. The browser keeps the
  colours it was last given in the frame's own storage, so a visitor who has seen `theme=dark` keeps it until a
  `theme` says otherwise, even if you drop the parameter later.
- If your page has a Content Security Policy of its own, it has to allow the app's origin in `frame-src` (or
  `child-src`).
- If you add `sandbox`, give it `allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox`. Without
  `allow-same-origin` the frame has an opaque origin, and the widget's own scripts and stylesheet (loaded with
  `crossorigin` and an integrity hash) and its requests to `/api` are cross-origin requests, which the app does not
  answer with a CORS header (see below), so nothing is drawn; the two popup tokens let its links open.
- `/widget` is sent with `Cross-Origin-Resource-Policy: same-origin`, which a page that sets
  `Cross-Origin-Embedder-Policy: require-corp` or `credentialless` is refused the frame by. A page that sets none,
  which is most, is not affected.
- The app is served from the root of its origin: it asks for `/api/...` and its files at absolute paths, and a base
  path (`NUXT_APP_BASE_URL`, or a proxy that serves it under `/wd/`) is not supported. `/widget` is the only address
  that is open to other sites, so `/wd/widget` is not, and a frame of it stays blank.

If a reverse proxy in front of the app rewrites the path before it forwards it (decodes `%77`, collapses `//`, resolves
`..`), the app cannot see what was asked for. The widget's page therefore also refuses to draw anything outside
`/widget` while it is framed by another site (by any ancestor of another origin, not only the top window), so such an
address shows a blank frame.

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

## Search engines

The pages are drawn by script, so the server writes what a crawler or a link preview that runs none needs into the
HTML it sends: the title, the description, the canonical link and the `og:` and `twitter:` tags of the path, and a
`<noscript>` text with links to the pages, and `<html lang>`. The server writes them in the language the page will
show: it picks it as the app does at startup, the language of the `wd_lang` cookie if the visitor chose one, else
the first language of the `Accept-Language` header that the app has, else German. A request with no
`Accept-Language` at all, as a crawler sends (a browser always sends one), gets English, the language of the page a
crawler renders. One URL has one language for the HTML and for the page. `/sitemap.xml` lists
the pages worth finding (the explorer, the forecast, the climate stripes, the API, the providers, the glossary, the measurement page, the
project and legal pages, and the page of each provider) and `/robots.txt` names it. The page of a provider
(`/providers/dwd`) has its own title and description; the server reads the list of providers from the backend's
`/api/providers` and keeps it for an hour. While the backend cannot be reached it goes on with the list it read last;
only a server that has read none since it started writes the generic head and lists the fixed pages only.
`/widget` and `/settings` ask not to be indexed, and a path
that ends in `.xml` or `.txt` and is none of the app's files is a 404.

Both files, and the canonical links, use the address that `NUXT_PUBLIC_SITE_URL` gives, which is
`https://wetterdienst.eobs.org` unless you set it. Set it to the address your instance is reached at
(`https://weather.example.org`, no path) if it is open to search engines; the variable is read when the server
starts, no rebuild.

To verify the site in Google Search Console with the HTML-file method, set `NUXT_GOOGLE_SITE_VERIFICATION` to the
name Google gives for the file (`google54ae9a07758f51bd`; a trailing `.html` is accepted). The server then answers
`/google54ae9a07758f51bd.html` with the one line Google looks for, and nothing else; any other path, and every
path while the variable is empty (the default), is answered as before. A value that is not `google` and lower-case
hex is ignored, and the server logs a warning when it starts. The variable is read when the server starts, no
rebuild. It is a setting and not a file of the build so that an instance does not serve the token of another's
Google account.

## Rate limit

The server limits what costs something, per client. It counts the requests to

- `/api/values`, `/api/stations`, `/api/interpolate`, `/api/summarize` and `/api/history`,
  and any other route under `/api` that is not one of the catalogue routes below,
- `/mcp` (a session is many small calls), and
- `/_ghcn/*`, the app's own routes for NOAA's GHCN daily (the list of its stations for the map, which costs the
  backend a 44 MB answer the first time, and the climate stripes' annual values and station lists, see below),

and answers the one past the limit with `429 Too Many Requests` and a problem of the kind
`urn:wetterdienst:problem:rate-limited`, with `Retry-After` (seconds). It does not count the pages, the assets,
`/docs` and `/openapi.json`, nor the catalogue routes that every page asks for: `/api/version`, `/api/settings`,
`/api/providers`, `/api/coverage`, `/api/glossary`, `/api/auth` and `/api/health`. The routes count together, one
limit for a client. The images of the Radar tool's frames (`/api/radar/frame`) are the exception: they are counted in a bucket
of their own, in the same window, with a larger limit (`NUXT_RATE_LIMIT_FRAME_TOKENS`), since one page of the tool asks for 49 of them and
the browser keeps them for an hour; the list of the frames (`/api/radar/frames`) is counted with the others.

Every counted answer carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` (when the window
ends, in seconds since the epoch).

| Variable | Default | |
|---|---|---|
| `NUXT_RATE_LIMIT_TOKENS` | `300` | Requests per client in a window |
| `NUXT_RATE_LIMIT_WINDOW_SECONDS` | `300` | The window: 300 in 300 seconds is 60 a minute |
| `NUXT_RATE_LIMIT_FRAME_TOKENS` | `1000` | Requests per client in a window for the radar's frame images, a bucket of their own |
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
own too (`/_nuxt_icon`), and so are the map's marker images (Leaflet's own). The app calls OpenStreetMap for map tiles
and GitHub for the avatars on the About page, nothing else.

The licences of the packages the browser is served (the copyright notices their MIT, BSD, ISC and Apache terms ask to
go with the code) are one file, `/third-party-licenses.txt`, linked from the footer. The production build writes it
from the packages the bundle holds, so it is in the Docker image and in the release tarball, and the development server
answers a note in its place.

The climate stripes are made by the app, from the annual values of the generic API: the stations of
`/api/stations` and the years of `/api/values` (`dwd/observation`, `annual/climate_summary` and
`annual/precipitation_more`), with the colour scale (the mean of 1971-2000, the standard deviation of 1901-2000)
calculated in the browser. NOAA's GHCN daily has daily values only, so the app's own server builds the years from them,
by the rules of WMO-No. 1203, and lists the stations that have a record long enough:

- `GET /_ghcn/annual?kind=temperature&station=USW00094728` (`kind` is `temperature` or `precipitation`, `unit_targets`
  optional, as `/api/values` takes it) answers one row for each year, the value `null` where the year fails the rules,
  with the unit, the way the days of a temperature were calculated (`midrange` of the daily maximum and minimum, or
  `tavg`) and the provider's credit and licence. It reads the station's days from `/api/values` of the backend (up to about
  25 MB of JSON for a record of 150 years, a third less with `drop_nulls=true`, which it asks for), and answers a few kilobytes.
- `GET /_ghcn/stations?kind=temperature` answers the stations of GHCN daily that still report (their record reaches into
  this or the last year) and span ten years or more in the elements the kind is made of, which is the picker's list. It
  combines the lists `/api/stations` gives for one daily parameter each, with that element's span (backend 0.194.0): for the
  precipitation `precipitation_amount`; for the temperature `temperature_air_mean_2m` taken with the years
  `temperature_air_max_2m` and `temperature_air_min_2m` have in common, and reads them one after another (8 to 21 MB of
  JSON each).

Both are kept in the memory of the server for twelve hours, as the backend keeps the files of NOAA: a station's years
(at most 1,000 stations, the one used longest ago going first) and the list of the stations of each kind. A station asked
for by several clients at once is read once, and a failure is not kept. The two stripes routes run at most four reads of the
backend between them, side by side (a read holds up to 80 MB of memory while it is parsed); another 16 may wait for their turn, for 30 seconds at the
most, and a read beyond that is answered `503` with a `Retry-After` of 10 seconds. A read whose client has closed the
connection is given up, in the queue or under way, unless another client waits for the same station, and a read the backend
does not answer in 90 seconds is a `504`. Neither route is part of the backend's API: a deployment that serves the app serves them, one that serves the backend
alone does not.

The app does not forward the cookies or the `Authorization` of a client to the backend, on `/api` or on `/mcp`.
The `/api` and `/mcp` proxies are for their own path of the backend and nothing else: a request whose path resolves
to somewhere else (`/api/../health`, `/mcp/../health`) is a `404`, and the backend is not asked.
