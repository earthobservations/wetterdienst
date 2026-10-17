# REST API

Wetterdienst has an integrated REST API which can be started by invoking:

```bash
wetterdienst restapi
```

There's also a hosted version at [wetterdienst.eobs.org](https://wetterdienst.eobs.org).

## Web App

The REST API is complemented by a modern web app built with Nuxt.js, providing an interactive interface for exploring weather data.

### Features

- **Interactive Explorer**: Browse and query weather data with an intuitive UI
  - Map-based station selection with search and filtering
  - Parameter selection across multiple providers and networks
  - Real-time data visualization with tables and charts
  - Date range selection for historical data
- **Comprehensive Settings**: Full access to all backend API parameters
  - General: Humanize parameters, unit conversion, custom unit targets
  - Values mode: Data shape (long/wide), skip empty stations, drop nulls
  - Interpolation mode: Station distances, nearby station distance, gain thresholds
- **Climate Stripes**: Visual representation of temperature trends
- **Customization**: Primary color themes and dark mode support
- **Export**: Download data in CSV, JSON, or GeoJSON formats

### Access

Visit [wetterdienst.eobs.org](https://wetterdienst.eobs.org) to use the web interface.

The JSON and GeoJSON of the `stations`, `values`, `interpolate`, `summarize` and `history` endpoints
carry a `metadata` block next to the data, always: see [Response metadata](#response-metadata). Add
`with_metadata=true` for its heavier parts, and (for the endpoints of values and `history`)
`with_stations=true` to include the queried stations' metadata; a listing of `stations` is the
stations, and takes no `with_stations`. With `with_metadata=true`, the JSON and GeoJSON of `values`,
`interpolate` and `summarize` also carry a `settings` block next to `metadata`: the settings the result
was got with, named as the endpoint's query parameters are. `interpolate` and `summarize` also report the settings the server sets alone
for them, which no query parameter of theirs changes: `skip_empty`, `skip_threshold`,
`skip_criteria`, `drop_nulls` and `station_distance_resolution_factors`.

The command line renders through the same function, so the same request gives the same body there:
`wetterdienst values ... --with-metadata=true` writes the `settings` block too, `--pretty` the
indentation `pretty=true` does, and every command that prints JSON prints the `metadata` block.

What the endpoints share about which stations a request names:

- **A name** (`name=Dresden`) is matched fuzzily. `stations` lists the best five matches, to choose
  from, and `values` the one best match, as the library's `filter_by_name` does. `rank` sets another
  number, for either.
- **A list of station ids** (`stations=01048,99999`) leaves out an id the network has no station for and
  goes on with the others. When none exists the result is empty. The ids left out are named in a
  warning of the response's `metadata`, and in the server's log. The one reference station
  of `interpolate` and `summarize` is a lookup, not a list: unknown, it is a 404.
- **An empty result** -- a window without readings, a name nothing is called -- is a 200 with an empty
  `values` or `stations`, on the command line exit 0 with the sentence on stderr. A 4xx or a non-zero
  exit means the request failed.
- **A window** (`timestamp`, a date or an interval as for `values`) also narrows `stations`: it lists
  only the stations whose record overlaps it. A station is left out when it started after the window,
  or ended before it by more than two readings of its resolution (two days up to daily, 62 days for
  monthly and 732 for annual), because the end a source publishes lags a station that is still
  reporting. A station whose start or end is not published is kept. With a point and `rank`, the
  window leaves out stations before the nearest are taken.

Every timestamp in a JSON or GeoJSON body, of values, stations, history, alerts and stripes alike,
and the same on the command line and in the MCP tools, is written the one way: ISO 8601 in UTC, to
the microsecond, with its offset, for instance `2026-09-01T00:00:00.000000+00:00`.

## Versioning

The routes are served under `/api/v1/...`, and OpenAPI (`/openapi.json`, `/docs`) documents that
prefix. `/api/...` is an alias of the current version: the same routes with the same handlers, so
`/api/values` and `/api/v1/values` answer alike. The alias is not deprecated, and it follows the
current version, so a client that must not move with the next one asks for `/api/v1`. The
examples on this page and the web app use the alias.

`GET /api/version` reports the version of the contract next to that of the package:

```json
{"version": "0.155.0", "api_version": "1", "mcp_enabled": true}
```

`api_version` is raised with a change a client has to follow. A path under a version that does
not exist (`/api/v2/...`) is a 404.

The operation ids of the OpenAPI document (`values_api_values_get`) and the names of the MCP tools
(`values`) do not carry the version.

## Response metadata

The JSON answer of `stations`, `values`, `interpolate`, `summarize` and `history` has a `metadata`
member, and so does the GeoJSON of the first four (next to its `data`). It is always there, and it
says where the data comes from and may be used, what was asked for as the library resolved it, and
what the answer is missing:

```json
{
  "metadata": {
    "api_version": "1",
    "schema_version": "1",
    "retrieved_at": "2026-10-16T21:04:37.118220+00:00",
    "provider": {
      "name_local": "Deutscher Wetterdienst",
      "name_english": "German Weather Service",
      "country": "Germany",
      "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
      "url": "https://opendata.dwd.de/climate_environment/CDC/",
      "license": {
        "spdx_id": "CC-BY-4.0",
        "name": "Creative Commons Attribution 4.0 International",
        "url": "https://creativecommons.org/licenses/by/4.0/"
      },
      "attribution": "Source: Deutscher Wetterdienst"
    },
    "producer": {
      "name": "wetterdienst",
      "version": "0.156.0",
      "repository": "https://github.com/earthobservations/wetterdienst",
      "documentation": "https://wetterdienst.readthedocs.io",
      "doi": "10.5281/zenodo.3960624"
    },
    "request": {
      "provider": "dwd",
      "network": "observation",
      "parameters": ["daily/climate_summary/temperature_air_mean_2m"],
      "periods": ["historical", "recent"],
      "start": "2026-01-01T00:00:00.000000+00:00",
      "end": "2026-01-01T23:59:59.999999+00:00",
      "stations": {"filter": "by_station_id", "ids": ["01048"]}
    },
    "counts": {"stations": 1, "rows": 1},
    "crs": {
      "code": "EPSG:4326",
      "name": "WGS 84",
      "axis_order": "longitude, latitude",
      "elevation": "metres above mean sea level"
    },
    "warnings": [
      {
        "code": "unknown-station",
        "message": "No station with station_id 99999 for the requested parameters and periods of DwdObservationRequest."
      }
    ]
  },
  "values": [
    {"station_id": "01048", "resolution": "daily", "dataset": "climate_summary", "parameter": "temperature_air_mean_2m", "timestamp": "2026-01-01T00:00:00.000000+00:00", "value": 1.6, "quality_flags": "10"}
  ]
}
```

- **`provider.license`** is the terms the provider publishes its data under: `spdx_id`, the identifier of
  the licence in the [SPDX list](https://spdx.org/licenses/) (or an expression, `CC-BY-4.0 OR NLOD-2.0`,
  where the provider offers two), `name` and `url`. `spdx_id` is `null` where the terms have none
  (ECCC's licence agreement, AEMET's legal notice). The whole of `license` is `null` where the provider
  states no terms that could be read, as for CHMI, IMGW, IPMA and NOAA GHCN: it is then for the user to ask
  the provider. **`provider.attribution`** is the credit line to give, in the provider's own words where it
  states one (DWD's "Source: Deutscher Wetterdienst") and else its name as the rights holder; `null` where the
  provider states none or asks for none. `copyright` stays the free text it was.
- **`request`** is the request as resolved, not as typed: `daily/kl` is the list of parameters it means,
  `periods` the periods read, `start` and `end` the window applied in UTC (`null` without one), and
  `stations` how they were selected (`filter`: `all`, `by_station_id`, `by_name`, `by_rank`,
  `by_distance`, `by_bbox` or `by_sql`) and the `station_id` of each station in the answer.
- **`retrieved_at`** is when the answer was made, in UTC. Whether the data came from the server's cache,
  and when the provider published it, are not told yet.
- **`counts`** is the stations in the answer and its rows: the items of `values` (one per timestamp in
  the wide shape), the stations listed, or the histories.
- **`crs`** is the reference system of every position in the answer: WGS 84, longitude before latitude in
  a GeoJSON position, the elevation in metres above mean sea level.
- **`warnings`** is what the answer is missing but did not fail on, so that a partial answer can be told
  from a whole one. Each has a `code` that stays and a `message` that may be improved. The codes are
  `unknown-station` (an id of `stations` the network has no station for), `station-skipped` (a station with too
  few readings, by `skip_empty` and `skip_threshold`), `period-not-published` and `period-not-narrowing`
  (a period that was asked for and does not apply), `elevation-unknown` (the stations of unknown
  elevation that an estimate at an elevation had to leave out), `missing-value-marker` (readings that are
  `null` because the source wrote a marker for a missing value: with `drop_nulls` they are not in the
  answer, and this counts them; without it the `raw:` token of their `quality_flags` keeps the marker) and `deprecated-parameter`. Codes are added as more are told; a client reads the
  ones it knows.
- **`api_version`** is the version of the API (`/api/version`), and **`schema_version`** that of this
  block, so that a stored answer can be told from one in a later shape.

`with_metadata=true` adds two more members to the block:

- **`parameters`**: for each parameter read its `resolution`, `dataset`, canonical `name`,
  `name_original` (the source's), `description`, `quantity` and the `unit` of its values: the target of the
  quantity, which `unit_targets` sets, where `convert_units` is on, else the unit the source publishes.
- **`quality`**: what the `quality_flags` of a reading holds (its `format`), and the `source_flags`, the
  quality flags the datasets read publish, whose code is the first token of `quality_flags`. The meaning of
  each code is the provider's and is not listed here yet.

A format with no body to put the block in carries the same in headers, and so does every JSON answer:

| Header | Value |
| --- | --- |
| `X-Wetterdienst-API-Version`, `X-Wetterdienst-Schema-Version` | `api_version` and `schema_version` |
| `X-Wetterdienst-Retrieved-At` | `retrieved_at` |
| `X-Wetterdienst-Provider` | the provider's English name |
| `X-Wetterdienst-License` | the SPDX identifier of the licence, else its name; left out without a licence |
| `Link` | `<licence url>; rel="license"`, left out without a licence |
| `X-Wetterdienst-Attribution` | the credit line; left out without one |
| `X-Wetterdienst-Stations`, `X-Wetterdienst-Rows` | the `counts` |
| `X-Wetterdienst-Warnings` | the `code` of each warning, comma-separated; left out without warnings |

A text with more than ASCII in it (a credit line such as "© Météo-France"), or a character a header cannot
carry, is percent-encoded UTF-8;
`urllib.parse.unquote` reads it back. The CSV and image formats are otherwise the data alone, as they were.
The command line prints the block in its JSON and GeoJSON, as REST does, and nothing of it in CSV; the MCP
tools return the REST answer, and so the block.

The OpenAPI document is the contract of the API, and `tests/ui/openapi.snapshot.json` is that document as
last reviewed: a test fails when the served document is not it, and `uv run poe openapi:snapshot` writes it
anew, for the diff to be read in the pull request that changes the contract.

## One vocabulary

A request is spelled the same on the REST API, the command line and the MCP tools, so that what is
learnt on one holds on the others:

- **The same name, with a hyphen on the command line.** The query parameters of an endpoint and the
  arguments of its MCP tool are written with underscores, `name_threshold`, and the options of the
  command with hyphens, `--name-threshold`. The mapping is that and nothing else, and a test holds
  every parameter of every request to it: a parameter has an option and an argument of its name and
  type, or is written down with the reason it has none (`--target` writes to a file, which REST does
  not). The underscored spellings of the command line,
  `--convert_units` and the like, are refused with an error naming the hyphenated one.
- **A parameter that takes a list is plural.** `parameters`, `periods`, `stations` and `sections`,
  and `resolutions` and `datasets` of `coverage`, take a list; `station`, `parameter`, `period`,
  `resolution` and `dataset` for them are refused with an error naming the plural
  (`station was renamed to stations`). A parameter of one value is singular: the one reference
  `station` of `interpolate` and `summarize`, the `station` of `issues` and `stripes`, the
  `parameter` text `glossary` looks for.
- **A list is comma-separated**, `stations=01048,04411` and `--stations=01048,04411`, which is how
  the OpenAPI document describes it (`explode: false`). The key given more than once,
  `stations=01048&stations=04411`, is read as the same list, and is not documented. The command line
  takes the last of an option given twice.
- **A boolean is `true`, `1`, `yes`, `on`, `t` or `y`, or one of their opposites**, in any case, on
  every surface; nothing else is one. On the command line a boolean option given without a value is
  on (`--pretty`, `--all`), and `--pretty=false` says it outright.
- **A parameter an endpoint ignores is not an option of the command or an argument of the tool.**
  `stations` takes `lead_time` and `issue` and ignores them: the stations of a forecast network are
  the same for every run, which is chosen for `values`. A value that does not parse is still
  refused. REST keeps accepting them, as it always has, so that no caller gets a 422, and the
  OpenAPI document says in their descriptions that they are ignored; `wetterdienst stations` and the `stations` tool
  do not take them, and `--lead-time` and `--issue` are options of `values`, `interpolate` and
  `summarize`.
- **The stations are named by exactly one of** `all`, `stations`, `name`, a point (`latitude` and
  `longitude`, with `rank` or `distance`), a bounding box (`left`, `bottom`, `right` and `top`) or
  `sql`. None, or two, is refused the same way everywhere, a `missing_one_of` or a `mutually_exclusive`
  error that names the alternatives: `Cannot be combined with name, give exactly one of all,
  stations, name, (latitude and longitude), (left, bottom, right and top) or sql` as the answer of a
  422, as the message of a tool error and, in the options' names, as the usage error of the
  command.

The following examples use [httpie](https://github.com/httpie/cli) to demonstrate the usage of the REST API.

## Examples

### Coverage

```bash
http localhost:7890/api/coverage
```

The list downloads nothing, so it answers at once. Each network of each provider has

| Field | |
| --- | --- |
| `name_short` | the provider's short name, `DWD` |
| `country` | the country of the provider, `Germany` |
| `url` | where the provider publishes the data |
| `kind` | what the network is, see below |
| `auth` | whether the network needs credentials |
| `configured` | whether the server has them |
| `date_required` | whether a dataset of the network needs the request to name `start` and `end` |

`kind` says which endpoints take the network. A **timeseries network** has stations and values, is
`observation`, `forecast` or `derived`, and is what `stations`, `values`, `history`, `interpolate`,
and `summarize` take, and what `coverage` with a provider and network lists the resolutions,
datasets and parameters of. Every network is one but two. The **standalone networks** are
`dwd/radar` (`radar`) and `dwd/alerts` (`alerts`): they have their own request classes and results in
Python, no stations or parameters, and every endpoint above answers a request for them with a 404. A
new standalone network gets a `kind` of its own.

A network that cannot be imported on the server, such as one whose package is broken, is not in the
list, nor is a provider none of whose networks can be; the server logs why. Asking for that network
by name, `coverage` or `auth` with its provider and network, answers a 500, or a 501 where an
optional package is missing, never a 404 as for a network that does not exist.

The list leaves out whether the provider accepts the credentials of a network that has them, because
that is a request to the provider. Ask for one network at a time, which gives up after a few seconds
and answers `valid` as `true` or `false`, or `null` when it could not tell (treat `null` as unknown,
not as rejected):

```bash
http localhost:7890/api/auth provider==aemet network==observation
```

The MCP tool `auth` and the command `wetterdienst about auth --provider=aemet --network=observation`
ask the same question and give the same answer.

### Glossary

Coverage says which parameters a provider offers; the glossary says what any of them means and
which unit it comes back in.

```bash
# Look up every canonical parameter.
http localhost:7890/api/glossary

# Match names containing some text.
http localhost:7890/api/glossary parameter==radiation

# List every parameter of one quantity.
http localhost:7890/api/glossary unit_type==temperature
```

### Settings

A setting a request to `values`, `interpolate` or `summarize` leaves out takes the server's
`WD_TS_*` variable, where it sets one, else wetterdienst's default. The settings endpoint reports
what each of them takes, keyed by endpoint, with `unit_targets` naming the unit of every quantity.

It takes the settings query parameters of the three endpoints, and answers what they resolve to
over the server's, for each endpoint that takes the parameter: `humanize`, `convert_units` and
`unit_targets` apply to all three, `min_gain_of_value_pairs` and `num_additional_stations` to
`interpolate` and `summarize`. A value an endpoint refuses is refused here the same way, and an
unknown parameter too, so a set of settings can be checked before fetching. Nothing is stored on
the server: the parameters apply to that one answer.

```bash
http localhost:7890/api/settings

# What a values request with shape=wide would get: the wide shape turns drop_nulls off.
http localhost:7890/api/settings shape==wide

# Check unit targets before fetching; an unknown unit is a 400 naming it.
http localhost:7890/api/settings unit_targets=='{"temperature": "degree_fahrenheit"}'
```

### Stations

```bash
# Acquire list of DWD OBS stations.
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent all==true

# Filter stations by name (fuzzy, case-insensitive).
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent name==Darmstadt

# Filter by name with custom threshold (0–1, default 0.8).
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent name==Darmstatt name_threshold==0.85

# Query list of stations with SQL, on a server running with WD_RESTAPI_SQL=true.
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent sql=="lower(name) LIKE lower('%dresden%');"

# Acquire list of DWD DMO stations.
http localhost:7890/api/stations provider==dwd network==dmo parameters==hourly/icon/temperature_air_2m all==true
```

### Issues (available model-run datetimes)

```bash
# List available MOSMIX-L run datetimes for a station.
http localhost:7890/api/issues provider==dwd network==mosmix station==10147

# List available DMO ICON run datetimes for a station.
http localhost:7890/api/issues provider==dwd network==dmo station==10147

# List available SWSMOS run datetimes; one run holds every road station, so any station lists them.
http localhost:7890/api/issues provider==dwd network==swsmos station==A006
```

### Values

`timestamp` covers everything it names: `2020-08-01` is that whole day -- all 24 readings of it for
hourly data -- `2020-08` the month and `2020` the year. An interval runs from the start of the
span its first half names to the end of the span its second, so `2020-08/2020-09` ends with
September. A date carrying a time, `2020-08-01T12`, names that one instant.

```bash
# Acquire observations.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent stations==1048,4411

# Observations for specific date.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020-08-01

# Observations for a whole month, since a date covers everything it names.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020-08

# Observations for date range.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020-08-01/2020-08-05

# Observations with SQL, on a server running with WD_RESTAPI_SQL=true.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent stations==1048,4411 shape=="wide" sql_values=="temperature_air_max_2m < 2.0;"

# Acquire ICON data (the latest forecast run; a past timestamp has none).
http localhost:7890/api/values provider==dwd network==dmo parameters==hourly/icon/temperature_air_2m stations==01001
```

### SQL filters

`sql` (stations and values: which stations) and `sql_values` (values, interpolate and summarize:
which rows of the result) take a SQL WHERE clause, run by DuckDB on the server. A server refuses
both with a 403 unless it runs with the setting `restapi_sql` enabled (`WD_RESTAPI_SQL=true`); the
MCP tools follow the same setting, and the library and the CLI are not gated.

The clause is a single condition on the frame, called `df`: anything after it, a second statement,
`ORDER BY` or `LIMIT`, is refused. It cannot read or list files, reach the network or load DuckDB
extensions, and runs on one thread with DuckDB's memory limit at 1 GiB plus the size of the frame.
What it can still do once enabled: read DuckDB's own settings, which name paths on the server; run
for as long as it likes on that thread; and allocate memory DuckDB's limit does not count, such as
one very long string. The limits hold per request, not for the server as a whole. Enable it only
for clients you trust with that.

### Image size

A chart in an image format (`png`, `jpg`, `webp`, `svg`, `pdf`) is refused with a 400 when a side of
the image is longer than 8192 px, `scale` applied; for `/api/stripes/image` the size is 700 x 500 px
times `dpi / 100`. A chart of several parameters is 300 px tall for each, and is measured as drawn.
The limit holds for the REST API and the MCP tools; the library and the CLI have none.

### Errors

Every error of the `/api/v1` routes and their `/api` alias is an [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
problem, served as `application/problem+json`, whatever its status: a 400, a 404, a 422, a 500 or
the 404 of a path that does not exist. The `/mcp` endpoint answers its own errors as JSON-RPC.

```json
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "'resolutions' and 'datasets' narrow the coverage of one provider and network, so 'provider' and 'network' must be given with them."
}
```

`detail` is always text, the whole reason, with one line for each thing wrong where a request is
wrong in several. A request that fails validation (422) also carries `errors`, a list with one
entry for each invalid parameter, where `loc` names it:

```json
{
  "type": "about:blank",
  "title": "Unprocessable Content",
  "status": 422,
  "detail": "limit: Input should be greater than or equal to 1",
  "errors": [
    {"type": "greater_than_equal", "loc": ["query", "limit"], "msg": "Input should be greater than or equal to 1", "input": "0", "ctx": {"ge": 1}}
  ]
}
```

| Status | When |
| --- | --- |
| 400 | the request is understood and cannot be served as phrased: a window that ends before it starts, a parameter the network does not have (the whole request is refused, and `detail` names each unknown one), a point out of range |
| 404 | what the request names does not exist: a provider, network, a resolution or dataset of `/api/coverage`, station, forecast run, or a path |
| 403 | the server declines it: `sql` filters it has not enabled |
| 405 | the method is not allowed for the path |
| 422 | the request is malformed: an unknown or invalid query parameter, a selection that needs exactly one of several |
| 501 | the server cannot serve it: a credential it lacks or the provider rejects, or an optional package it lacks, which the body does not name |
| 502 | the data provider failed or sent an answer the server cannot read: a download that was refused or cut short, a file in a layout it does not expect; the request was valid and can be retried |
| 503 | the server could not reach the data provider (no network connection); the request was valid and can be retried, the body says so and does not name the provider's address |
| 504 | the data provider did not answer in time; the request was valid and can be retried |
| 500 | the server's own error, a defect: the body names the exception's type and nothing else, the cause is in the server log |

Read `status` for what happened and `detail` for a sentence to show; the wording of `detail` is not
part of the contract, and `type` is `about:blank` until the errors have codes of their own. A client
that read `detail` as the list of a 422 reads `errors` now.

The library's exceptions are answered by their class in the hierarchy of
`wetterdienst.exceptions` (a `RequestError` is a 400, a `NotFoundError` a 404, a
`ConfigurationError` a 501, an `UpstreamError` a 502, 503 or 504), and the command line and the MCP
tools ask the same table. A client may retry a 502, 503 or 504; a 4xx it has to change the request
for, a 501 whoever runs the server has to act on, and a 500 is a defect.

The MCP tools put the same text into the tool error of an error the API answers, as `HTTP error
422: Unprocessable Content - limit: Input should be greater than or equal to 1`, and an exception
that no endpoint handled is the 500 sentence there too, not its own message.

## MCP endpoint

The REST API can optionally expose a [Model Context Protocol](https://modelcontextprotocol.io/)
(MCP) endpoint at `/mcp`, so LLM agents can call the data endpoints (coverage, auth, stations,
values, interpolate, summarize, stripes, alerts, ...) as MCP tools. It is served over the
streamable-HTTP transport by [FastMCP](https://gofastmcp.com/), generated from the REST API's own
routes and running in the same process.

The generated tools are made agent-friendly so even small models use them correctly: a workflow
`instructions` block (find a station, then query its values) is attached to the server, the tools
get clean names (`values` rather than `values_api_values_get`), and the non-data endpoints
(index, health, ...) are hidden.

Install the optional extra to enable it:

```bash
pip install wetterdienst[mcp]
wetterdienst restapi
```

The endpoint then lives next to the HTTP API, on the backend:

```
http://localhost:7890/mcp
```

Point any MCP client (streamable HTTP) at that URL — for example:

```json
{
  "mcpServers": {
    "wetterdienst": {
      "url": "http://localhost:7890/mcp"
    }
  }
}
```

Without the `[mcp]` extra installed, the REST API behaves exactly as before and the `/mcp` route is
simply absent. `GET /api/version` says which of the two an instance is:

```json
{"version": "0.155.0", "api_version": "1", "mcp_enabled": true}
```

The app reads that flag before offering an MCP client configuration, so an instance installed
without the extra is never advertised as having an endpoint it does not serve.

### Hosted instance

The `[mcp]` extra is included in the backend Docker image, and the app proxies `/mcp` through
to the backend (preserving the streamable-HTTP POST/SSE transport), so the hosted app serves the MCP
endpoint on its own origin:

```
https://wetterdienst.eobs.org/mcp
```
