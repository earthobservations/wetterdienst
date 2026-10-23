# REST API

Wetterdienst has an integrated REST API which can be started by invoking:

```bash
wetterdienst restapi
```

There's also a hosted version at [wetterdienst.eobs.org](https://wetterdienst.eobs.org).

The REST API is the backend of the [web app](app.md) and of the [MCP server](mcp.md), and the command line renders
through the same functions, so what is said here holds for all four. [Troubleshooting](troubleshooting.md) says what
the failures mean.

## Web App

The [web app](app.md) is a client of this API, with a map-based explorer, forecasts, climate stripes, the providers
and a glossary; its page says what is in it and how to run it.

## What every endpoint shares

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

- **A name** (`name=Dresden`) is matched fuzzily, without regard to case or diacritics (`Köln`, `Koln`
  and `koeln` are the same name). `stations` lists the best five matches, to choose
  from, and `values` the one best match, as the library's `filter_by_name` does. `rank` sets another
  number of stations, for either; a station is one match however many datasets it has, and two
  stations that share a name are two. The best match comes first, equal matches in the order of their
  station ids. With a `timestamp` the name is matched among the stations that have a record in that
  window, for `values` as for `stations`, so the best match is not a station that closed before it
  while one of the same name is open; a window no station of that name covers is an empty
  result. The library's `filter_by_name` does the same with the `start` and `end` of its request.
- **A list of station ids** (`stations=01048,99999`) leaves out an id the network has no station for and
  goes on with the others. When none exists the result is empty. The ids left out are named in a
  warning of the response's `metadata`, and in the server's log. The one reference station
  of `interpolate` and `summarize` is a lookup, not a list: unknown, it is a 404.
- **An empty result** -- a window without readings, a name nothing is called -- is a 200 with an empty
  `values` or `stations`, on the command line exit 0 with the sentence on stderr. A 4xx or a non-zero
  exit means the request failed.
- **A window** (`timestamp`, a date or an interval as for `values`) also narrows `stations`: it lists
  only the stations whose record overlaps it. A station is left out when it started after the window,
  or ended before it by more than a buffer, because the end a source publishes lags a station that is
  still reporting: two days by default up to daily, 62 days for monthly and 732 for annual. The start is
  compared exactly, as an index states the first day with a reading. A station whose start or end is not
  published is kept. `station_window_end_buffer` sets the buffer in days, the same for every resolution
  (0 to 3660): `0` compares the end exactly, and left out it is the buffer by resolution, or the
  server's `WD_TS_STATION_WINDOW_END_BUFFER`. It applies to `stations` and to `values` with a `name`, as
  the library's `filter_by_name` applies the option of the same name, and `values` reports it in the
  `settings` block. With a point and `rank`, the window leaves out stations before the nearest are taken.

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
{
  "version": "0.157.0",
  "api_version": "1",
  "mcp_enabled": true,
  "mcp_path": "/mcp/v1",
  "mcp_alias_path": "/mcp",
  "limits": {"max_stations": 100, "max_rows": 500000, "max_stream_rows": 10000000, "timeout": 60.0, "max_concurrent": 32}
}
```

`limits` are those the instance holds requests to (see [Limits](#limits)), so a client can size its
requests before it is refused; 0 means the instance sets none.

`api_version` is raised with a change a client has to follow. A path under a version that does
not exist (`/api/v2/...`) is a 404. What counts as a change a client has to follow, for this API and
for the other surfaces, is on the [Compatibility](compatibility.md) page.

The MCP endpoint is versioned alike, see [MCP endpoint](#mcp-endpoint). The operation ids of the
OpenAPI document (`values_api_values_get`) and the names of the MCP tools (`values`) do not carry
the version, see [The OpenAPI document](#the-openapi-document).

### Deprecation

What is deprecated keeps working for at least two minor releases of wetterdienst before it is removed, and
a removal is announced in the changelog under `Deprecated` when it is deprecated. Meanwhile:

- the OpenAPI document marks the endpoint or the parameter `deprecated`;
- every response to a request that uses it carries a `Deprecation` header ([RFC 9745](https://www.rfc-editor.org/info/rfc9745/)),
  `@` and the unix time of the day it was deprecated, for instance `Deprecation: @1791158400`;
- where a day is set from which it may stop working, `Sunset` ([RFC 8594](https://www.rfc-editor.org/info/rfc8594/))
  says it as an HTTP date, and a `Link` with `rel="deprecation"` points to where the replacement is told;
- for a parameter, the `metadata` block of the answer has a `deprecated-parameter` warning; the old name of a
  renamed canonical parameter, which stays an alias for at least two minor releases, is marked so, without a `Sunset`.

A response that uses several deprecated things says the earliest of each date. A client that logs the
`Deprecation` header of the answers it gets is told before anything is removed.

From 1.0.0 an endpoint or a parameter of `/api/v1` is removed only with the next version of the API: `/api/v1`
is served for at least two minor releases after `/api/v2` appears, and announced by these headers, with `Sunset`
set to the day it stops. Nothing is deprecated today. The code marks one with `ui.deprecation`: `deprecated_route(Deprecation(since=...))` in the decorator of a route
for an endpoint, `mark_deprecated(...)` in the handler that reads a parameter.

## Response metadata

The JSON answer of `stations`, `values`, `interpolate`, `summarize`, `history`, `issues`, `alerts` and
the three `stripes` endpoints has a `metadata` member, and so does the GeoJSON of the first four (next to its
`data`) and of `alerts` (a foreign member of the collection, next to its `snapshot`). It is always there, and
it says where the data comes from and may be used, what was asked for as the library resolved it, and
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
      "stations": {"filter": "by_station_id", "count": 1, "ids": ["01048"]}
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
  (ECCC's licence agreement, AEMET's legal notice, IMGW's terms of data provision, IPMA's statement that the
  data may be reused with the source named). `url` is the licence, or the provider's own page that states it. The
  whole of `license` is `null` where the provider states no terms that could be read: no provider does at present,
  and it is then for the user to ask the provider. **`provider.attribution`** is the credit line to give, in the provider's own words where it
  states one (DWD's "Source: Deutscher Wetterdienst") and else its name as the rights holder; `null` where the
  provider states none or asks for none. `copyright` stays the free text it was.
- **`request`** is the request as resolved, not as typed: `daily/kl` is the list of parameters it means,
  `periods` the periods read, `start` and `end` the window applied in UTC (`null` without one), and
  `stations` how they were selected (`filter`: `all`, `by_station_id`, `by_name`, `by_rank`,
  `by_distance`, `by_bbox` or `by_sql`), `count` the stations in the answer and `ids` their `station_id`, for an
  answer of up to 100 stations; for one of more `ids` is `null`, so a listing of a whole network does not carry
  its ids a second time, and `count` is how many there are. To have the ids of a large answer, read the
  `station_id` column of its body.
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
  answer, and this counts them; without it the `raw:` token of their `quality_flags` keeps the marker) and
  `deprecated-parameter` (issued when a parameter is deprecated; none is at the moment). Codes are added as
  more are told; a client reads the ones it knows.
- **`api_version`** is the version of the API (`/api/version`), and **`schema_version`** that of this
  block, so that a stored answer can be told from one in a later shape.

Where the answer is not about stations, `request.stations` is `null` and `counts.stations` is `0` (the
warnings of `alerts`), and `counts.rows` counts what it lists: the issues, the alerts. The `metadata` of
`stripes/values` says what its values are of in a `series` member next to `metadata` (the `station`,
`resolution`, `dataset`, `parameter` and `unit` of the values), not in the block. `providers` has a
smaller block, with the `api_version`, `schema_version`, `retrieved_at`, `producer`, `warnings` and the counts of
providers, networks and the different parameters they declare: its answer is about the library, and
the terms are those of each provider it lists.

`with_metadata=true` adds two more members to the block:

- **`parameters`**: for each parameter read its `resolution`, `dataset`, canonical `name`,
  `name_original` (the source's), `description`, `quantity` and the `unit` of its values: the target of the
  quantity, which `unit_targets` sets, where `convert_units` is on, else the unit the source publishes.
- **`quality`**: what the `quality_flags` of a reading holds (its `format`), the `source_flags`, the
  quality flags the datasets read publish, whose code is the first token of `quality_flags`, and the
  `legend`: what each kind of token means for the network read, in the order of the column. An entry has
  its `kind` (`zone` for `zone:mez`; `null` for the source's own flag, which has no prefix and comes first),
  how it is `written` (`zone:<mez|woz>`, `raw:<text>`), its `meaning` and, where the source documents a closed
  set, its `codes` with their meanings (DMI's `validity:true` and `validity:false`, IMGW's `8`, `9`, `Z` and
  `11`, CHMI's quality `0` to `5`, the MADIS flags of the NWS). Where the source tells the
  codes itself (DWD's QN levels, Frost's `qualityCode`, GHCN's flags) the `meaning` names whose they are, and
  `codes` is `null`. The legend is empty for a network whose readings carry no flag (LHMT, MeteoSwiss, WSV).

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

## The OpenAPI document

`/openapi.json` (and `/docs`, the interactive reference) is the contract of the API. `tests/ui/openapi.snapshot.json`
is that document as last reviewed: a test fails when the served document is not it, and
`uv run poe openapi:snapshot` writes it anew, for the diff to be read in the pull request that changes the contract.
A second test holds the served document to `tests/ui/openapi.baseline.json`, the document of the last release: a path, a
parameter, a status, a member or an enum member that release offered must still be there, with its type, and a
request must not be asked more of (a changed default, a tighter bound, a new pattern), so a change that would break a
client written against it fails even where the snapshot was regenerated with it. The baseline is refreshed in the
release commit, with `uv run poe contracts:baseline`.

- **`info`** is the project's: the title, the MIT licence, the issue tracker as the contact, and the `version` of
  wetterdienst that serves the document, and `info.x-api-version` is the version of the API (`1`, the same as
  the `v1` of the paths, `api_version` of `GET /api/version` and of the `metadata` block, and the
  `X-Wetterdienst-API-Version` header). The `servers` are the hosted instance and the address `wetterdienst restapi` listens on.
  There are no terms of service: the data is published under the terms of each provider, which the `metadata` of an
  answer and `providers` state.
- **Tags** group the operations: `Catalogue` (`coverage`, `providers`, `glossary`, `auth`), `Stations` (`stations`,
  `issues`, `history`), `Values` (`values`, `interpolate`, `summarize`), `Climate stripes`, `Alerts` and `Server`
  (`version`, `settings`, `health`, the index and `robots.txt`).
- **`operationId`** is the name of the handler, then the path without the version, then the method, with every
  non-word character an underscore: `values_api_values_get`, `stripes_image_api_stripes_image_get`. It does not carry the version, so
  a client generated from the document keeps its method names when the version moves, and the MCP tools are found by it (`values`, `stripes_image`, see [MCP endpoint](#mcp-endpoint)). Changing one is a
  break of the API version, as a removed path or parameter is.
- **Answers** have a schema everywhere: the health check (`Health`), the version (`VersionAnswer`) and the data
  routes (the response models above), and a media type of their own for the index (`text/html`), `robots.txt`
  (`text/plain`) and the stripes image (`image/png`, `image/jpeg`, `image/svg+xml`, `application/pdf`).
- **Errors** are declared by status where the route can answer them, as references to the `responses` of
  `components`, each listing the kinds of problem that status is (see [Errors](#errors)). Every route under `/api/v1`
  can answer a 400 for a `Host` the server does not answer to, a 500, a 503 when the server is working on as many
  requests as it allows, and a 504 when the request times out; a route with a query also the 422. Beyond those: the
  routes that read from a provider (`stations`, `issues`, `history`, `values`, `interpolate`, `summarize`,
  `stripes/values`, `stripes/image`, `alerts`) the 400 of a refused request, 404, 501 and 502, and `stations`, `values`,
  `interpolate` and `summarize` the 403 of `sql` where the server does not enable it; `coverage` a 400, 404 and 501,
  `auth` a 404 and 501, `providers` a 404, `settings` a 400, and `stripes/stations` a 501 and 502. A test makes each
  of these routes fail with each exception of the table of [Errors](#errors) and holds the status it answers to
  what the document declares.

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
- **A parameter an endpoint ignores is not a parameter of it.** `stations` takes no `lead_time` and `issue`: the
  stations of a forecast network are the same for every run, which is chosen for `values`, `interpolate` and
  `summarize`. `/api/stations` answers either with a 422 like any parameter it does not know, as
  `wetterdienst stations` and the `stations` tool do.
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

### Providers

What each provider is, for a page that lists them or a client that has to credit the data: the names it goes
by (`name_short` for a chip beside a flag, `name_english`, `name_local`), its country (`country_code` is the ISO 3166-1 alpha-2 code, null for a provider of several countries), the
terms it publishes its data under (`license`, as in the `metadata` of a data answer) and the credit line
(`attribution`), and its networks with their `kind`, source `url`, whether they need credentials (`auth`) and
the resolutions and datasets they offer, with how many parameters each has. Nothing is downloaded and no
credential is read, so it answers at once: `coverage` lists the parameters of a network and `auth` checks
whether its credentials are accepted. `dwd/radar` and `dwd/alerts` are listed without resolutions.

```bash
# Every provider, sorted by name.
http localhost:7890/api/providers

# One provider.
http localhost:7890/api/providers provider==dwd
```

The command line is `wetterdienst about providers [--provider dwd]` and the MCP tool is `providers`.

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
`unit_targets` apply to all three, `station_window_end_buffer` to `values` alone, and
`min_gain_of_value_pairs` and `num_additional_stations` to `interpolate` and `summarize`. A value an endpoint refuses is refused here the same way, and an
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

### History

The changes of a station (DWD observation only, see [Station history](station_history.md)):

```bash
http localhost:7890/api/history provider==dwd network==observation parameters==daily/kl stations==1048 sections==name,geography
```

### Alerts

The weather warnings of DWD that are active now, or at a time of the last 48 hours (see
[Alerts](../data/provider/dwd/alerts/index.md)):

```bash
http localhost:7890/api/alerts granularity==district language==de format==geojson
```

### Values

`timestamp` covers everything it names: `2020-08-01` is that whole day -- all 24 readings of it for
hourly data -- `2020-08` the month and `2020` the year. An interval runs from the start of the
span its first half names to the end of the span its second, so `2020-08/2020-09` ends with
September. A date carrying a time, `2020-08-01T12`, names that one instant.

The Python API reads `start` and `end` the same way: `end="2020-08-05"` is the whole 5th, as
`timestamp==2020-08-01/2020-08-05` is, `start="2020-08"` and `end="2020-09"` are the months as
`timestamp==2020-08/2020-09` is, and the same inputs give the same window on both. The command line's
`--timestamp` and `--start` / `--end` and the `timestamp` of the MCP tools read them alike.

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

## SQL filters

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

## Image size

A chart in an image format (`png`, `jpg`, `webp`, `svg`, `pdf`) is refused with a 400 when a side of
the image is longer than 8192 px, `scale` applied; for `/api/stripes/image` the size is 700 x 500 px
times `dpi / 100`. A chart of several parameters is 300 px tall for each, and is measured as drawn.
The limit holds for the REST API and the MCP tools; the library and the CLI have none.

## Limits

A request that would return more than the server allows is refused with a 400 before anything is
downloaded, as a problem of the kind `limit-exceeded`. It names the limit, its value and what the request comes
to (`limit`, `maximum`, `requested`), and `detail` says how to narrow it:

```json
{
  "type": "urn:wetterdienst:problem:limit-exceeded",
  "title": "Bad Request",
  "status": 400,
  "detail": "This request reads 1284 stations, more than the 100 this server allows for one request. Name fewer stations, or narrow the selection: a smaller `rank`, a smaller `distance` or bounding box. Request the rest in further calls.",
  "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "limit": "stations",
  "maximum": 100,
  "requested": 1284
}
```

| `limit` | Setting | Default | What it bounds |
| --- | --- | --- | --- |
| `stations` | `WD_RESTAPI_MAX_STATIONS` | 100 | the stations one `values` or `history` request reads; a `rank` counts as that many |
| `rows` | `WD_RESTAPI_MAX_ROWS` | 500,000 | the rows of an answer sent as one body: `json`, `geojson`, a chart, and the answer of `interpolate`, `summarize` and the listing of `stations` |
| `stream_rows` | `WD_RESTAPI_MAX_STREAM_ROWS` | 10,000,000 | the rows of a streamed answer, `format=ndjson` and `format=csv` of `stations` and `values` |

The host sets them with the settings of the same names (`restapi_max_stations`, ...; see [Settings](settings.md)),
and `0` switches a limit off. They hold for the REST API and the MCP tools; the library and the command line have
none. The default of 100 stations is the number `request.stations.ids` of the `metadata` block lists.
`GET /api/version` reports the values of the instance as `limits` (`max_stations`, `max_rows`, `max_stream_rows`,
the `timeout` in seconds and `max_concurrent`), so a client can size its requests before one is refused.

The stations are counted from the selection, which the server holds already. The rows of `values` are an
estimate, and an upper bound: for each station the readings its resolution can hold between the start and the end
of its record, within the `timestamp` of the request, times the parameters asked for (once for each timestamp in the
wide `shape`). Where the provider reads per period (DWD does), `periods=recent` narrows it to what that release
holds, counted as the last two years, rather than the whole record of the station; a dataset whose recent release
reaches back further (the 1 and 5 minute data, the annual data) is counted from further back, and one with no
release of its own (the hourly and daily solar data, the hourly urban data) or one that holds years (the monthly
derived data, the phenology) is counted from its record. A request for `now` alone is counted as the last four days
(10 minute data) or five days (1 and 5 minute data), over the day or two that DWD's `now` files hold.
A station whose record is not published is counted from an assumed start, so that a request without a
`timestamp` is held to the limit as well. That concerns the datasets that need no date and whose station list publishes
no record (the phenology of DWD is one; a network that requires a date has the window of the request). The start is
assumed from the periods of the dataset: 1 January 1950 for one with historical data (or one whose recent data
reaches back years, as the phenology's does), which is before the oldest archive of this kind that the library reads
(IMGW's begins in 1951), two years before the end for recent data and two days for current data. A forecast has no
record to assume and is not counted: its answer is bounded by the horizon of the model. `drop_nulls` or a station
with less data than its record makes the answer smaller. For `interpolate` and
`summarize` it is the readings of the window for each parameter. So the time span of a request is bounded through
the rows: a year of 1-minute readings of one parameter is 525,600 of them, a century of daily ones 36,500.

An answer over `rows` that fits `stream_rows` is told to use `format=ndjson` or `format=csv`.

## Streaming

`stations` and `values` answer `format=ndjson` and `format=csv` as the answer is built, station by station,
instead of holding it: the memory of the server does not grow with the answer, and the client reads the first
rows while the later stations are still downloaded. `json` and `geojson` are one body, as before.

```bash
http --stream localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020 format==ndjson
```

**NDJSON** (`application/x-ndjson`) is one JSON object on a line, UTF-8:

1. `{"metadata": {...}}`: the `metadata` block (with `with_metadata`, the `settings` beside it in the same line).
   It is the block as known before the first reading: `counts.stations` is the stations selected (at most `rank`
   of them), `counts.rows` is 0, and `warnings` are those raised so far.
2. One line for each row: an item of the `values` (or `stations`) of the JSON answer.
3. `{"end": {"counts": {"stations": n, "rows": n}, "warnings": [...]}}`: what was sent, and every warning, those of
   the stations read after the first line too.

A stream without its `end` line was cut short. A failure after the response began cannot change its status
(the first station is read before, so a failure on it still has its own status); it is the last line instead,
`{"error": {<problem>}}`, the problem as an error would have been answered, with no `end`. `metadata`, `end` and
`error` are the keys of the lines that are not rows. The command line writes the same lines
(`wetterdienst values --format=ndjson`), all at once.

**CSV** is the CSV of the answer, with the header row once, sent in chunks. A CSV has no place for the block, so
it is in the headers: `X-Wetterdienst-API-Version`, `-Schema-Version`, `-Retrieved-At`, `-Provider`, `-License`,
`-Attribution`, `-Stations` (the stations selected), and `Link: <licence>; rel="license"`. They go out before the
first row, so `X-Wetterdienst-Rows` is left out, and `X-Wetterdienst-Warnings` has only what was raised by then. A
failure after the response began cuts the connection, as CSV cannot say it; the server logs it.

`ndjson` refuses `sql_values` and `with_stations` (a 400): the first filters the answer as a whole frame and the
second lists the stations of the whole answer, which a stream never holds. `format=csv` with `sql_values` is
sent as one body, as it was, and is held to `rows`.

## Timeout

A request has to be answered within a timeout, `WD_RESTAPI_TIMEOUT` (`restapi_timeout`, in seconds), 60 by
default, `0` for none. It holds for the routes under `/api` until the response begins; one that has not by then is a
504 problem of the kind `request-timeout` with `Retry-After`. A stream may run for longer: the timeout holds
between two of its chunks, and a chunk that takes longer ends the stream with an `error` line of that kind (CSV: the
connection is cut).

The work already begun is not cancelled, so what the request had downloaded is cached, and the same request
made again after the `Retry-After` is likely to succeed. The request keeps its place in the
[limit on requests served at once](#concurrency) until that work is done. A reverse proxy in front of the server has a timeout of its
own, usually 60 seconds too; set this one below it for the answer to be this problem.

### Concurrency

A server works on a limited number of requests at once, `WD_RESTAPI_MAX_CONCURRENT` (`restapi_max_concurrent`), 32 by
default, `0` for no limit. A request under `/api` past it is not started but answered with a 503 problem of the
kind `server-busy` and `Retry-After`, and a client retries it after that time. `/health` and the index page are
not counted. A tool of the MCP endpoint makes its request to the API in process and is counted as one request there.

A request keeps its place until the work of its handler is done, not until its answer is sent: the work of a
request that timed out goes on in its thread (see [Timeout](#timeout)), so the limit bounds the threads of the
server, which the timeout alone does not. The default leaves the rest of the 40 threads of the pool to the routes
that are not counted. Set it to what the host can take, and put a rate limit in front of the server; a cap is no
protection against a client that sends requests faster than they are answered, it only keeps them from piling up.

### Allowed hosts

The REST API and the MCP endpoint answer to every `Host` by default, which is what a server behind a proxy or on a
public name wants. `WD_RESTAPI_ALLOWED_HOSTS` (`restapi_allowed_hosts`) is a comma-separated list of the names the
server answers to; a request with another `Host` is a 400 problem of the kind `host-not-allowed`, and so is a
request to the MCP endpoint (`/mcp/v1`, `/mcp`) with an `Origin` that names a host that is not listed
(`origin-not-allowed`; a request without an `Origin`, as a client of an agent makes it, is not checked).

```bash
WD_RESTAPI_ALLOWED_HOSTS=weather.example.org,*.internal.example.org wetterdienst restapi --listen 0.0.0.0:7890
```

An entry is a name without a scheme or a path, compared without regard to case: `localhost` lets `localhost:7890` and
`localhost:3000` in, `localhost:7890` only the first; an IPv6 address is written in brackets (`[::1]`);
`*.example.org` stands for every name below `example.org`, not `example.org` itself. The `Origin` is compared by its
host in the same way. The probe of `/health` is not checked.

`wetterdienst restapi` sets the list for its own process to `localhost,127.0.0.1,[::1]` (and the host it was given)
when `--listen` is a loopback address, which is the default, `127.0.0.1:7890`, and the setting is not given. A page of
another site, whose name a DNS server re-points at `127.0.0.1` (DNS rebinding), reaches a local server with its own
name in `Host`, and is refused. A local server that is reached by another name, through a tunnel, a port mapping
or a container, sets the variable to its names, or listens on `0.0.0.0` and sets it to the names it is served
under. A server started otherwise (`uvicorn wetterdienst.ui.restapi:app`) answers to every host unless the variable is
set.

## Running it for others

The REST API and the MCP endpoint have no authentication, and the server sets no CORS headers. Both are by design,
and what follows is for an instance that others can reach (the
[threat model](https://github.com/earthobservations/wetterdienst/blob/main/.github/SECURITY.md) has the rest):

- **Who may use it.** Anyone who reaches it can use the provider credentials it holds (`WD_AUTH__*`) and spend their
  quotas. `/api/auth` and `/api/coverage` say whether a key is configured, never the key. Put a gateway in front that
  authenticates, terminates TLS and limits the requests of each client: the server has a [timeout](#timeout), a
  [cap on requests served at once](#concurrency) and [limits](#limits), no limit per client.
- **CORS.** A page of another origin cannot read the answers. Serve it from the origin of the API, or let the reverse
  proxy add the headers it needs.
- **Hosts.** [Allowed hosts](#allowed-hosts) are open until you set them, in the image too.
- **Response headers.** Every answer, errors and streams included, carries `X-Content-Type-Options: nosniff`, so a
  browser takes a body for the media type it is sent as. A `Content-Security-Policy` is sent with the index page and
  the `svg` answers only, which need no script or request: not with data answers, the `html` chart (a script by
  design), `pdf`, or `/docs` and `/redoc`, which load their own from a CDN. Other headers (HSTS, a
  `Referrer-Policy`, a policy for those answers) are for the reverse proxy to add.
- **SQL.** [`sql` and `sql_values`](#sql-filters) stay off until you set `WD_RESTAPI_SQL=true`.
- **The cache directory.** `WD_CACHE_DIR` holds pickled directory listings: whoever can write there can run code as
  the server. Keep it private to the user the server runs as.

## Errors

Every error of the `/api/v1` routes and their `/api` alias is an [RFC 9457](https://www.rfc-editor.org/info/rfc9457/)
problem, served as `application/problem+json`, whatever its status: a 400, a 404, a 422, a 500 or
the 404 of a path that does not exist. The MCP endpoint (`/mcp/v1`) answers its own errors as JSON-RPC, but for the `Host` and `Origin` check, which is a problem
as well (see [Allowed hosts](#allowed-hosts)).

```json
{
  "type": "urn:wetterdienst:problem:request-refused",
  "title": "Bad Request",
  "status": 400,
  "detail": "'resolutions' and 'datasets' narrow the coverage of one provider and network, so 'provider' and 'network' must be given with them.",
  "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11"
}
```

`detail` is always text, the whole reason, with one line for each thing wrong where a request is
wrong in several. A request that fails validation (422) also carries `errors`, a list with one
entry for each invalid parameter, where `loc` names it:

```json
{
  "type": "urn:wetterdienst:problem:invalid-parameters",
  "title": "Unprocessable Content",
  "status": 422,
  "detail": "limit: Input should be greater than or equal to 1",
  "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "errors": [
    {"type": "greater_than_equal", "loc": ["query", "limit"], "msg": "Input should be greater than or equal to 1", "input": "0", "ctx": {"ge": 1}}
  ]
}
```

| Status | When |
| --- | --- |
| 400 | the request is understood and cannot be served as phrased: a window that ends before it starts, a parameter the network does not have (the whole request is refused, and `detail` names each unknown one), a point out of range, a `Host` or an MCP `Origin` the server does not answer to ([Allowed hosts](#allowed-hosts)) |
| 404 | what the request names does not exist: a provider, network, a resolution or dataset of `/api/coverage`, station, forecast run, or a path |
| 403 | the server declines it: `sql` filters it has not enabled |
| 405 | the method is not allowed for the path |
| 422 | the request is malformed: an unknown or invalid query parameter, a selection that needs exactly one of several |
| 501 | the server cannot serve it: a credential it lacks or the provider rejects, or an optional package it lacks, which the body does not name |
| 502 | the data provider failed or sent an answer the server cannot read: a download that was refused or cut short, a file in a layout it does not expect; the request was valid and can be retried |
| 503 | the server could not reach the data provider (no network connection), or it is working on as many requests as it allows ([Concurrency](#concurrency)); the request was valid and can be retried, the body says so and does not name the provider's address |
| 504 | the data provider did not answer in time; the request was valid and can be retried |
| 500 | the server's own error, a defect: the body names the exception's type and nothing else, the cause is in the server log |

Read `type` for what kind of error it is, `status` for what happened and `detail` for a sentence to show; the
wording of `detail` is not part of the contract, the `type` is. A client that read `detail` as the list of a 422
reads `errors` now.

`type` is `urn:wetterdienst:problem:<kind>`: a name for the kind of error, not an address to fetch. The kinds
are these, and a kind keeps its status:

| Type | Status | When |
| --- | --- | --- |
| `urn:wetterdienst:problem:invalid-parameters` | 422 | A query parameter is unknown, malformed or invalid, or a selection that needs exactly one of several does not. `errors` has an entry for each invalid parameter. |
| `urn:wetterdienst:problem:request-refused` | 400 | The request is understood and cannot be served as phrased: a window that ends before it starts, a parameter the network does not have, a point out of range. |
| `urn:wetterdienst:problem:limit-exceeded` | 400 | The request would return more than the server allows. `limit` names the limit (`stations`, `rows` or `stream_rows`), `maximum` its value and `requested` what the request comes to; `detail` says how to narrow it. |
| `urn:wetterdienst:problem:image-too-large` | 400 | A chart would be longer than 8192 px on a side. |
| `urn:wetterdienst:problem:host-not-allowed` | 400 | The `Host` of the request is not one the server answers to (`WD_RESTAPI_ALLOWED_HOSTS`). Reach the server by a name it lists. |
| `urn:wetterdienst:problem:origin-not-allowed` | 400 | The `Origin` of a request to the MCP endpoint is not a host the server answers to (`WD_RESTAPI_ALLOWED_HOSTS`). A page of another origin cannot use the endpoint. |
| `urn:wetterdienst:problem:sql-disabled` | 403 | The request carries a `sql` or `sql_values` filter and the server does not enable them. |
| `urn:wetterdienst:problem:not-found` | 404 | What the request names does not exist: a station, a forecast run, a resolution or dataset, or a path. |
| `urn:wetterdienst:problem:unknown-network` | 404 | The provider and network are not served, or have no stations or values to request. |
| `urn:wetterdienst:problem:method-not-allowed` | 405 | The method is not allowed for the path. |
| `urn:wetterdienst:problem:not-implemented` | 501 | The server does not implement what the request asks for, such as the station history of a network. |
| `urn:wetterdienst:problem:dependency-missing` | 501 | The server lacks an optional package the request needs. Whoever runs it has to install it. |
| `urn:wetterdienst:problem:credential-missing` | 501 | The provider needs a credential and the server has none. |
| `urn:wetterdienst:problem:credential-rejected` | 501 | The provider rejected the credential of the server. |
| `urn:wetterdienst:problem:not-configured` | 501 | The server is not configured to serve the request. |
| `urn:wetterdienst:problem:upstream-failed` | 502 | The data provider failed or sent an answer the server cannot read. The request was valid; retry it. |
| `urn:wetterdienst:problem:server-busy` | 503 | The server is working on as many requests as it allows at once (`WD_RESTAPI_MAX_CONCURRENT`). The request was not started; retry it after `Retry-After`. |
| `urn:wetterdienst:problem:upstream-unreachable` | 503 | The server could not reach the data provider (no connection). The request was valid; retry it. |
| `urn:wetterdienst:problem:upstream-timeout` | 504 | The data provider did not answer in time. The request was valid; retry it. |
| `urn:wetterdienst:problem:request-timeout` | 504 | The server did not answer within its request timeout. Narrow the request, or retry it: what the server had fetched is cached. |
| `urn:wetterdienst:problem:internal-error` | 500 | The server's own error, a defect. The cause is in the server log. |

Every problem has `instance`, `urn:wetterdienst:request:<id>`, and `request_id`, the id of the request. The id
is also the `X-Request-ID` header of every response, error or not: the client's own where it sends one (letters,
digits and `._~-`, up to 128 characters), else one the server makes. Quote it when reporting a failure; the server
logs it with a failure of its own (a 5xx).

The web app's own `/api` proxy passes the backend's answers on as they are, the problem, `X-Request-ID` and
`Retry-After` included, and sends on the `X-Request-ID` of the client. When it cannot reach the backend there is no
answer to pass on, and it answers a problem of its own, a 502 of the kind `urn:wetterdienst:problem:backend-unreachable`
with `instance`, `request_id`, `X-Request-ID` and `Retry-After` as above. The backend cannot answer that kind, so it is not
in the table.

A 502, 503 or 504 carries `Retry-After`, 30 seconds: the request was valid and the same one can succeed once the
provider is back (or, after a timeout, with what the server has cached by then). The server limits no rate, so
there is no 429; a proxy in front of it may, and the web app's own server does (a problem of the kind
`urn:wetterdienst:problem:rate-limited` with `Retry-After`, see [Web app](app.md#rate-limit)). The app's problems are
not in the table.

The library's exceptions are answered by their class in the hierarchy of
`wetterdienst.exceptions` (a `RequestError` is a 400, a `NotFoundError` a 404, a
`ConfigurationError` a 501, an `UpstreamError` a 502, 503 or 504), and the command line and the MCP
tools ask the same table. A client may retry a 502, 503 or 504; a 4xx it has to change the request
for, a 501 whoever runs the server has to act on, and a 500 is a defect.

The MCP tools put the same text into the tool error of an error the API answers, as `HTTP error
422: Unprocessable Content - limit: Input should be greater than or equal to 1`, and an exception
that no endpoint handled is the 500 sentence there too, not its own message.

## MCP endpoint

The REST API can serve a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) endpoint at `/mcp/v1`
(`/mcp` is an alias of the current version), so that LLM agents can call the data endpoints as tools. It needs the
`[mcp]` extra; without it the MCP paths are absent and `GET /api/version` says so (`mcp_enabled`). How to use the
hosted endpoint, how to run your own, the tools and the versioning are on the [MCP server](mcp.md) page.
