# MCP server

The [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) lets an assistant call wetterdienst as tools:
it finds a station, then reads its measurements, and answers from them instead of from memory. The endpoint is
part of the [REST API](restapi.md): the tools are generated from its routes and run in the same process, so what
the REST API answers (the [`metadata` block](restapi.md#response-metadata) with the licence and the credit line,
the [limits](restapi.md#limits), the [problems](restapi.md#errors)) is what a tool answers.

## Use the hosted endpoint

The hosted instance serves it on its own origin, with no account and no API key:

```text
https://wetterdienst.eobs.org/mcp/v1
```

Any client of the streamable-HTTP transport takes that URL. For an assistant that is configured with a JSON file:

```json
{
  "mcpServers": {
    "wetterdienst": {
      "url": "https://wetterdienst.eobs.org/mcp/v1"
    }
  }
}
```

For Claude Code, one command adds it:

```bash
claude mcp add --transport http wetterdienst https://wetterdienst.eobs.org/mcp/v1
```

Then ask in words: "How warm was it in Kiel on 26 December 2025?" The assistant calls `stations` with the name and
`values` with the station it got.

## Run your own

Install the extra and start the REST API; the endpoint is served next to it:

```bash
pip install "wetterdienst[mcp]"
wetterdienst restapi
```

```text
http://localhost:7890/mcp/v1
```

`GET /api/version` says whether an instance serves it (`mcp_enabled`) and where (`mcp_path`, `mcp_alias_path`; both
`null` without the extra). The [Docker image](docker.md) and the [app](app.md)'s `/mcp/v1` have it.

The server holds the provider credentials (`WD_AUTH__AEMET`, `WD_AUTH__KNMI_EDR`, `WD_AUTH__METNO_FROST`,
`WD_AUTH__CEDA`, see [Settings](settings.md)), not the client: a tool for a network that needs one answers a
[problem](troubleshooting.md#credentials) when the server has none, and the tool `auth` says whether the provider
accepts them. The `sql` and `sql_values` arguments are refused unless the server runs with `WD_RESTAPI_SQL=true`.

## The tools

A tool is a route of the REST API, with the same name for each argument (written with underscores, as the query
parameters are, see [one vocabulary](restapi.md#one-vocabulary)) and the same answer.

| Tool | REST route | What it is for |
| --- | --- | --- |
| `stations` | `/api/v1/stations` | find a station by name, id, point, bounding box or rank |
| `values` | `/api/v1/values` | the measurements or forecast of stations; the tool for "what was the weather" |
| `interpolate` | `/api/v1/interpolate` | an estimate for a point between stations; only when asked for |
| `summarize` | `/api/v1/summarize` | the nearest station with data at each timestamp, for a point; only when asked for |
| `history` | `/api/v1/history` | the changes of a station (name, position, instruments), not weather |
| `issues` | `/api/v1/issues` | the model runs of a forecast network |
| `providers` | `/api/v1/providers` | which provider has which network, and what a provider is: country, licence, credit line to cite, the networks with their `kind`, `extent` and whether they are `configured` |
| `coverage` | `/api/v1/coverage` | the resolutions, datasets and parameters of one network (`provider` and `network` are required) |
| `glossary` | `/api/v1/glossary` | what a parameter means and the unit it comes back in |
| `auth` | `/api/v1/auth` | whether the credentials the server holds are accepted by one provider |
| `alerts` | `/api/v1/alerts` | the weather warnings of DWD: all of Germany unless given a place (`latitude` and `longitude`, or `name`), so pass it |
| `stripes_stations`, `stripes_values`, `stripes_image` | `/api/v1/stripes/...` | climate stripes, see [Climate Stripes](stripes.md) |

An argument that is a mapping (`unit_targets`, `limits`, `interpolation_station_distance`,
`summary_station_distance`) is advertised as an object, and an assistant gives it as one:
`unit_targets={"temperature": "degree_fahrenheit"}`. The server sends the REST API its JSON text, which is what the
query parameter takes (`?unit_targets={"temperature": "degree_fahrenheit"}`), so the object and the JSON text of it
are the same argument.

Every tool has a `title` ("Find stations" for `stations`) and says in its annotations that it only reads:
`readOnlyHint` true, `destructiveHint` false and `idempotentHint` true, so a client may run it without asking
first. `openWorldHint` is false for `coverage`, `glossary` and `providers`, which answer from wetterdienst's own
metadata, and true for the others, which fetch from a provider's service (`auth` probes it).

The endpoints of the server itself (`/api/version`, `/api/settings`, the index and the health check) are not tools.
The server gives the assistant a block of `instructions`: the workflow (find the station, then read its values),
which tool not to reach for first (`interpolate` and `summarize` introduce an error and are for an explicit
request), how a parameter is written (`daily/climate_summary/temperature_air_mean_2m`) and how to read a result.
The instructions and the descriptions of the tools are written for agents and are improved without a new version.

The same two steps serve a network of any `kind` (`observation`, `forecast`, ...), for a place given by coordinates as
well as by name. The `country` of a provider is the country of the agency that runs it, not the extent of its data, and
the instructions tell the assistant not to conclude from it that a network cannot serve a place: it looks at the
network's `kind`, its [`extent`](restapi.md#extent) (where its stations are, in `providers`; `coverage` has the extent of each
dataset of one network) and at
what `stations` returns near the place. `providers` is the tool for which networks reach a place, as well as for the
country, licence and credit line of a provider.

An error comes back as the text of the REST problem, for instance
`HTTP error 422: Unprocessable Content - limit: Input should be greater than or equal to 1`, and an argument a tool
does not take is refused with the name of the one it takes where the tool had the old name
(`station was renamed to stations`), and as an unknown argument where it never did. No tool takes
`debug`: the log level of the server is its operator's, and a call that gives it is refused saying so.

Every `format` a tool offers is answered, as one body held to the `rows` limit. `json` and `geojson` are the
structured content of the result. The other formats are content blocks: `csv`, `ndjson`, `html` and `svg` are text, as
the REST API sends them; `png`, `jpg` and `webp` are image content and `pdf` is an embedded resource. The structured
content that the output schema of the tool requires is then one sentence about the answer: its media type and size in
bytes, and the licence, the attribution, the note on what wetterdienst did to the
data and the warnings that the REST API sends in headers for these formats (the same
in the `_meta` of the result, under `wetterdienst`). For data (`csv` and `ndjson`) the body follows the sentence in the
structured content, since a client may hand the model that alone; a chart is not repeated. An `html` chart loads plotly.js
from the CDN, so the page is a few kilobytes (9 KB for one station) where the REST API sends it inline, about 4.8 MB,
and the page needs the network to draw. The default is `json` (`png` for `stripes_image`, which only draws), which
the assistant reads without further ado: a chart is for a client that shows it, and a long `csv` goes through the
context of the assistant.

## A forecast starts at now

A forecast is the rows of a model run, and the latest MOSMIX-L or DMO run begins hours before the request: at 14:28 UTC
its first row can be at 10:00 (MOSMIX-S and SWSMOS begin at the current or the next hour). An assistant that reads the
first rows reports an hour that has passed as the forecast. So `values` for a network whose `kind` is `forecast`
(`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`; `coverage` and `providers` give the kind) leaves out the rows stamped before
the current hour, in UTC, and the row stamped at the current hour stays. A `forecast-from-now` warning in
`metadata.warnings` says that the answer starts at now and names the `timestamp` window that asks for the earlier
hours of the run; for `csv` and `ndjson`, whose headers are in the sentence and the `_meta` of the result, it is the
`X-Wetterdienst-Forecast-From-Now` header and the sentence of the tool (an `ndjson` answer also has the block as its
first line). No row is left out, and no note is attached, where the run begins at or after the current
hour. The cut is made before the size budget below, so that the characters of the budget go to hours that are still to
come.

Which requests are cut:

- **No `timestamp`:** every row before now.
- **A `timestamp` of whole days that contains now**, as a day or a span (`2026-11-12`, `2026-11-12/2026-11-14`): the
  rows of today before the current hour, as the instructions tell an assistant to give a day. The days of the window
  before today are what the caller named, and stay. Whether a window is of whole days is read from its text: a time
  part (`2026-11-12T00:00`) on either half makes it an exact window, served as asked, as is a month or a year.
- **Left as they are:** a day window wholly in the past or in the future, a run asked for by its `issue` (an older run
  is past by nature), a network that is not a forecast, and `interpolate` and `summarize`, whose `timestamp` is
  required. To read the past hours of today, ask with a time (`2026-11-12T10:00/2026-11-12T14:00`).

The start of now follows the resolution of a row: the current hour for an hourly forecast (the only one a network has
today) and for anything finer or subdaily, the current 6-hour period of a `6_hours` forecast, the current day of a daily
one, the month of a monthly one and the year of an annual one. A frame of several resolutions gets one window for each
in the note, since the window of one can span rows of another that were kept. A run that is over, with every hour
before now, answers no row and says so. The REST API, the command line and Python answer the whole run.

## The size of an answer

An assistant reads the answer of a tool in its context, and Claude Code saves a result of more than 50,000 characters to
a file instead of handing it over (it counts characters, not tokens). So the answer of `values`, `stations`,
`interpolate`, `summarize`, `stripes_stations` and `coverage` is held to **40,000 characters** of what the client receives, in
`json`, `geojson`, `csv` and `ndjson`: for JSON the answer as the client gets it, `metadata` and `with_metadata`
included, and for `csv` and `ndjson` the structured content as JSON: the sentence of the tool, which carries the
licence and the note below, and the body, each newline and quote of it written as the escape it is there. A chart is
not counted. The budget is a constant of the server and applies to the tools alone: the REST API, the command line and Python answer everything the
[limits](restapi.md#limits) allow, so an app that lists every station of a network is unaffected.

An answer over the budget is cut, not refused, and says so:

- **`values`** keeps whole timestamps, at least one. Without a `timestamp` it keeps the end nearest to now: the start of
  a forecast (which [starts at now](#a-forecast-starts-at-now)), the latest part of a `recent` or `historical` record.
  With a `timestamp` it keeps the start of the window, so the next window continues it. Only where one timestamp alone is more than the budget are its rows cut, and no
  window can split a timestamp: ask for fewer parameters or stations.
- **`interpolate`** and **`summarize`** answer a series as `values` does and are cut the same way. Their `timestamp` is
  required, so it is always the start of the window that is kept and the next window continues it. They have no
  `shape`, so the note offers `format=csv` (about half the size of the JSON) instead of `shape=wide`.
- **`stations`** with `name` is never cut: it asks for a few stations. Otherwise (`all`, a bounding
  box, `sql`, ids) it keeps the first stations that fit, in the order of the list, and says how many match and that
  `latitude`, `longitude` with `rank` or `distance`, or `name`, narrow it. A `distance` is cut too, as a wide one lists
  hundreds of stations (983 within 500 km of Berlin): the nearest stations are kept, nearest first, and the note says
  how many lie within the distance and how far the farthest returned is, and suggests a smaller `distance`, or `rank`.
  So is a large `rank` (700 asks for as many): the nearest stations that fit are kept, nearest first, and the note says
  how many the `rank` asked for, how many are returned and how far the farthest of them is, and suggests a smaller
  `rank`. A `rank` that fits is unchanged.
- **`stripes_stations`** is cut like `stations`: the first stations of the list. It has nothing to select with, so the
  note says to give the place as `name` to `stripes_values` or `stripes_image`, which match it themselves, or to find a
  station with `stations`. The list of the temperature stripes is 144,000 characters, that of the precipitation
  stripes 640,000.
- **`coverage`** is not rows but resolutions, datasets and parameters with a description each, and noaa/ghcn (59,000
  characters), dwd/observation (89,000) and dwd/phenology (139,000) are over the budget. It is cut in steps, each only
  where the one before is still over: the answer as it is; the `description` of every parameter null (everything else
  stays); whole datasets in the order of the network, as many as fit; and, where the first dataset alone is more than
  the budget, its first parameters, the others not being available through the tool. The note names the datasets that
  were left out as `resolution/dataset` and says how to ask for one: `datasets=<name>` with `resolutions=<resolution>`
  gives its full detail. Where a dataset alone is over the budget with its descriptions (noaa/ghcn `daily/data`, 210
  parameters), no request can give them, so the note does not offer one and names `glossary` for what a parameter
  means. The answer keeps its shape. It has no `metadata` block and takes no key beside the resolutions, so the note is
  the start of the `description` of the first resolution; a JSON answer reaches a client as its body alone, so no header
  carries it. `providers` is not cut: it is 20,000 characters for all providers together.

The note (but for `coverage`, above) is a warning, `answer-truncated`, in `metadata.warnings`. A JSON answer reaches a
client as its body alone, so no header carries it (a `csv` answer has no block; for `csv` and `ndjson` the headers are in
the sentence and the `_meta` of the result, and an `ndjson` answer also has the block as its first line). It gives the
rows returned of the total, the range kept, the `timestamp` window to ask for the rest (a value the tool accepts,
ending where the caller's window did) and the ways to ask for less: a narrower `timestamp`, fewer parameters, and
`format=csv` with `shape=wide`, which is five to six times smaller than the long JSON. For `csv`, which has no block, it
is the `X-Wetterdienst-Truncated` header too and a sentence of the tool that tells it in words, never a row of the body.
`metadata.counts.rows` is the number of rows returned, not of those that were cut. The block that `with_metadata` adds
(the units, the quality legend, the settings) can be more than the budget by itself, as for a dataset with many
parameters: it is then left out, the always-present `metadata` stays, and the note says how many characters it was and
that `coverage` and `glossary` give the units. The same holds for a `rank` whose rows fit, a `name` or a single
station, whose rows are not cut: a block of 60,000 characters (noaa/ghcn with `with_metadata`) is left out of them,
and nothing else is.

The instructions and the description of `values` recommend a `timestamp` window, so an assistant that follows them
asks for a day or a week and is not cut. A forecast of ten days of three parameters in the long JSON is about 100,000
characters, a window of 48 hours about 20,000. An assistant that needs more than a tool gives uses the REST API or the
[library](large-requests.md#from-an-assistant).

## Text from the providers

A tool answers what the REST route answers, and some of that is text written by the provider: station names, the free
text of DWD warnings (`headline`, `description`, `instruction`), the remarks and instruments of a station's history. The
server does not filter or mark it. To the assistant that reads it, it is untrusted input, as a web page would be: an
assistant that is connected to this endpoint together with tools that act (send, write, run, fetch) should not follow an
instruction that such a field contains. The
[threat model](https://github.com/earthobservations/wetterdienst/blob/main/.github/SECURITY.md)
has the rest.

## Stateless

The endpoint keeps no session. The tools hold no state: each is a request to the REST API, so the server does not
create a session at `initialize`, sends no `mcp-session-id` header and has nothing to expire, and a request needs no
earlier one: `tools/list` and `tools/call` work without an `initialize`. A request that carries an `mcp-session-id`
is served as one without. The two requests that belong to a session are answered with a 405, as the specification
lets a server do: `DELETE` (ending a session; clients that send it on closing carry on) and `GET` (opening a stream
of messages from the server, of which a server of tools has none). A tool's answer is one body and is not streamed
(`format=ndjson` and `csv` are text content of the result, held to the same `rows` limit as every other format of
a tool, not the higher `stream_rows` of the REST API). A tool makes its request to the
API in process, so it is held to the [limits](restapi.md#limits), the [timeout](restapi.md#timeout) and the
[concurrency](restapi.md#concurrency) of the server like any request. A request that a tool is refused for its size is
asked again for a window or fewer stations (for `interpolate` and `summarize`, which name no stations: a shorter
window or fewer parameters, or a smaller radius when it reaches too many stations), or made from the library: see
[Getting more than the limit](large-requests.md#from-an-assistant).

## Versioning

`/mcp/v1` is the endpoint to configure, and it stays what it is: a breaking change of a tool (its name, an
argument, the answer) comes with `/mcp/v2`, and `/mcp/v1` keeps serving the tools as they were for at least two
minor releases, announced in the changelog. `/mcp` is an alias of the current version, the same endpoint with the
same tools, as `/api` is for `/api/v1`: it is not deprecated and it moves with the next version, so a
client that must not move with it is configured with `/mcp/v1`. Until `/mcp/v2` exists, it is a 404. A new tool, an optional argument and a new member of
an answer are not breaking and come to `/mcp/v1` as they come to the REST API. The
[Compatibility](compatibility.md) page has the rules of every surface in one place. The app reads `/api/version` before
offering an MCP client configuration, so an instance without the extra is never advertised as serving an endpoint
it does not.
