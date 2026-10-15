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

By default the `stations`, `values`, `interpolate`, `summarize` and `history` endpoints return only
the requested data. Add `with_metadata=true` to include the provider-metadata block, and (for the
value endpoints) `with_stations=true` to include the queried stations' metadata. With
`with_metadata=true`, the JSON and GeoJSON of `values`, `interpolate` and `summarize` also carry a
`settings` block next to `metadata`: the settings the result was got with, named as the endpoint's
query parameters are. `interpolate` and `summarize` also report the settings the server sets alone
for them, which no query parameter of theirs changes: `skip_empty`, `skip_threshold`,
`skip_criteria`, `drop_nulls` and `station_distance_resolution_factors`.

Every timestamp in a JSON or GeoJSON body, of values, stations, history, alerts and stripes alike,
and the same on the command line and in the MCP tools, is written the one way: ISO 8601 in UTC, to
the microsecond, with its offset, for instance `2026-09-01T00:00:00.000000+00:00`.

The following examples use [httpie](https://github.com/httpie/cli) to demonstrate the usage of the REST API.

## Examples

### Coverage

```bash
http localhost:7890/api/coverage
```

The list downloads nothing, so it answers at once. For a network that needs credentials it says
whether they are present (`configured`); `valid` is `false` where they are not, and `null` where
they are, because whether the provider accepts them is a request to the provider. Ask for one
network at a time, which gives up after a few seconds and answers `null` as well when it could not
tell (treat `null` as unknown, not as rejected):

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
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent station==1048,4411

# Observations for specific date.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl station==1048,4411 timestamp==2020-08-01

# Observations for a whole month, since a date covers everything it names.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl station==1048,4411 timestamp==2020-08

# Observations for date range.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl station==1048,4411 timestamp==2020-08-01/2020-08-05

# Observations with SQL, on a server running with WD_RESTAPI_SQL=true.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent station==1048,4411 shape=="wide" sql_values=="temperature_air_max_2m < 2.0;"

# Acquire ICON data (the latest forecast run; a past timestamp has none).
http localhost:7890/api/values provider==dwd network==dmo parameters==hourly/icon/temperature_air_2m station==01001
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

Every error of the `/api` routes is an [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
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
| 501 | the server cannot serve it: a credential or an optional package it lacks, which the body does not name |
| 503 | the server could not reach the data provider (no network connection); the request was valid and can be retried, the body says so and does not name the provider's address |
| 500 | the server's own error, or the provider's: the body names the exception's type and nothing else, the cause is in the server log |

Read `status` for what happened and `detail` for a sentence to show; the wording of `detail` is not
part of the contract, and `type` is `about:blank` until the errors have codes of their own. A client
that read `detail` as the list of a 422 reads `errors` now.

The MCP tools put the same text into the tool error of an error the API answers, as `HTTP error
422: Unprocessable Content - limit: Input should be greater than or equal to 1`.

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
{"version": "0.132.0", "mcp_enabled": true}
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
