# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.

## [Unreleased]

### Changed

- **Breaking**: a station history's records -- station and operator names, parameters, devices,
  geography, missing data -- give their span as `valid_from` and `valid_to`, where they gave
  `start_date` and `end_date`: in Python's `History`, `/api/history`, the MCP `history` tool and
  the CLI `history` command. Read the new names (GH-2440)
- **Breaking**: the single date or interval a request names is `timestamp`, no longer `date`:
  `/api/values`, `/api/interpolate`, `/api/summarize`, `/api/alerts` and their MCP tools,
  `--timestamp` of the CLI's `values`, `interpolate`, `summarize` and `alerts`, and
  `DwdWeatherAlertRequest(timestamp=...)` with its attribute `.timestamp`. Write
  `timestamp=2020-05-01` where you wrote `date=2020-05-01`; the old name is refused with an error
  naming the new one. The app sends `timestamp` from its next release; 0.18.1 and older send
  `date`, so upgrade the app with the backend (GH-2438)
- **Breaking**: the request window is `start` / `end`, no longer `start_date` / `end_date`: write
  `DwdObservationRequest(..., start=..., end=...)` for every provider's request and
  `DwdRadarValues`, read `.start` / `.end` off a request or a `StationsResult`, and pass
  `--start` / `--end` on the CLI. The old keywords and options fail with an error naming the new
  one; reading the old attributes, or passing them by keyword to
  `TimeseriesRequest.convert_timestamps`, is a plain Python error. Error messages that named the
  pair name `start` / `end` (GH-2437)
- **Breaking**: the span a station has records for is `start_timestamp` / `end_timestamp`, no
  longer `start_date` / `end_date`: in every provider's stations frame and its exports, and wherever
  a station is returned -- `/api/stations` and the MCP `stations` tool, the OGC feature properties,
  values with stations, interpolate, summarize, `/api/stripes/stations` and the station in the
  `/api/stripes/values` metadata. Read and filter the new names, and rename the columns of a
  database table you append stations to; a `sql` filter on a station's old name fails naming the
  new one. The app reads the new names from its next release, so upgrade the app with the backend
  (GH-2439)
- **Breaking**: `/api/auth`, `/api/coverage`, `/api/glossary`, `/api/stripes/stations` and
  `/api/alerts` refuse a query parameter they do not take with a 422, as `/api/stations` and
  `/api/values` do, and every MCP tool refuses an argument it does not take, naming the ones it
  does. Both used to answer as if it had not been given, so a misspelt `limit` returned every
  match. Drop parameters an endpoint or tool does not take, such as a cache buster (GH-2479)
- CLI: `stations` reports a request the caller can rephrase -- an unknown parameter, a bad
  bounding box, a `--sql` DuckDB refuses -- as a one-line usage error with exit code 2, where it
  printed a traceback. `history` on a network whose stations have no history, such as
  `dwd/mosmix`, and `about coverage` on a standalone network such as `dwd/radar` are usage errors
  too, where they exited 1. Scripts checking for exit 1 on these now see 2; an upstream failure
  still exits 1 with its traceback (GH-2465)
- **Breaking**: in a DWD observation station's history, the current position in `geography` has a
  null `valid_to`, where it was the time the history was read and changed on every call. A name or
  operator still in use was null already. Read a null `valid_to` as a position that still applies
  (GH-2474)
- **Breaking**: a download that failed raises `wetterdienst.exceptions.DownloadError` through
  `File.raise_if_exception`, which most providers use, where it raised the stored error itself
  (`FSTimeoutError`, `ClientResponseError`, `FileNotFoundError`, aiohttp's connection errors). Its
  message is `Failed to download <url>: <reason>` with the URL stripped of query, fragment and user
  information, so the REST API's `detail` and the CLI name the file. Catch `DownloadError` and read
  `__cause__` for the original error (GH-2460)
- **Breaking**: a station the provider gives no end has a null `end_timestamp` in the station list
  of `eaufrance/hubeau` (every station it lists) and of `dwd/observation` 1-minute precipitation
  from the historical period, where it was the time of the call or the day before. Read a null
  `end_timestamp` there as a station the provider has not closed (GH-2482)
- Values of `dwd/phenology`, `dwd/poi`, `dwd/swsmos`, `chmi`, `fmi`, `ipma`, `dmi`, `rmi`,
  `metoffice`, `lhmt`, `meteofrance/synop` and `meteofrance/observation` raise a data download that
  failed -- a timeout, a 5xx -- as `DownloadError`, where they logged it and returned no data for
  the station, or went on to the next file: the REST API answers a 500 and the CLI fails, and so
  do interpolate and summarize where a station they read fails. A 404 still gives no data at
  `dwd/poi`, `dwd/swsmos`, `chmi`, `lhmt`, `metoffice`, `meteofrance/observation` and, for the
  current year, `meteofrance/synop`, and raises at the others. `fmi` gives no data for a 400, which
  it answers for a station it does not know. A connection that cannot be made at all still gives
  no data (GH-2461)

### Fixed

- The CLI's `about coverage` refuses `--provider` without `--network`, and `--network` without
  `--provider`, with a usage error (exit 2) naming the missing option. It printed every provider
  with exit 0, as if neither had been given; with neither it still lists them (GH-2498)
- `geosphere/observation` values without dates, at 10 minutes or hourly, and long windows no
  longer fail: the API refused a slice of more than 1,000,000 data points (the 10-minute record is
  1.8 million), and answered one of more than about 6 years at 10 minutes too slowly for the read
  timeout. A window is fetched in several requests, two years each at 10 minutes and ten years
  each hourly for one parameter (GH-2466)
- `geosphere/observation` values ask the API for all the requested parameters of a dataset in one
  request, not one request per parameter. A whole dataset of a station without dates took 285 to
  414 requests at 10 minutes or hourly and stopped at the API's 240 requests an hour with an HTTP
  429; it takes about 105 (10 minutes), 62 (hourly), 4 (daily) and 1 (monthly). The windows get
  shorter with more parameters, as the API counts timestamps times parameters towards its limit of
  1,000,000 data points, and a whole daily dataset is now fetched in windows too (GH-2517)
- A `file://` target of `to_target` and of the CLI's `stations`, `values`, `interpolate`,
  `summarize`, `history` and `alerts` is read as the path the URI names: `%20` and other
  percent-encoding is decoded, and on Windows `file:///C:/data/obs.csv` is `C:/data/obs.csv`.
  Both wrote to the wrong path. A path with a literal `%20` in a `file://` target is now written
  `%2520`; a plain path is read as given (GH-2454)
- `/api/values` and the MCP `values` tool log a request they refuse with a 400 -- an unparseable
  timestamp, an unknown parameter or period -- as one info line, as `/api/interpolate` and
  `/api/summarize` do. Each was logged as an error with its traceback; the status is unchanged
  (GH-2459)
- `WD_USE_CERTIFI=true` now reaches every download of `geosphere/observation` values,
  `ea/hydrology` values, `metno/frost` stations, values and credential check, and `dwd/road`
  values. They went out with the system CA store, so where that store cannot verify the upstream
  they failed SSL verification even with the setting on (GH-2463)
- A `WD_AUTH__METNO_FROST` pair that is not valid JSON, such as `[myid, mysecret]` with its
  elements unquoted, is refused, and `check_settings()` names it. It was taken whole as the client
  id, secret included, and sent to Frost, which refused it. Quote each element:
  `["myid", "mysecret"]`. A pair given in Python as that text is read as the pair (GH-2464)
- A download through the cache (any TTL but `CacheExpiry.NO_CACHE`, cache not disabled) reports
  the failure it met, as one without the cache does: an HTTP error other than 404 comes back with
  its own status -- a 401, 403 or 429 too, which `download_file` no longer asks again -- and a
  refused connection as 503 with `NoInternetError`, where all were `File(status=404)` with
  `FileNotFoundError`, as a missing file is, and a provider that skips a missing file, such as DWD
  derived's months, skipped them too. KNMI's and AEMET's own retry of a 429 or 5xx now
  applies through the cache too. A cache miss is one GET instead of two, and a body that ends
  before its `Content-Length` is no longer read back from the cache by the retry (GH-2467)
- `filter_by_name`, `filter_by_rank` and `filter_by_bbox` build the station list once, where they
  built it twice, `filter_by_distance` once instead of four times, and `interpolate` and
  `summarize` twice instead of six times: that much less parsing, and with `WD_CACHE_DISABLE` or a
  provider that does not cache its station list, that many fewer downloads. `filter_by_distance`
  on a request with no stations finds none, where it raised "'rank' has to be at least 1."
  (GH-2475)
- A request built from a `Settings` object, as the CLI builds its requests, uses it as it is rather
  than validating it again, so the cache line and the `ts_drop_nulls` notice of a wide shape are
  logged once, when the settings are built, rather than twice. Settings given as a dict are
  validated as before (GH-2476)
- DWD road values and radar BUFR reads import `pyproj`, where it is installed, before they load
  `eccodes`. On Linux, with the `eckitlib` wheel pip installs beside `eccodes`, a process that used
  `pyproj` or wradlib after such a read aborted at exit with status 134 or 139 (ecmwf/eckit#354);
  it now exits cleanly, unless something imported `eccodes` before wetterdienst did (GH-2468)
- `/api/values`, `/api/interpolate`, `/api/summarize` and their MCP tools word a `timestamp` that
  ends before it starts, or is missing for an interpolation or a summary, in terms of `timestamp`
  ("the interval in timestamp ends before it starts"), where they named the request's `start`
  and `end`, which their callers cannot pass. Python callers keep the request's message, and
  `ReversedTimeIntervalError` and `MissingTimeIntervalError` are subclasses of the exceptions
  they raised (GH-2478)
- `wetterdienst stripes values` refuses a `--target` that is a URI (`s3://...`, `file://...`)
  before it fetches and renders, as a usage error (exit 2) naming `--target`; the write to the
  path read off the URI (`s3:/bucket/...`) failed only afterwards. A `--target` whose extension
  does not match `--format` is a usage error too, exit 2 where it was 1. Pass a local path
  (GH-2450)

## [0.141.0] - 2026-10-06

### Added

- The JSON of `/api/stripes/values` and the MCP `stripes_values` tool name the unit of their
  values in a new metadata field `unit`: `degree_fahrenheit` where the server's
  `WD_TS_UNIT_TARGETS` converts temperatures to it, the source's unit with
  `WD_TS_CONVERT_UNITS=false`, and `degree_celsius` or `millimeter` by default (GH-2372)

### Changed

- The `restapi` extra now needs `fastapi>=0.142` (was `>=0.115`), which brings `opentelemetry-api`;
  upgrade fastapi where it is pinned lower. The REST API turns off fastapi's OpenTelemetry export
  from `OTEL_*` variables: to export, set up a provider yourself, e.g. with
  `opentelemetry-instrument`. Such a provider now gets fastapi's spans, metrics and logs, or, where
  the `opentelemetry-instrumentation-fastapi` middleware runs, that instrumentation's (GH-2407)
- REST API: `/api/interpolate` and `/api/summarize`, and the MCP tools of the same names, answer
  a point there is no estimate at -- beyond the latitudes UTM covers (80°S to 84°N) on
  interpolate, or a `station` without a position -- with a 400 rather than a 404, as they answer
  an elevation no station can be placed against. The server logs it as an info line, not as an
  error with its traceback (GH-2385)
- Values of `dwd/observation`, `dwd/derived`, `imgw/hydrology` and `imgw/meteorology` raise a
  download that timed out, where they used to drop it as a missing file and return no data for
  the station: the REST API answers a 500 and the CLI fails, and so do interpolate and summarize
  where a station they read times out. A 5xx after the retries is raised the same way only with
  the cache off (`WD_CACHE_DISABLE=true`); with it on, a 5xx still reads as a missing file (GH-2430)
- CLI: `values`, `interpolate`, `summarize`, `issues`, `stripes values` and the station lookup of
  `history` report a request the caller can rephrase -- such as a parameter the network does not
  have, a network without an issue listing, or a point there is no estimate at -- as a one-line
  usage error with exit code 2, and so does every command for an unknown provider or network.
  Scripts checking for exit 1 on such a mistake now see 2; an upstream failure still exits 1 with
  its traceback (GH-2426)
- REST API: `/api/interpolate` and `/api/summarize`, and their MCP tools, answer the other
  requests they refuse as phrased -- an empty or unparseable `date` or one as late as 9999-12-31, an
  unparseable `issue` or one the source does not list, an unknown parameter or unit target, a
  `sql_values` clause DuckDB refuses -- with a 400 rather than a 404, the status `/api/values`
  gives them. An unknown `station` stays a 404. The server logs these, and a window that ends
  before it starts on any of the three, as an info line, not as an error with its traceback
  (GH-2429)

### Fixed

- MCP: an MCP tool's in-process request to the REST API gets no fastapi server span and no
  `http.server.*` metrics of its own. It started a trace of its own, cut off from the tool call's,
  and counted each tool call a second time. Over `/mcp`, fastapi's operation spans for it now sit
  beneath the tool call's span. The middleware of `opentelemetry-instrumentation-fastapi`, where it
  runs, still records the request (GH-2432)
- On Windows, DWD road values and DWD radar BUFR read with `Settings(read_bufr=True)` decode. Road
  values raised `PermissionError`, and radar logged "Unable to read BUFR file." and left
  `result.df` as `None` (GH-2446)
- `Settings` reads a `null` Frost secret in a `WD_AUTH__METNO_FROST` pair as no secret, and refuses
  any other `null`, `true`, float or object in a `WD_AUTH__METNO_FROST` / `WD_AUTH__CEDA` pair with
  a `ValidationError` naming the element (`auth.ceda.1`; `WD_AUTH__CEDA[1]` in the CLI's
  message). Such an element was taken as the text of its repr, `None` or `True` (GH-2434)
- A `ValidationError` from `Settings` or `Auth` no longer repeats the value it refuses as its
  `input_value`, which for `auth` is a credential; `errors()` still holds it (GH-2435)
- A `file://` target of `to_target`, and of `--target` on `stations`, `values`, `interpolate` and
  `summarize`, reads everything after `file://` as its path, as `alerts` and `history` do:
  `file://out/data.csv` writes `./out/data.csv`, where it wrote `/data.csv` with `out` read as a
  host. `file:///abs/data.csv` is still absolute; a host is now read as a directory, so write
  `file://localhost/abs/data.csv` as `file:///abs/data.csv` (GH-2424)
- NOAA GHCN daily stations QOORNOQ and ARSUK on the coast of Greenland and SORFJORD_KRV and
  SKJOMEN_SLETTJORD by the fjords near Narvik, the four rows listed at -100.0 m, have a null
  `elevation` instead of one 100 m below sea level. Real heights below sea level, such as DEATH
  VALLEY NP's, stay (GH-2418)
- NOAA GHCN hourly station GJBAKKI (`ICM00004919`) in southwestern Iceland, the one row listed at
  -99.0 m, has a null `elevation`. `interpolate` and `summarize` given an elevation moved its air
  temperatures and dew points from about 100 m below sea level; they now leave it out for those,
  as other stations of unknown elevation. Real heights below sea level stay (GH-2377)
- `wetterdienst stripes values` checks `--target`'s suffix against `--format`: `--format=jpg` now
  takes a `.jpeg` target, and a target merely ending in the format's letters, such as `stripespng`
  or `out.xpng`, is refused instead of written without the extension. The refusal names the
  suffixes it takes, `'.png'` where it said `'png'` (GH-2371)
- `Settings` takes an all-digit `WD_AUTH__METNO_FROST` as the Frost client id it is, and refuses a
  `WD_AUTH__CEDA` or `WD_AUTH__METNO_FROST` that is neither text nor a pair, such as `5`, `true` or
  a JSON object, with a `ValidationError` naming `auth.ceda` / `auth.metno_frost`. It raised a
  bare `TypeError` that named nothing, or took a JSON object's keys as the pair (GH-2379)
- A credential assigned to `settings.auth` after construction, such as `settings.auth.knmi = "key"`,
  is held as a secret and checked as one given to the constructor is: a `username:password` text
  for `ceda` is split, and the mask a JSON dump leaves behind is refused. It was kept as plain
  text, which `reveal()` and the providers failed on (GH-2387)
- `wetterdienst issues` reports a refused option, such as `--lead_time` on MOSMIX, as a one-line
  usage error with exit code 2 instead of a traceback with exit code 1. An upstream failure still
  logs its traceback and exits 1 (GH-2368)
- The climate stripes refuse a station that returns no rows, such as one whose data file is
  missing, with `NotEnoughDataError` ("has data for no year"): a 400 from `/api/stripes/values`
  and `/api/stripes/image` and their MCP tools, and that message from `wetterdienst stripes`. They
  raised polars' `ComputeError`, a 500 (GH-2369)
- `wetterdienst history --target file://history.json`, the form its docs show, writes
  `history.json`. The `file://` prefix was kept, so the write went to `file:/history.json` and
  failed with "No such file or directory". A plain path works as before (GH-2370)
- The Docker image reads BUFR: DWD road weather data, and radar BUFR with `read_bufr`. It had the
  eccodes bindings but no ecCodes library behind them; it now installs Debian's, which adds about
  55 MiB. That library is 2.41.0, so the bindings warn on import that 2.42.0 is recommended
  (GH-2409)
- `Settings()` no longer fails where no home directory resolves (HOME unset and the uid missing
  from the password database), which it did with platformdirs 4.12 even with
  `cache_disable=True`. Without `WD_CACHE_DIR` the cache is then kept in a temporary directory, one
  per process and removed at exit, with a warning to set `WD_CACHE_DIR` or `HOME`; a `~` directory
  below the working directory is no longer created with older platformdirs either (GH-2408)
- Reading BUFR (DWD road weather, radar with `read_bufr`) no longer warns "ecCodes 2.42.0 or
  higher is recommended" with an older ecCodes library, such as Debian trixie's 2.41 or Ubuntu
  24.04's 2.34; the version is logged at debug instead. Under `-W error` this advice no longer
  gets BUFR reported as not installed either. To see the advice, import eccodes before wetterdienst
  does. Other warnings still show (GH-2442)
- `wetterdienst history` refuses a `--target` with a scheme other than `file://`, such as
  `s3://bucket/history.json`, as `alerts` does: a usage error with exit code 2 before anything is
  fetched. It ran the whole fetch first and then failed to write the file (GH-2425)

## [0.140.0] - 2026-10-05

### Added

- WSV Pegelonline and Eaufrance Hub'Eau stations name the vertical datum of their `gauge_zero` in
  a new string column `gauge_zero_datum`: Pegelonline's as published (`m. ü. NHN`, `m. ü. NN`,
  ...), Hub'Eau's as the Sandre label of `code_systeme_alti_site` (`IGN 1969`, ...), or the code
  where it has none. Stations differ in it, so compare gauge zeros only where it agrees, and not
  between Hub'Eau stations labelled as on an unknown or a local system (GH-2228)
- `wetterdienst issues`, `/api/issues` and the MCP `issues` tool list the DWD SWSMOS runs, and
  `DwdSwsmosRequest.available_issues(settings)` returns them as UTC datetimes. They refused
  dwd/swsmos as unsupported. One run holds every road station, so the list is the same for any
  station (GH-2319)
- `GET /api/settings` reports the settings `/api/values`, `/api/interpolate` and `/api/summarize`
  take where a request leaves them out: the server's `WD_TS_*` variables over wetterdienst's
  defaults, with the unit of every quantity. With `with_metadata`, those three endpoints' JSON and
  GeoJSON, and their MCP tools', carry a `settings` block next to `metadata`, with the settings the
  result was got with. Their OpenAPI schemas, which declare it, are now named
  `_ValuesWithSettingsDict`, `_ValuesWithSettingsOgcFeatureCollection` and so on (GH-2359)
- `GET /api/settings` takes the settings query parameters of `/api/values`, `/api/interpolate` and
  `/api/summarize`, and answers what they resolve to over the server's, for each endpoint that
  takes the parameter. A value one of them refuses is refused here with its 400 or 422, and an
  unknown parameter is a 422, as on those endpoints. Nothing is stored on the server (GH-2383)

### Changed

- `pydantic-settings` now has a floor of `>=2.14.0` (was `>=2.7.0`): `Settings` reads `.env` with
  its `dotenv_filtering` option, which 2.14.0 added. Upgrade it where it is pinned lower (GH-2349)
- **Breaking**: DWD derived `monthly/soil` returns its monthly totals of potential
  evapotranspiration as the new `evapotranspiration_potential_grass_fao` and
  `evapotranspiration_potential_grass_haude`, where they came as the daily `..._last_24h` names.
  Use the new names for monthly in requests, `parameter` filters, wide-frame columns and
  `ts_geo_station_distance`; daily keeps `..._last_24h` (GH-2042)
- **Breaking**: `/api/stripes/*` and MCP match a stripes `name` at a threshold of 0.8 by default,
  as the CLI and the stations and values requests do; it was 0.9, so a name may now find a station
  where it found none. Pass `name_threshold=0.9` to match as before (GH-2063)
- Climate stripes are coloured over the years asked for: with `start_year` and `end_year`, the
  lowest and highest of them take the ends of the colour map, and `value_scaled` in the CSV of
  `/api/stripes/values` runs from 0 to 1 over the years returned. They were scaled over the
  station's whole record (GH-2063)
- **Breaking**: `/api/stripes/values` and `/api/stripes/image` refuse neither or both of `station`
  and `name`, an `end_year` not after `start_year`, or a `name_threshold` outside 0 to 1 with a 422
  of typed entries, as the other endpoints do, where they answered a 400 with a string `detail`.
  An unknown query parameter is a 422 as well. Match on the entries' `type`: each is located at a
  parameter, but neither `station` nor `name` at `["query"]` alone. `wetterdienst stripes values`
  tells the same refusals in click's terms, with exit status 2 where it was 1 (GH-2060)
- **Breaking**: the REST API and MCP refuse with a 422 a stations, values or history request they
  answered before: one selecting stations in two ways, answered for the first (`station` with
  `name` returned the station alone), and one sending `rank` or `distance` beside anything but a
  point (or `rank` beside `name`), which was ignored. No selection, or half a point or bounding
  box, is a 422 where it was a 400. Each error is located at the parameter it concerns, typed
  `missing_one_of`, `mutually_exclusive`, `missing_with` or `requires`, the others in `ctx`. Send
  exactly one of `all`, `station`, `name`, a point with `rank` or `distance`, a bounding box, or
  `sql`, and drop a `rank` or `distance` left over from a point (GH-2056)
- `wetterdienst` no longer depends on cloup. Each command's `--help` lists its options in one
  list -- what is requested, which stations, then the output -- and ends with examples, and
  `wetterdienst --help` is a short overview rather than a hand-kept copy of every option. The CLI
  takes `--rank` beside `--name`, as the REST API does. A refused request is told in click's own
  terms, a line per problem -- `Missing option '--longitude'`, `Options '--station' and '--name'
  cannot be used together`, `Invalid value for '--distance'` with the value refused -- instead of
  pydantic's echo of every option given (GH-2056)
- **Breaking**: `DwdDmoRequest.available_issues` lists the runs of `lead_time="short"` by default,
  as its docstring said and a default request reads; it listed every lead time, so `wetterdienst
  issues` and `/api/issues` named runs the default `values` request rejected with `IndexError`.
  Pass `lead_time="long"` (`--lead_time long`) for the long runs, or `lead_time=None` in Python
  for every lead time together (GH-2009)
- **Breaking**: DWD DMO refuses the values of a request naming a parameter its lead time's run does
  not carry with `ParameterNotCarriedError`, a `ValueError` naming the lead time that does, where
  the parameter answered with an empty frame: `icon`'s four 3-hourly parameters under the default
  `lead_time="short"`, its three 1-hourly ones under `"long"`. The REST API answers 400. Ask for
  them with the lead time named, apart from any parameter only the other lead time carries; a
  request for a whole dataset is not refused (GH-1976)
- **Breaking**: `cloud_cover_below_1000ft` is `cloud_cover_below_2km`. It is DWD's `nl` in
  `dwd/mosmix` and `dwd/dmo`, low cloud below 2 km, which the old name and its glossary entry put
  at 1000 ft. Request the new name; the old one in a request, as a `ts_geo_station_distance` key or
  as a wide column in a SQL filter is reported with its replacement. A wide DuckDB, SQLite or
  PostgreSQL table `to_target` wrote before takes no append of it: write it anew (GH-1977)
- **Breaking**: `imgw/meteorology` `daily/precipitation` returns `precipitation_amount` as 0 mm,
  with `quality` 11, for a day the file leaves out of a month the station reports in; such a day
  was missing. Drop `quality` 11 to get the rows as before. Other parameters and datasets are
  unchanged (GH-2000)
- **Breaking**: Eaufrance Hub'Eau stations list the altitude of the gauge's zero, in metres, as
  `gauge_zero`, as WSV Pegelonline does; it was listed as `elevation`. Read `gauge_zero` for it
  (GH-2020)
- Each station history gives the `resolution` and `dataset` it belongs to beside its `station_id`,
  whichever `sections` are asked for. DWD observation answers up to one history per station and
  dataset, and a request for several datasets left them to be told apart by the records inside
  (GH-2224)
- **Breaking**: the `postgresql` extra installs psycopg 3 instead of psycopg2, and a bare
  `postgresql://` target writes through psycopg 3 whenever it is installed, on every SQLAlchemy
  version; under 2.1 it failed with `No module named 'psycopg'`. `postgresql` and `mysql` bring
  SQLAlchemy and pandas, so neither needs `export` beside it. For `postgresql+psycopg2://`,
  install `psycopg2-binary` yourself; the Docker image has psycopg 3 only, so drop `+psycopg2`
  there (GH-2202)
- Eaufrance Hub'Eau stations list as `elevation` the altitude of their site, `altitude_site` from
  Hub'Eau's sites referential, in metres. It is null where the site gives none, gives 0, or gives
  one below -10 m or from 4810 m up, and for every station when that referential cannot be read,
  which is logged as a warning. About three stations in four have one (GH-2223)
- **Breaking**: `/api/values`, `/api/interpolate`, `/api/summarize` and their MCP tools answer a
  failure on the server's or the data source's side with a 500 carrying its message, where values
  answered 400 and the other two 404. Retry or report a 500 rather than rephrasing. A request
  refused for what it asks keeps its 400 or 404. Those refusals that raised a bare `ValueError` or
  `IndexError` raise a subclass of it: `InvalidTimeIntervalError`, `InvalidEnumerationError`, or
  the new `InvalidBoundingBoxError`, `LocationOutOfRangeError` and `IssueNotFoundError`. Catch
  `InvalidTimeIntervalError` for the day `9999-12-31`, which raised `OverflowError`, and
  `LocationOutOfRangeError` for a point outside UTM, which raised `utm.error.OutOfRangeError`
  (GH-2252)
- **Breaking**: `/api/stations`, `/api/history`, `/api/issues`, the `/api/stripes` endpoints and
  their MCP tools answer a failure on the server's or the data source's side to read what was asked
  for with a 500 carrying its message, where they answered 400, as `/api/values` does. Retry or
  report a 500 rather than rephrasing. A request refused for what it asks keeps its 400 (GH-2276)
- **Breaking**: `/api/alerts` and its MCP tool answer a failure to list, download or read DWD's CAP
  feed with a 500 carrying its message, where they answered 400. Retry or report a 500 rather than
  rephrasing; a `date` that does not parse or lies before DWD's rolling window keeps its 400, and
  one an offset carries past a datetime's range is a 400 where it was a 500.
  `DwdWeatherAlertRequest.query()` raises a date before the window as `InvalidTimeIntervalError`,
  still a `ValueError`, and a listing without any snapshot as `FileNotFoundError` (GH-2294)
- The `mysql` extra takes pandas 3, as the other extras that bring pandas do. It asked for pandas
  below 3, so installing it downgraded an environment on pandas 3 to 2.x (GH-2250)
- DWD DMO's coverage, from `discover`, `/api/coverage`, the CLI and MCP, gives each parameter
  `lead_times`: the lead times whose run carries it, such as `["long"]` for `icon`'s
  `precipitation_amount_last_3h` and `["short"]` for every `icon_eu` parameter. A caller can offer
  only what the `lead_time` it sends will answer; the other keys are as they were (GH-2256)
- **Breaking**: a dict given as `fsspec_client_kwargs` or `WD_FSSPEC_CLIENT_KWARGS` is merged into
  the defaults, `headers` one level deep, where it replaced them, so the docs' proxy example
  `{"trust_env": True}` no longer drops the 30 s timeout and the User-Agent. A key given still wins:
  give `"timeout": None` for aiohttp's own timeout, which a dict without one used to get, and a
  `User-Agent` header of your own to send that instead of wetterdienst's (GH-2269)
- **Breaking**: the InfluxDB sinks read a target as the SQL sinks' SQLAlchemy does: the password
  ends at the first `@`, and the username, password and database are percent-decoded, as the
  CrateDB database (its schema) now is too. Write an `@` in an InfluxDB org, password or token as
  `%40`, and a literal `%` followed by two hex digits there or in an InfluxDB database or CrateDB
  schema as `%25`. An `@` in the path or query of an InfluxDB or CrateDB target with a `host:port`
  is read as ending a password too; write it as `%40` there (GH-2248)
- **Breaking**: the InfluxDB 3 sink connects with the scheme and port its target names:
  `influxdb3://` is http and `influxdb3s://` https, on the target's port or, with none, 8181 (an
  InfluxDB 3 Core's) for http and 443 for https. It took only the host and went to https on 443
  whatever the target said, so a local InfluxDB 3 Core could not be reached. Write an https
  server, such as InfluxDB Cloud, as `influxdb3s://` (GH-2279)
- **Breaking**: `Settings` refuses a `ts_skip_threshold` outside (0, 1], as `--skip_threshold`
  does. One above 1, as `WD_TS_SKIP_THRESHOLD=5`, skipped every station under `ts_skip_empty`, and
  `values` said "No data available" with no hint at the setting. Such a variable, or one of 0, now
  fails every `Settings()`; correct or remove it. `/api/values` answers a `skip_threshold` of 0
  with a 422, and the MCP `values` tool refuses it; to skip no station, leave `skip_empty` off
  (GH-2334)
- **Breaking**: DWD SWSMOS raises `IssueNotFoundError` for an `issue` naming a run DWD does not
  hold, as MOSMIX and DMO do, so the REST API answers it as the caller's error. It returned no rows,
  as if the run held nothing for the station. Catch `IssueNotFoundError`, or pick the issue from
  `DwdSwsmosRequest.available_issues` (GH-2324)
- A NOAA GHCN station asked for at both `hourly` and `daily` has the daily list's `elevation` on
  its hourly row as well, where the two lists put it within 5 km of each other, unless the daily
  list gives 0.0 against an hourly height. Interpolate and summarize, by station id or by point,
  then use one elevation for such a station whatever the order of the parameters. Otherwise each
  row keeps its own list's elevation. A request for one resolution is not affected by this
  (GH-2336, GH-2362)
- Locked dependencies refreshed within their declared ranges -- 21 packages, among them
  duckdb 1.5.6, platformdirs 4.12.2, and SQLAlchemy 2.1.2 and xarray 2026.9 on Python 3.11 and
  later; 3.10 keeps the release lines that still support it (GH-2403)

### Deprecated

- `summarize`'s `use_nearby_station_distance` (the CLI's `--use_nearby_station_distance`,
  `/api/summarize` and the MCP `summarize` tool) is deprecated and will be removed in a future
  release. It never had an effect on a summary; leave it out. The CLI warns when it is given, the
  REST API logs it, and the schema marks it deprecated. The setting
  `ts_geo_use_nearby_station_distance` stays, for interpolation (GH-2333)

### Fixed

- `Settings` ignores a key of `.env` that is no setting, such as another program's
  `POSTGRES_PASSWORD`, as it ignores one in the environment. Such a key made every `Settings()`
  fail with its value in the error, and the CLI commands and the REST API that read the settings
  refused to run. A `WD_*` key that names no setting, such as the misspelt `WD_CACHE_DIABLE`, is
  ignored too, as in the environment. A keyword to `Settings(...)` that is no setting is still
  refused (GH-2349)
- `Settings` no longer takes a `.env` key without the `WD_` prefix for the setting it names, as it
  did with pydantic-settings older than 2.11, which the `>=2.7.0` floor allowed: another program's
  `CACHE_DIR` or `TS_SHAPE` set wetterdienst's cache directory or result shape (GH-2373)
- `Settings` refuses a non-empty `ts_geo_station_distance` or
  `ts_geo_station_distance_resolution_factors` that is not a mapping, such as
  `WD_TS_GEO_STATION_DISTANCE=5`, with a `ValidationError` naming the setting, where it raised a
  bare `TypeError` that named nothing (GH-2353)
- Climate stripes values and images (CLI `stripes values`, `/api/stripes/values`,
  `/api/stripes/image`, MCP `stripes_values` and `stripes_image`) no longer fail under
  `WD_TS_SHAPE=wide`, which raised `ColumnNotFoundError`, or under `WD_TS_SKIP_EMPTY=true`, which
  raised a `ComputeError` for a station with gaps in its record. They read the values long and
  unskipped whatever those two say (GH-2348)
- `wetterdienst issues --dataset/--lead_time`, and the `/api/issues` and MCP `issues` descriptions
  of `dataset` and `lead_time`, said other networks ignore them. They are DWD DMO only, and MOSMIX
  and SWSMOS refuse them, so leave them out there (GH-2347)
- Interpolate and summarize answer under `ts_humanize=False` and `ts_shape="wide"`, however they
  are set: `Settings`, `WD_*`, the CLI's or REST API's `humanize`. The first returned no data and
  the second raised `ColumnNotFoundError`. The result is long either way, its parameters named by
  the source's codes under `ts_humanize=False` (GH-2331)
- The `/api/values` description, which is the MCP `values` tool's, and the MCP instructions said
  the `values` array is sorted by timestamp. It is grouped by station, then by resolution, dataset
  and parameter, in timestamp order within each group, so a parameter's latest timestamp is the
  last of its group. The description now also says what a wide item and a GeoJSON response hold
  (GH-2295)
- Values: a station asked for several datasets is no longer skipped when one dataset has no
  `start_date` in the station list and another starts after `end_date`. With NOAA GHCN `hourly`
  and `daily` together, such a station returned no hourly values inside the window (GH-2292)
- Interpolation and summary take a station's elevation from another requested resolution's row
  where the first row they read gives none. With NOAA GHCN `hourly` named before `daily`, the
  `..._by_station_id` methods answered without the elevation of 859 stations the hourly list gives
  none for (6 the other way round), and an answer at an elevation could leave such stations out
  (GH-2300)
- `/api/values` and its MCP tool answer `unit_targets` naming a quantity the converter does not
  have, such as `{"foo": "bar"}`, with a 400 saying so, where they answered a bare 500 (GH-2272)
- `/api/interpolate`, `/api/summarize`, `/api/alerts` and their MCP tools answer a malformed `WD_*`
  setting in the server's `.env` with a bare 500, where they answered 400 with the setting's value
  in `detail`; `/api/stations`, `/api/history` and `/api/issues` no longer give the value in their
  500. A request refused for what it gives keeps its 400 (GH-2297)
- `wetterdienst values` refuses such `--unit_targets` with `Invalid value for '--unit_targets'`
  and exit status 2, where it died with a traceback (GH-2296)
- `Settings` refuses a `ts_unit_targets` unit the converter does not have for its quantity, such as
  `{"temperature": "furlong"}`, or one only a source publishes in. It was refused once the stations
  had been fetched, so the CLI died with a traceback; `values`, `interpolate` and `summarize` now
  exit with status 2, and `/api/interpolate` and `/api/summarize` answer 400 where they answered
  404. Such a unit in `WD_TS_UNIT_TARGETS` now fails every `Settings()`, as an unknown quantity
  there does, where it broke only values requests: set when the REST server starts, it stops it at
  import; set in `.env` later, requests answer 500. Correct or remove it. An unknown quantity's
  refusal names only the unknown ones (GH-2306)
- `/api/values` answers a malformed `WD_TS_UNIT_TARGETS` in the server's `.env` with a bare 500,
  where it answered 400 with the setting's value in `detail`; `/api/stripes/stations`, `/values`
  and `/image` no longer give a malformed setting's value in their 500. The MCP tools answer the
  same (GH-2312)
- Interpolation places stations across a UTM zone boundary (in Germany at 6 and 12 deg E, most
  places every 6 deg of longitude) or the equator in the zone of the point. Each was placed in its
  own zone, hundreds of kilometres off, or 10000 km off across the equator, so a point near either
  got no value, or one weighted as if those stations stood elsewhere. A station beyond 80 deg S or
  84 deg N, where UTM ends, is now left out; it failed the whole interpolation. The
  `interpolation` extra needs utm 0.8 or later, the first to keep the point's hemisphere (GH-2277)
- Network: a download that keeps arriving no longer fails with `FSTimeoutError` once it runs past
  the `timeout` in `fsspec_client_kwargs` (30 s by default), so a slow link can fetch large files.
  A number there now bounds each wait, to connect and for the next bytes of the answer, not the
  whole request. The settings docs give that default, where they listed `{}` (GH-2258)
- Eaufrance Hub'Eau stations are listed when the station referential takes more than 30 seconds
  to arrive, which it often does; the list failed with `FSTimeoutError`. The referential now has
  the 120 seconds the observations requests have (GH-2221)
- `to_target` and the CLI's `--target` log the target with its password as `***`. They logged it
  verbatim at INFO, which the CLI shows by default, so a database password or the InfluxDB 2/3 API
  token in the password slot reached stderr and any log it was captured in (GH-2219)
- A `/`, `?` or `#` in the password of an InfluxDB or CrateDB target, or a `?` or `#` in a SQL one,
  is read as part of it. It was read as the end of the host part, so the export went to the wrong
  host, port, database or table, and pieces of the password reached the log. A password whose
  unencoded `@` cannot be read is refused with `ExportRefusedError`, naming none of it (GH-2248)
- DWD derived can be used on a base install. Its station lists were read with pandas, so
  `Wetterdienst("dwd", "derived")` failed with an `ImportError` unless an extra that brings pandas,
  such as `export`, was installed. They are read with polars now, with the same result (GH-2213)
- Precipitation stripes colour dry years brown and wet years teal; they were the other way round.
  A year range holding fewer than two years with data is refused, where one beyond the station's
  record answered with no values and an empty image, and stripes start and end at a year with data.
  Years all of one value take the middle colour rather than none (GH-2063)
- Images are sent as `image/jpeg`, `image/svg+xml` and `application/pdf`, where charts and stripes
  were sent as `image/jpg` and `image/svg`, and stripes as `image/pdf` (GH-2063)
- DWD DMO returns in metres the elevation of 32 `F9` stations that DWD gives in feet: `F9051`
  QUERETARO/GUTIERREZ is at 1919 m, not 6296 m. A warning names such a station once DWD gives it
  another value. An elevation in a run that is not a number is returned as null; it previously
  failed the whole station list (GH-2017)
- `interpolate` and `summarize` estimate for a point on the equator or the prime meridian. A
  latitude or longitude of 0 was taken for no point at all, and the request failed with "Either
  latitude and longitude or station must be provided" (GH-2056)
- `wetterdienst about fields` applies `--debug`, and for any network but DWD observation answers
  with a usage error naming the one it describes; it ended in an `AttributeError` traceback
  (GH-2056)
- `wetterdienst radar --wmo_code` finds the site it names. The option was read as text and compared
  with the sites' integer WMO codes, so every lookup failed with a `KeyError` traceback. A code no
  site carries now answers `Error: Radar site not found` and exit status 1, and an ODIM code of the
  wrong length is a usage error rather than a traceback (GH-2023)
- `wetterdienst history --sections` returns only the sections it names; it returned all five. The
  REST API filtered already but in a random order, and both now keep the history's own order. A
  section name the history does not have is a usage error rather than a traceback, as is a request
  with neither `--all` nor `--station` (GH-2022)
- `wetterdienst --help` and the command help name only options and commands that exist:
  `--convert_units` for `--si_units`, no `--tidy`, `--wmo_code` and `--country_name` for `radar`,
  and `stripes values` for `warming_stripes`, the command's old name. `--convert_units` converts to
  the unit targets, not to SI units: temperature stays in °C by default. The overview that listed
  options under commands that do not take them is gone, the `--sql_values` example on a column
  runs in the wide shape it needs, and the README counts nearly 600 parameters, not 514 (GH-2021)
- DWD observation history gives the station id zero-padded in its `parameter`, `device` and
  `geography` sections, `01048` as in `name`, `missing_data` and the stations and values frames.
  They gave `1048`, so joining them with those frames on `station_id` found nothing. Each history
  also gives its station's `station_id` beside the sections, whichever `sections` are asked for, so
  one whose sections hold no records still names its station (GH-2058)
- Values converted to a much larger unit keep their precision. Every converted value was rounded to
  four decimals, so with `WD_TS_UNIT_TARGETS='{"length_short": "mile"}'` 5 cm of snow came back as
  `0.0`. A conversion now keeps one more decimal per order of magnitude it shrinks a value by, so
  under the default targets a reading published in percent, Pa, mm, kJ/m² or l/s can carry up to
  three more decimals where its source gives them (GH-2002)
- `interpolate` and `summarize` round a value as `values` rounds a converted reading of the same
  parameter, where they rounded every value to two decimals: with
  `WD_TS_UNIT_TARGETS='{"length_short": "mile"}'` a summarized 5 cm of snow came back as `0.0`, and
  a cloud cover of 0.875 as 0.88. Values are rounded to four decimals or more, so an interpolated
  6.64 °C now reads 6.6422; `distance` and `distance_mean` keep two (GH-2225)
- With `WD_TS_CONVERT_UNITS=false`, `interpolate` and `summarize` no longer round away a reading
  published in mm/s: `dwd/road` publishes 0.1 mm/h of precipitation intensity as 0.0000278 mm/s,
  which came back as `0.0`. A value is now rounded as one converted into its source unit from its
  target unit would be, so the decimals follow `WD_TS_UNIT_TARGETS` even though nothing is
  converted. Under the default targets mm/s keeps seven, as do durations in hours and visibility in
  km, durations in minutes, kPa and depths in metres keep five or six, and every other unit four
  (GH-2257)
- PostgreSQL and MySQL export targets no longer fail on `?table=`: it names the table and is no
  longer passed to the database driver, which refused it as a connection option, so no such target
  could be written to. The rest of the query, such as `sslmode` or `charset`, still reaches the
  driver (GH-1974)
- On Windows, a request that downloads many files at once with a cache no longer fails with
  `PermissionError: [Errno 13]` when two of its download threads read and replace the cache's
  metadata file at the same time; the threads of one process now take turns. Two processes
  sharing a cache directory can still meet that way (GH-1990)
- DWD DMO dates each run as the latest date on or before now that its `DDHHMM` stamp can name.
  Between the 1st's 00 UTC run appearing (about 03:10 UTC) and 04:01, every run was a month early:
  `available_issues` listed past issues and `values` for the newest issue raised `IndexError`. On
  1 January, April, June, August and November it named days the month lacks, such as 31 November,
  so `available_issues` and `values` raised `InvalidOperationError` and the station list lost the
  stations only a run describes (GH-2203)
- The REST API's OpenAPI schema types a station's `elevation`, `latitude`, `longitude` and `name`
  as nullable, and declares that a station may carry the columns its provider adds, such as
  `gauge_zero`, so a client generated from it keeps them. MCP tools no longer fail output
  validation on a station row holding such a null, as every WSV station does (GH-2226)
- GeoJSON of stations and values gives a station without an elevation the position `[lon, lat]`;
  it was `[lon, lat, null]`, which strict GeoJSON parsers reject. One collection can now hold both
  lengths, so read an elevation from a third number only where there is one. Each feature's
  `properties` also carry the station columns a provider adds, such as WSV's `gauge_zero` and
  characteristic values, DWD road's station group and road columns, and the `icao_id` of DWD
  MOSMIX, DMO and POI (GH-2222)
- DWD observation history no longer fails for a station whose name holds a non-ASCII letter, such
  as 01684 Görlitz: its missing-data file is read as latin-1, as DWD writes it, where it raised
  `UnicodeDecodeError` and `/api/history` answered 400 (GH-2214)
- `/api/values` answers a `ValueError` raised while reading a provider's values with a 400
  carrying its message, where it answered a 500 with none, and the MCP `values` tool, which calls
  it, now passes the message on. `wetterdienst values` still logs it and exits 1 (GH-2218)
- MySQL and MariaDB export targets create `DATETIME` columns holding UTC, so values before 1970
  can be written. Their `TIMESTAMP` columns started in 1970, so the first earlier row was refused or
  stored as zeros. A table created by an earlier version keeps its `TIMESTAMP` columns and what
  they stored; to get `DATETIME`, write it anew with `if_exists='replace'`, which drops every row
  it held (GH-2229)
- SQL Server export targets (`mssql://`) create `DATETIME2` columns holding UTC for datetimes.
  They created `timestamp` columns, which SQL Server takes as `rowversion`, a row counter that
  refuses any value written to it (GH-2249)
- GeoJSON of values gives each feature, one per dataset of a station, that dataset's values only,
  and no feature to a dataset the station returned no values for; each feature carried the values
  of every dataset, so each value appeared once per dataset (GH-2253)
- GeoJSON of values in the wide shape gives a station one feature per resolution into which
  several requested datasets were merged, with `dataset` null as its rows have it, and dates from
  the earliest start to the latest end of those datasets. Each merged dataset got a feature holding
  all of the rows, so each value appeared once per dataset. Read a value's dataset from its column
  prefix; the REST API's schema types `dataset` as nullable (GH-2274)
- The MCP `values` tool answers with GeoJSON and in the wide shape; it failed its own output
  validation. The REST API's schema for `/api/values` gives a GeoJSON feature's values no
  `station_id`, which the feature's properties carry, and a wide row `resolution`, a nullable
  `dataset`, `timestamp` and, outside GeoJSON, `station_id`, plus a value and a quality column per
  parameter, typed as nullable numbers where pydantic is 2.12 or later (GH-2282)
- GeoJSON of stations and values gives a station without a latitude or longitude, such as a
  postcode of DWD derived `monthly/climate_correction_factor`, the geometry `null`, as RFC 7946
  has an unlocated feature; it was a `Point` of null coordinates, which strict parsers reject. The
  REST API's schema types `geometry` as nullable, so check for `null` before reading it (GH-2241)
- DWD derived stations at 1000 m or higher keep the first digit of their elevation and their
  `end_date`: Brocken was listed at 135 m and Zugspitze at 956 m, both with a null `end_date`.
  This affects the monthly degree-day and degree-hour datasets and hourly `radiation_global` and
  `sunshine_duration` (GH-2234)
- NOAA GHCN daily stations without a known elevation have a null `elevation`. They were listed at
  -999.9 m, the station list's missing value, and `interpolate` and `summarize` given an elevation
  took it for a known one (GH-2247)
- NOAA GHCN hourly stations without a known elevation have a null `elevation` too. They were
  listed at -999.9 m, the station list's missing value (GH-2260)
- NOAA GHCN stations asked for both `hourly` and `daily` in one request are listed; the request
  failed with a polars schema error. The hourly stations have a null `start_date` and `end_date`,
  as their station list gives none (GH-2267)
- DWD MOSMIX takes an `issue` given without an offset as UTC, as DWD DMO does, and converts one
  with an offset to UTC before flooring it to a run. A naive issue was read in the server's local
  time, and an offset one floored in its own hours, so a published run could go unfound. The
  request's `issue` is now a UTC datetime; compare it with aware datetimes (GH-2275)
- DWD SWSMOS converts an `issue` given with an offset to UTC before flooring it to a run, as DWD
  MOSMIX and DMO do. It kept the issue's wall-clock hour and relabelled it UTC, so
  `2026-10-01T13:00+02:00` read the 13 UTC run rather than the 11 UTC one it names (GH-2288)
- The InfluxDB 2 sink reaches an IPv6 host, such as `influxdb2://acme:tok@[::1]:8086/`. It dropped
  the brackets and sent `http://::1:8086`, which names no valid host (GH-2279)
- The InfluxDB 1 sink reaches an IPv6 host, such as `influxdb://root:pw@[::1]:8086/`. It dropped
  the brackets, so its client's base URL was `http://::1:8086`, which names no valid host (GH-2287)
- DWD SWSMOS reads the run an `issue` names when asked through the CLI (`--issue`), the REST API or
  MCP. The issue was dropped on the way, so the latest run was read whatever was asked. An `issue`
  that is no ISO date raises `InvalidTimeIntervalError`, a `ValueError`, as MOSMIX and DMO do, so
  the REST API refuses it as the caller's error, as it does theirs (GH-2299)
- `wetterdienst alerts` reports a DWD feed it cannot read as an error with exit status 1, as it does
  a failed download, where it reported an invalid option with exit status 2. A `--date` before
  DWD's rolling window is still a usage error, now named as `Invalid value for --date` (GH-2313)
- The CLI's `values`, `interpolate` and `summarize` leave a setting whose option is not given on
  the command line to its `WD_TS_*` variable, such as `WD_TS_SHAPE=wide`. They passed every
  option's default, which outranks the environment, so those variables had no effect (GH-2307)
- The CLI's `interpolate` and `summarize` refuse a bad station distance or unit target in one line
  naming its option, as `values` does, where they printed pydantic's whole message. All three raise
  a malformed `WD_*` variable as it is rather than as a usage error, also one merged into the dict
  an option gives, such as `WD_TS_UNIT_TARGETS` beside `--unit_targets` (GH-2308)
- `WD_TS_GEO_USE_NEARBY_STATION_DISTANCE`, `WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS` and
  `WD_TS_GEO_NUM_ADDITIONAL_STATIONS` can be set from the environment or `.env`. The settings
  refused the string an environment variable gives, so setting any of them made every `Settings`
  fail (GH-2326)
- The REST API's and MCP's `values`, `interpolate` and `summarize` leave a setting the request does
  not give to the server's `WD_TS_*` variable, such as `WD_TS_SHAPE=wide`, as the CLI does, where
  those variables had no effect. A client that parses one layout whatever the server sets sends
  `shape`, `humanize` and `convert_units` with its request (GH-2325)
- The REST API refuses a bad `unit_targets` or station distance in one line naming its field and
  quoting what the request gave, where the 400 was pydantic's whole message quoting the dict merged
  from it and the server's `WD_TS_UNIT_TARGETS` or `WD_TS_GEO_STATION_DISTANCE` entries (GH-2329)
- A malformed `WD_*` setting is told by the variable that sets it and what is wrong with it, a
  line each and without pydantic's echo of the value, where it ended in pydantic's traceback. The
  REST API refuses to start with it, also under `uvicorn` directly unless its lifespan is turned
  off, and `wetterdienst restapi` exits with uvicorn's status 3; the other CLI commands that read
  the settings exit with status 1 (GH-2335)
- Values in the wide shape can be drawn: `ValuesResult.to_plot`, and with it the image formats
  (`html`, `png`, `jpg`, `webp`, `svg`, `pdf`) of the CLI's `values` and `/api/values`, draw a wide
  result as they draw the long one. They raised `ColumnNotFoundError` on `parameter` (GH-2330)
- `wetterdienst alerts` refuses a `--date` that does not parse, or that an offset carries out of a
  datetime's range, as `Invalid value for --date` with exit status 2; the latter was a traceback.
  It raises a malformed `WD_*` variable as it is rather than as an invalid option, as `values`
  does, and a `--target` it cannot write is an error with exit status 1, not a traceback (GH-2322)
- NOAA GHCN hourly stations listed at 9999.0 m or 8191.0 m, 154 placeholders such as the North
  Sea lightship ELBE NO. 1, have a null `elevation`. `interpolate` and `summarize` given an
  elevation took them for known ones (GH-2336)
- `wetterdienst history` and `wetterdienst stripes values` end a `--target` they cannot write,
  such as one in a directory that does not exist, as `Error: Could not write --target: ...` with
  exit status 1, as `alerts` does; it was a traceback after the whole fetch (GH-2346)
- NOAA GHCN daily stations of the Brazilian network (`BR0...`) listed at 0.0 m, 912 placeholders
  such as ALFENAS at about 880 m, have a null `elevation`. `interpolate` and `summarize` given an
  elevation took them for stations at sea level. A 0.0 m outside that network stays (GH-2362)
- NOAA GHCN hourly stations listed at -999.0 m, 93 placeholders such as BOGUS ALGERIAN, have a
  null `elevation`. `interpolate` and `summarize` given an elevation took them for known ones
  (GH-2352)
- A `Settings` field assigned after construction is validated as one given to the constructor:
  `settings.ts_skip_threshold = 5` or `settings.ts_shape = "foo"` raises a `ValidationError` naming
  the field, where it was taken and failed later or skipped every station. A radius assigned
  reaches `ts_geo_station_distance` at once, and a dict assigned to `fsspec_client_kwargs` is
  merged into the defaults as one given is, where it replaced them (GH-2342)
- NOAA GHCN hourly stations listed at 0.0, 0.0, or named `BOGUS ...`, 15 placeholders such as
  BOGUS AUSTRIAN, have a null `latitude` and `longitude`. They are still fetched by id, but no
  rank, distance or bbox search, `interpolate` or `summarize` picks them. A rank search now leaves
  out every station without a position, which it sorted first, ahead of the nearest; estimating
  at one by station id is refused with a `LocationOutOfRangeError`. The CLI prints that error in
  one line, also for a point beyond the latitudes UTM covers, where it was a traceback (GH-2380)
- A `Settings` once in the wide shape drops nulls again once it is long. The wide shape wrote
  False into `ts_drop_nulls` for good, so a `Settings` reused for a long request returned the
  null rows. The field now keeps the value given, so `Settings(ts_shape="wide").ts_drop_nulls`
  reads True; read `ts_drop_nulls_effective` for whether nulls are dropped (GH-2388)
- The REST API's OpenAPI schema, and the MCP tools built from it, give each settings parameter of
  `/api/values`, `/api/interpolate`, `/api/summarize` and `/api/settings` the server's value as
  its default: with `WD_TS_SHAPE=wide`, `shape` is `wide`. `drop_nulls` is `WD_TS_DROP_NULLS` or
  true, what leaving it out means whatever the shape. They gave wetterdienst's, which a client
  filling in defaults sent, hiding the server's. Read once per server process: restart it after
  editing its `.env` (GH-2393)

### Security

- **Breaking**: the `sql` and `sql_values` filters run on a DuckDB connection holding only the
  frame, so they raise a `duckdb.Error` on a table of DuckDB's default connection, a file, a URL
  or an extension; join or filter the returned frame with polars instead. The clause is a single
  condition: a statement after `;`, `ORDER BY` or `LIMIT` raises `duckdb.ParserException`; sort or
  slice the returned frame instead. It runs on one thread, with DuckDB's memory limit at 1 GiB
  plus the frame's size and no disk to spill to (`duckdb.OutOfMemoryException`). The REST API
  answers these as client errors. Any REST or MCP client could read the server's files, read
  DuckDB's settings through an appended statement, or run a query on every core with most of the
  memory (GHSA-rpwr-qmm5-m9wp)
- **Breaking**: the REST API and MCP server refuse `sql` (stations, values) and `sql_values`
  (values, interpolate, summarize) with a 403 unless they run with the new setting `restapi_sql`
  enabled; set `WD_RESTAPI_SQL=true` to accept them as before. Enabled, the clause runs in DuckDB
  on the server within the limits above, which hold per request: it can still read DuckDB's
  settings, which name paths on the server, run for as long as it likes on one thread, and
  allocate memory DuckDB's limit does not count. The library and the CLI are not gated
  (GHSA-rpwr-qmm5-m9wp)

## [0.139.0] - 2026-09-29

### Changed

- **Breaking**: the station column `height` is now `elevation`, in every stations frame and its
  JSON, CSV and `with_stations` output. History's `station_height` is `station_elevation`, the DWD
  radar BUFR frame's `height` is `elevation`, and `NoStationsWithHeightError` is
  `NoStationsWithElevationError`. Read `elevation` instead; a SQL filter still naming `height` fails
  with an error naming `elevation`. A DuckDB, SQLite or PostgreSQL table `to_target` wrote before
  takes no append of `elevation`: write it anew (GH-2024)
- **Breaking**: the station column `state` is now `region`, in every stations frame and its JSON,
  CSV, GeoJSON and `with_stations` output. Read `region` instead; a SQL filter still naming `state`
  fails with an error naming `region`. A DuckDB, SQLite or PostgreSQL table `to_target` wrote before
  takes no append of `region`: write it anew (GH-2026)
- **Breaking**: the values column `date` is now `timestamp`, in long and wide values, interpolated
  and summarized values, their JSON, CSV, GeoJSON, NetCDF and Zarr output, the stripes values and
  the DWD radar BUFR frame. The `date` request parameter, `filter_by_date` and the station columns
  `start_date`/`end_date` keep their names. Read `timestamp` instead; a SQL filter on values still
  naming `date` fails with an error naming `timestamp`. A DuckDB, SQLite or PostgreSQL table
  `to_target` wrote before takes no append of `timestamp`: write it anew (GH-2028)
- **Breaking**: in wide values, each parameter's quality column is `<parameter>_quality` rather than
  `qn_<parameter>` (`<dataset>_<parameter>_quality` where several datasets are requested). Read the
  new name instead; a SQL filter still naming a `qn_` column fails with an error naming its
  `_quality` successor. A DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no
  append of the new columns: write it anew (GH-2030)
- **Breaking**: 31 parameter names lose a misspelling, a German word or a mistranslation: `gras` is
  `grass`, `chlorid` `chloride`, `loamysilt`/`loamysand`/`winterwheat` are split into words,
  `count_weather_type_ripe` is `count_weather_type_hoar_frost`, `thawing_thickness_plantstock*` is
  `thawing_thickness_plant_cover*`, `wave_height_sign` is `wave_height_significant`,
  `thawing_thickness_bare*` is `thawing_thickness_bare_ground*`, `number_of_{days,hours}_per_month`
  are `count_{days,hours}_in_month`, `wind_movement_24h` is `wind_movement`, and
  `cloud_cover_between_2km_to_7km` is `cloud_cover_between_2km_and_7km`. Request the new name; an
  old one in a request, or as a wide column in a SQL filter, is reported with its replacement. A
  wide DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no append of them
  (GH-2032)
- **Breaking**: `dwd/observation` `snow_depth_excelled` and `water_equivalent_snow_depth_excelled`
  are `snow_depth_sampled` and `water_equivalent_snow_depth_sampled`. They are DWD's *ausgestochene
  Schneehöhe*, the snow cut out as a sample to measure its water equivalent; their descriptions and
  app labels said snow beyond the measuring range, which neither is. Request the new names; an old
  one in a request, or as a wide column in a SQL filter, is reported with its replacement. A wide
  DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no append of them (GH-2034)
- **Breaking**: `humidity`, `humidity_max` and `humidity_min` are `humidity_relative`,
  `humidity_relative_max` and `humidity_relative_min`; `humidity_absolute` is unchanged. Request the
  new names; an old one in a request, as a `ts_geo_station_distance` key or as a wide column in a
  SQL filter is reported with its replacement. A wide DuckDB, SQLite or PostgreSQL table
  `to_target` wrote before takes no append of them (GH-2036)
- **Breaking**: every parameter name containing `precipitation_height` or `evaporation_height` says
  `precipitation_amount` or `evaporation_amount` instead -- 66 names, from `precipitation_height`
  itself to `count_days_precipitation_height_ge_1mm` and `evaporation_height_multiday`. Request
  the new names; an old one in a request, as a `ts_geo_station_distance` key or as a wide column in
  a SQL filter is reported with its replacement. A wide DuckDB, SQLite or PostgreSQL table
  `to_target` wrote before -- a nightly `daily/kl` export, say -- takes no append of them (GH-2038)
- **Breaking**: `visibility_range`, `visibility_range_index` and
  `visibility_range_measurement_method` are `visibility`, `visibility_index` and
  `visibility_measurement_method`. Request the new names; an old one in a request, as a
  `ts_geo_station_distance` key or as a wide column in a SQL filter is reported with its
  replacement. A wide DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no append
  of them (GH-2040)
- Locked dependencies refreshed to their latest compatible versions -- 41 packages, among them
  fastmcp 4.0.10, fsspec 2026.9, SQLAlchemy 2.1 on Python 3.11 and later and zarr 3.4 on 3.12 and
  later; each older Python keeps the release line that still supports it (GH-2050)

## [0.138.0] - 2026-09-28

### Added

- `--if_exists` on `stations`, `values`, `interpolate` and `summarize`, taking `replace` (the
  default, and what the CLI did before), `append`, `fail` or `skip`. `to_target` has taken the
  argument since it was written but no command passed it, so every CLI export replaced: a nightly
  timer pointed at a DuckDB table held one run's rows rather than a history. A pairing the sink
  refuses is reported as a line and exit 1 rather than a traceback
- `precipitation_intensity` can be declared in `millimeter_per_second`, which is what BUFR publishes
  a precipitation rate in (`kg m-2 s-1`). It is a source unit only: `WD_TS_UNIT_TARGETS` cannot ask
  for values in it, because `_convert_units` rounds to four decimals and would quantise mm/h into
  0.36 mm/h steps. A rounding rule that scales with the target is GH-2002 (GH-1984)
- `imgw/meteorology` `daily/synop` returns the five columns it read and never declared: the daily
  maximum, minimum and 5 cm minimum temperature, the precipitation total and the snow depth (`TMAX`,
  `TMIN`, `TMNG`, `SMDB`, `PKSN`). No synop station could return any of them (GH-1991)
- `imgw/meteorology` carries IMGW's own status in `quality`, which was null for every value the
  provider returned. "8" and "9" are IMGW's codes; `Z` (*opad zbiorczy*) is reported as 10, since
  `quality` is numeric and IMGW's code is a letter. A blank status is a measurement and stays null
  (GH-1998)
- Six dataset descriptions the docs carried and the model did not, so `discover`, the REST API and
  MCP report them too: `dwd/mosmix` hourly `small` and `large`, the three `dwd/derived` monthly
  `cooling_degreehours_*`, and `imgw/meteorology` monthly `climate`. The three
  `cooling_degreehours_*` are each described by the reference temperature they use rather than by
  the docs page's shared blurb about "13, 16 and 18 degree Celsius", those interfaces reporting a
  dataset at a time
- Documentation for running wetterdienst on a schedule, with ready-made units for systemd timers,
  launchd, cron and `docker run`. A `DynamicUser=yes` service has no writable `$HOME`, so without
  `CacheDirectory=` and `WD_CACHE_DIR` the run fails rather than going uncached, and
  `No data available for given constraints` exits 1 indistinguishably from a real failure (GH-255)
- DWD road: a temperature below -60 °C is marked suspect whatever window was asked for. The stopped
  sensors reporting `-75.00` °C were already caught by the rule marking a sensor held at one value
  for six hours, but only where the request covered six hours to find them in. Germany's record low
  air temperature is -45.9 °C, so the line stands 14 K under it (GH-1917)

### Changed

- **Breaking**: Every export a sink refuses raises `ExportRefusedError` -- a mode it does not do, a
  target already holding data under `if_exists="fail"`, or a format or protocol nothing here writes.
  It replaces a `NotImplementedError`, a `FileExistsError`, two `KeyError`s and pandas' `ValueError`
  in the SQLAlchemy sinks, so callers matching on those have to match on this one instead
- **Breaking**: DWD DMO declares the elements its runs carry, 23 parameters for `icon` and 19 for
  `icon_eu` rather than 122 and 40. The old lists were MOSMIX's, copied in when the provider was
  written, so a request for one of the 99 and 22 that are gone now raises `NoParametersFoundError`
  where it used to return an empty frame. `precipitation_height_last_1h` is added to `icon_eu`,
  which serves it and did not declare it. The model has no lead-time axis, so four of `icon`'s 23
  are carried only by `lead_time="long"` and three only by the default `"short"`; those still answer
  with the empty frame, tracked in GH-1976. Three served elements stay undeclared: no canonical
  parameter describes a net radiation flux, and `radiation_global_last_3h` is taken by one, which
  GH-1977 carries
- **Breaking**: `DwdDmoRequest.available_issues` takes the product it is answering for -- `dataset`,
  `station_group` and `lead_time`, keyword-only. It used to list `icon/single_stations/` whatever
  the request would read, and named issues that request then rejected. `wetterdienst issues` and
  `/api/issues` take `--dataset`/`--lead_time` to match. `dataset` and `station_group` default to
  `DwdDmoRequest`'s own; `lead_time` defaults to `None`, which lists every lead time together, so
  with no arguments this still answers more than a default request accepts -- GH-2009 (GH-1956)
- **Breaking**: `Settings.auth` holds `SecretStr` rather than `str`, so reading a credential back
  has to ask for it: `reveal(settings.auth.aemet)`, or `.get_secret_value()`. Setting them is
  unchanged, as is every `if not settings.auth.x` check. An f-string or `str()` of a credential now
  yields `**********`, and the mask is refused as a credential on the way in
- **Breaking**: `filter_by_name` refuses a name that is not a string before it downloads anything.
  The same `TypeError` came out of rapidfuzz before, one whole station index later -- except for
  `None`, which came back as an empty result and now raises like any other non-string. Check the
  name is there before asking, rather than reading an empty result as "no station by that name"
  (GH-2003)
- **Breaking**: The `mcp` extra requires `fastmcp>=4,<5` (was `>=3.4.4,<4.0.0`), and `ui/mcp.py`
  builds the `OpenAPIProvider`'s in-process ASGI client with `httpx2` (`>=2.12,<3`, now declared
  alongside the extra) rather than `httpx`, which FastMCP 4 has moved off entirely
- Locked dependencies refreshed to their latest compatible versions -- 74 packages, among them cloup
  4, fastmcp 4 (mcp 2), plotly 7 and tzfpy 2 -- which widened `cloup<5` and `tzfpy<3`. Plotly 7
  leads an HTML export with a doctype where 6.x began at `<html>`, the only change visible in output
- `DwdRadarValues.period` is annotated `Period | None`, which is what it has always held. The
  annotation claimed `Period` and carried a `ty: ignore`, which made both `not self.period` guards
  in the radar API read as dead code to the type checker

### Fixed

- **Breaking**: `dwd/road` declares the units BUFR publishes its precipitation intensity and water
  film in, so both are converted instead of being served 3600 and 100 times too small.
  `intensityOfPrecipitation` is `kg m-2 s-1`, millimetres per second, and was declared
  `millimeter_per_hour`, so a shower came back as 0.0056 mm/h; `waterFilmThickness` is metres and
  was declared `centimeter`. A request now answers 20.16 mm/h and 0.2 cm. The page's warning to
  multiply by 3600 by hand is gone with it -- do not apply that factor to a value from this version
  (GH-1984)
- **Breaking**: `imgw/meteorology` returns no value where IMGW records no measurement, rather than a
  zero. Each of the 61 declared value columns is followed by a status column and none was read,
  while the value cell of a missing measurement holds a literal `.0` -- so PSZCZYNA reported 0 %
  relative humidity for January 2010 and WARSZOWICE 0 cm of snow cover every day of it. Only status
  `8` becomes null. Under the default `ts_drop_nulls` a frame can come back shorter, or a parameter
  empty where it used to read zero throughout (GH-1994)
- **Breaking**: `imgw/meteorology` returns a documented *brak zjawiska* as the zero it means, where
  it returned no value at all. Status "9" was handled by passing the value cell through, which only
  works where the cell holds a zero, and the files disagree that it does: `o_d_07_2024` leaves it
  empty beside all 8,490 of its "9"s. WARSZOWICE on 2024-07-02 answered null and now answers 0.0 mm;
  `daily/synop` lost whole parameters that way rather than single days (GH-1997)
- **Breaking**: `imgw/meteorology` returns three parameters that were permanently empty and one that
  published a different column's numbers, and `monthly/climate/precipitation_height_max` answers to
  a different original name. Two rename targets carried a typo -- `opadóww` a doubled `w` and
  `minimalnaj` a stray `j` -- and `daily/precipitation/precipitation_height` carried
  `daily/climate`'s mean-temperature name for what upstream calls `SMDB` -- the one measurement that
  dataset exists to publish. `monthly/precipitation/precipitation_height_max` was worse for never
  looking empty: it read `o_m` field 7, the count of days with snowfall, and published that count as
  millimetres. A request for `monthly/climate/opad maksymalny` now raises `NoParametersFoundError`;
  the canonical name is unaffected (GH-1981)
- **Breaking**: `imgw/meteorology` declares `daily/climate`'s grass temperature as
  `temperature_air_min_0_05m`, the name its monthly siblings already use for the same measurement,
  rather than `temperature_air_mean_0_05m` -- `k_d_format.txt` names field 12 a daily minimum, and
  every other provider declaring the mean means a genuine 5 cm mean by it. A request for the old
  name raises `NoParametersFoundError` and names the new one in its hint (GH-1993)
- **Breaking**: A DuckDB `if_exists="append"` matches columns by name. `INSERT INTO t SELECT *`
  matches by position, so two frames with the same number of columns under different names were both
  accepted and the second one's values landed under the first one's headings -- a `--shape=wide`
  schedule that changed one parameter put a precipitation value into `temperature_air_mean_2m`, exit
  0 and nothing said. A frame whose columns are a subset of the table's is still accepted
- `ts_unit_targets` applies all of a mapping or none of it. `update_targets` validated and assigned
  entry by entry, so a mapping carrying one entry it could not use applied those written before it
  and then raised (GH-1984)
- `wsv/pegel` returns no data for a timeseries between measurements rather than raising
  `ColumnNotFoundError`. Pegelonline answers `[]` with HTTP 200 for a series it lists but holds no
  current measurements for, which `pl.read_json` reads as a frame with no columns (GH-1987)
- The InfluxDB sink takes `if_exists="append"`, which is the one word for what it does: every write
  is points, and a point repeating another's timestamp and tags replaces it. Refusing that spelling
  made a multi-station export impossible, `to_target` writing every station after the first with
  `append` -- the three export examples in the docs had been broken since `if_exists` was added
- DWD mosmix: a `kml/` directory that exists and holds nothing is answered rather than raising past
  the line written for it. `next` raises `StopIteration` where its filter matches nothing and the
  `except IndexError` never caught it, so a caller saw
  `RuntimeError: generator raised StopIteration` naming neither the directory nor what was looked
  for. A run is read as the ten digits DWD stamps a `.kmz` with rather than as the third
  `_`-separated part of the name: MOSMIX-L all-stations carries no station id, so that part was
  `2026092203.kmz` with the extension still on it and every row met
  `conversion from str to datetime failed` -- that layout could not be asked for a run at all.
  `available_issues` answers such a directory with no issues, as `dwd/dmo` now does for its own
  (GH-1946)
- DWD dmo: a run is read by its whole name (`_<lead>_<n>_<DDHHMM>.kmz`), where every part of it was
  read by position or by substring and each wrongly. The lead time matched a bare `"78"` anywhere in
  the URL, which 187 of 5811 station ids also satisfy, so ~3% of stations raised
  `can only call '.item()' if the Series is of length 1`; the run stamp took four characters off the
  last name part, so a README raised `conversion from str to i64 failed`. `available_issues`
  returned tz-aware datetimes that this compared against a naive column, so `wetterdienst issues`
  printed issues `wetterdienst values` could not accept. An issue is floored to the run before it,
  where `hour % 12` sent 1 through 11 up to 12, and one given in another zone is converted rather
  than relabelled (GH-1948)
- DWD DMO: a station the shared catalogue omits is described from the product's newest run, so it
  can be asked for. 135 of `icon`'s stations and 132 of `icon_eu`'s are absent from
  `dmo_stationsliste_txt.asc` -- `Y0353` is Mont Blanc -- and were filtered out of every request
  although their forecasts publish and fetch with HTTP 200. Both products now advertise exactly what
  they publish, 5757 and 3688. The added stations report `icao_id` as null (GH-1964)
- **Breaking**: DWD DMO: a station is advertised only for the product that forecasts for it. The
  shared catalogue matches neither product, so a request for `icon_eu` listed 2255 stations that
  could only ever answer with an empty frame. Coverage is read from the product's `single_stations/`
  directory, one listing rather than a 20 MB parse; a listing that cannot be read keeps the
  catalogue (GH-1964)
- DWD DMO: a station position is read as the degrees and minutes the catalogue writes it in
  (`{degrees}.{minutes:2d}`), and the seven hardcoded station patches are gone. Read as plain
  decimals, `.5` became 0°50' -- a station 84 km from where DWD says it is, and nothing raised --
  while `.-6` raised `conversion from str to f64 failed` naming neither column nor station. Of the
  file's 11 622 position fields, 21 needed repairing and all 21 now land on the coordinate DWD's own
  placemarks carry. `P0563` (London Luton) is beyond reach, written `.22` where the sign is missing
  rather than misplaced
- DWD DMO: a run stamp becomes the hour it names whatever that hour is. `DDHHMM` had its day, month
  and minute padded back to two digits before parsing but not its hour, so `3` made `...01300` and
  `%H` took the `30` it could see. DMO publishes at `00` and `12`, so no run has hit this
- DWD DMO: both dataset descriptions were MOSMIX's, word for word -- `icon` described as MOSMIX-L's
  "115 parameters for worldwide stations", `icon_eu` as MOSMIX-S's 40-parameter one, and neither
  count is DMO's. Neither description names a parameter count any more, and `icon_eu` names the set
  it is published for rather than "European": 11 of its 3688 stations sit east of 35° longitude
- DWD mosmix: `LATEST` reads the newest run the listing names rather than the alias beside it, and a
  named run is held for twelve hours instead of five minutes. The two are the same bytes -- one
  ETag, one content-length -- but a run named by its timestamp is that run for good, where the alias
  is a name DWD replaces hourly. MOSMIX-S, 36 MB published hourly, was refetched up to twelve times
  an hour: 10.4 GB a day over the wire against 871 MB now, at the cost of one blob an hour where it
  reused one -- reclaimed by the TTL sweep below, a named run being held under a positive one
  (GH-1945)
- DWD mosmix: a station whose directory DWD has emptied or retired costs that station and no more.
  `get_url_for_date` raised on a listing that named nothing and nothing between it and
  `values.all()` catches, so one such station ended a request for fifty. It answers `None` now, the
  split `dwd/dmo` has always made. A cached body that is not a zip is dropped and asked for once
  more, since fsspec records a cache entry before the copy that fills it finishes (GH-1949)
- DWD swsmos: the run is read once for the request rather than once for every station it answers
  for. One run file holds every road station's whole forecast -- 306 612 rows -- and was listed,
  fetched and parsed once per station with all but one station's rows thrown away. Twenty-five
  stations took 14.1 s and now take 0.8 s. The run is pinned for the length of a query and no
  longer, so a caller querying again on a timer is answered with the run published since (GH-1922)
- DWD swsmos: `LATEST` no longer answers with a run up to twelve hours old. The alias is a name
  whose content DWD replaces hourly and was cached by URL for twelve hours like everything else, so
  "the latest run" could be one whose first twelve forecast hours had already happened -- measured
  at 22:57 UTC, the alias answered from the 21:00 run while DWD served 22:00 (GH-1922)
- DWD swsmos: a run that cannot be read is reported and skipped, where it used to end the request in
  a traceback out of `bz2.decompress` and repeat it for the twelve hours it stays cached. `LATEST`
  falls back to the run before the newest, an hour-old forecast being what it should mean while a
  run is still being written. A run is matched exactly (`swsmos_<14 digits>_opendata.csv.bz2`),
  since a `swsmos_` prefix also matches a checksum sidecar that sorts after the run it belongs to,
  and a zero-byte 200 no longer parses to a run that simply holds nothing. The body is asked for
  once more past the cache before the fallback, and only once where the caller disabled the cache,
  which `cache_disable` can now say (GH-1922)
- Network: the cache says what it did, where it used to decide on a caller's behalf and keep quiet.
  `cache_dir`, `cache_disable` and `use_certifi` decided what `NetworkFilesystemManager.register`
  built and were not part of the key it was filed under, and `register` runs only for a new key --
  so the first caller in a thread decided for every later one, and a request made with caching
  disabled could be served by a caching filesystem. A listing that could not be read is no longer
  answered as an empty directory either: `fs.find` walks with `on_error="omit"` and aiohttp's
  `ClientOSError` is an `OSError`, so a connection reset was swallowed inside fsspec. A directory
  that is not there stays `[]`, as does being offline (GH-1947)
- Network cache: the on-disk blob directory is separated by the TTL and by the headers that can
  change what a server sends back, and by nothing else. Named for a hash of the whole of
  `client_kwargs`, it moved whenever the default User-Agent's version number did -- one developer
  machine held 129 directories and 4.3 GB, of which 115 MB was reachable by the installed version
  and 1.4 GB sat under `ttl-INFINITE-*`, a provider saying those bytes never change. Directories of
  the older layout are reclaimed on the first cached download of a process, and one a rotated
  credential named ages out at a month (GH-1959)
- Network cache: a blob its own TTL has already made useless is dropped, once per directory per
  process. A TTL that is not a positive number is not swept at all, because `CacheExpiry.INFINITE`
  is `False` and fsspec reads an expiry of zero as "every entry is expired" -- it would have thrown
  away the immutable archives `lhmt` and both `meteofrance` providers keep there. The lock is held
  across the sweep, which is what keeps a `download_files` thread pool from writing rows the sweep's
  own snapshot would then drop and orphan (GH-1955)
- Network: two credentials never share a cache directory or a filesystem, whatever shape their
  headers arrive in. `str()` of a `SecretStr` is `**********`, so every secret hashed to one value
  and the second caller was handed the first caller's filesystem, built with the first caller's
  `Authorization` header; `client_kwargs["headers"]` reaches aiohttp as a mapping or as a sequence
  of pairs and only the mapping was read. The cache also separates on every header but the ones that
  cannot change a body, rather than on a list of those known to carry credentials --
  `Accept-Language: de` and `en` shared a directory. An unknown header now costs a cache miss
- met.no Frost: the credential probe builds its own headers rather than writing into the dict
  `Settings` holds. `{**settings.fsspec_client_kwargs}` copies one level, so
  `setdefault("headers", {})[...] = ...` mutated the shared mapping and every later request from
  that `Settings` -- any provider, not only this one -- carried met.no's basic auth
- Network: the log says whether a file was downloaded or read from the cache, rather than saying
  "Downloading file" for both -- and it was wrong for every cache hit, the one thing a reader could
  already tell was not happening. `download_files` says what it is fetching up front and then how
  many arrived and how many the cache answered, `uncached` where there is no cache to report on
- A token exchange that meets a server error is asked a second time. `post_file` retried a
  connection that never carried a response but took every response that did arrive as an answer, and
  a 502 from a token endpoint is a blip. A mint is made once every three days and empties a whole
  Met Office query when it fails. A 401 is still an answer, and so is a 429 deliberately:
  `download_file` no longer retries every failing status, so a 429 from AEMET or met.no Frost is not
  answered by doubling the request rate against a provider that has just said it is rate-limiting. A
  404 and a 5xx are still asked twice, a file index being read minutes before the files it names
  (GH-1939)
- Met Office works on a plain `pip install wetterdienst`. Its CEDA token exchange imported `httpx`
  at module level, which only the `restapi` extra declared, so
  `Wetterdienst("metoffice", "observation")` raised on an installation that had not asked for the
  REST API. The exchange goes through fsspec now, by way of a new `post_file` in `util/network.py`,
  and `httpx` is no longer a dependency of wetterdienst at all. A redirect is not followed, since
  aiohttp would repeat a redirected POST as a GET and turn CEDA's login page into a 200 whose body
  parses as nothing (GH-1929)
- A provider that cannot be loaded says which package it is missing. `importlib` raises
  `ModuleNotFoundError` for an absent dependency as readily as for an absent module, and
  `Wetterdienst.resolve` rewrote both into `Module wetterdienst.provider.X not found`. Where an
  extra of this package would install it the message says which, read out of the installed metadata
  rather than from a list kept in the code (GH-1929)
- The three paths that do not go through the provider registry say which extra they want, where they
  used to raise a bare `ModuleNotFoundError`: `wetterdienst restapi` without `[restapi]`,
  `.interpolate()` without `[interpolation]`, and the radar HDF5 dump without `[radar]` (GH-1938)
- The MCP server tells a client which wetterdienst it is talking to. `FastMCP(version=...)` was
  never set, and left unset it reports the installed FastMCP release as the server's own version --
  so a client asking what it had connected to was answered "Wetterdienst 4.0.3"
- Examples: the DuckDB dump addresses its database file with three slashes rather than four, so it
  opens on Windows, where the leftover slash left DuckDB reading `//C:\...` as a UNC share. The same
  count was wrong in `to_target`'s docstring and the PyConDE notebook, which showed
  `duckdb://name.duckdb` -- read as a host rather than a path, so the data went to an extensionless
  file named `dwd` in the working directory with no error
- Three documented parameters that no request could ask for, and four requestable ones no page
  documented. `dwd/mosmix` hourly documented `cloud_base_convective` and `cloud_cover_below_7km`
  under `small`, which the model declares for `large` alone, and carried a stale `n1` row for
  `cloud_cover_below_1000ft` that the model has never mapped; `imgw/meteorology` monthly `synop`
  documented none of its four precipitation parameters at all
- Three unit cells disagreeing with the model about the quantity rather than the notation:
  `dwd/road` 15_minutes wrote `mm/s` where the model declared `millimeter_per_hour` -- there the
  page was right and the model wrong, which GH-1984 settles in this release -- and `dwd/observation`
  monthly and annual wrote `Bft` for `wind_gust_max`, which the model declares `meter_per_second`,
  copied from the `wind_force_beaufort` row above it
- The stale MOSMIX and DMO figures the docs carried: MOSMIX-L at "~115 parameters" and both products
  at "over 5000 stations worldwide" in two files beside the `docs/data/overview.md` being corrected
  in the same change, and a fourth copy of the 115 in `dwd/mosmix` hourly's own dataset description.
  Measured: MOSMIX 5649 stations, 40 parameters for `small` and 122 for `large`; DMO 5757 stations
  and 23 parameters for `icon`, 3688 and 19 for `icon_eu`
- `imgw/meteorology`'s page states what its status column does not settle. A `0` in
  `monthly/climate`'s `snow_depth_max` carrying no status means either no snow cover in the month or
  a maximum that could not be determined -- 96 of the 196 rows of 2024, returned as 0 cm -- and
  `daily/precipitation` omits a *brak zjawiska* day rather than returning 0 mm for it. The page had
  said a parameter a station does not measure "comes back with no values" (GH-1997, GH-1998)
- `imgw/hydrology` monthly is described as "historical monthly hydrology data", not "historical
  daily climate data" -- wrong in both the resolution and the subject, and wrong in the model and
  the page alike. A caller asking `discover`, the REST API or MCP for `monthly/hydrology` was told
  it holds daily climate data
- The three `dwd/derived` *Kuehltage* overrides are described as "Number of days with at least one
  cooling hour", which is what DWD counts, rather than "Number of days on which cooling was
  required". The canonical `count_days_cooling_degree` keeps the general wording, as its
  `count_days_heating_degree` sibling does

### Security

- Provider credentials are held as `SecretStr`, so that rendering the settings does not print them.
  `Settings.__repr__` serialises the whole model, `auth` included, and a request's dataclass repr
  embeds a `Settings` -- so an API key reached every ordinary way of looking at an object on a
  failure path: a pytest assertion diff, a traceback, `print(request)`, a debugger, a notebook.
  Anyone pasting such a traceback into an issue or a CI log published every credential they had
  configured. All four -- AEMET, KNMI, met.no Frost and CEDA -- now render as `**********`, and
  `reveal()` is the one way back to a value (GH-1920)
- A credential no longer travels in the error a failed download hands back. aiohttp hangs the
  request's headers on a `ClientResponseError` and on its `args`, so an `Authorization` header
  reached anything that rendered the `File` the download returned. It travelled three further ways:
  the traceback's frames in `util/network.py` hold the caller's client kwargs as locals, which
  `pytest --showlocals` prints; `ClientResponseError.history` holds a copy per redirect; and
  `stamina`'s retry hook logs a `repr` of what failed. None of the four shows in `str(error)`. The
  header is redacted, the history and traceback dropped, and the error scrubbed on its way into the
  retry as well as out of it
- A failed request that carried its credential in a header of another name has that header redacted
  too. The scrubbing knew `Authorization`, where KNMI's key, met.no Frost's basic auth and Met
  Office's bearer token go, but AEMET sends its key as `api_key`
- `httpx2` now has a floor of `>=2.12` wherever it is declared -- the dev group, which held
  `>=2.4.0`, and the `mcp` extra, which now declares it -- and the lockfile carries 2.13.0 where it
  held 2.10.0. Six advisories stand against 2.10.0, three distinct defects: multipart part header
  injection through an unvalidated file `Content-Type` (CVE-2026-84379, fixed in 2.11.0),
  conflicting `Content-Length` and `Transfer-Encoding` headers generated together (CVE-2026-84380,
  2.11.0), and unbounded peak memory decompressing a streamed response (CVE-2026-84382, 2.12.0).
  `uv audit` has failed on `main` since 2026-09-16 on exactly these, and passes again

## [0.137.0] - 2026-09-18

### Added

- Interpolation and summary take an `elevation` for the point they answer for, in metres above sea
  level, and bring each station's readings to it before using them. Air temperature falls about 0.65
  K per 100 m, so the stations within 40 km of Garmisch span 630 m to 2956 m -- 15 K interpolated as
  though it were horizontal structure. Named `elevation` on the API and the REST API, `--elevation`
  on the CLI, and it names the point too, so two elevations at one place no longer share a station
  id. A station whose height the provider does not report is left out of such an answer; where that
  leaves a parameter with no station at all, `NoStationsWithHeightError` names it and how to ask for
  the readings uncorrected (400 on the REST API)
- Parameter table: `lapse_rate` says how fast a quantity falls with height, in its own unit per
  metre, for the 17 air temperatures measured at 2 m and the dew point. Not for the 5 and 10 cm
  readings, which are governed by the ground beneath them, nor for anything in or on the ground, nor
  for the comfort indices, nor for pressure, which wants the barometric formula rather than a rate
- Export: `file://` targets for `.json`, `.jsonl` and `.nc`. JSON could not be written to a file at
  all; it holds the frame's records rather than the `{"metadata": ..., "values": [...]}` envelope a
  response carries. NetCDF joins Zarr as the second array format, written through xarray with CF
  time units and gaps as NaN rather than the -999 Zarr fills them with. The `export` extra carries
  `h5netcdf`, which needs no compiled netCDF library
- DWD road: the `quality` column carries the station's own verdict on its sensors, where it was null
  on every road reading. `qualityInformationAwsData` (BUFR `0 33 005`) is a 30-bit flag naming which
  quantities the station calls suspect, and it was read and thrown away. A reading is `1` where the
  station checked it and calls it suspect, `0` where it checked and does not, and null where nothing
  is known -- the common case, 817 of 1199 station-minutes reporting no checks performed.
  `road_surface_condition` and `water_film_thickness` stay null, the WMO's generic table naming no
  state of a road. `quality` carries whatever a source publishes and the scale differs by provider,
  which the column's description now says rather than promising one meaning (GH-1917)
- DWD road: a sensor that has stopped is marked suspect. Where an air temperature, dew point or road
  surface temperature reports the identical value for 24 readings -- six hours here -- `quality`
  becomes `1` and the reading is left exactly as DWD published it. Measured rather than chosen: over
  a day of ~700 stations per quantity a working sensor's longest run was 9 to 17 readings, a broken
  one 86 to 96 of 96. Only those three quantities, since a dry day's surface condition and water
  film legitimately sit at 0 all day. A road at its melting point is exempt where the station's own
  air came near freezing, salted roads holding a constant sub-zero value by the same physics
  (GH-1917)

### Changed

- DWD road: the precipitation type is reported as `precipitation_type_flags` rather than
  `precipitation_form`, being a different kind of number. `precipitationType` is BUFR `0 20 021`, a
  30-bit flag table with a bit per type, where `precipitation_form` elsewhere holds a single code --
  so rain came back as `33554432` against DWD observation's `6` for the same weather, under one
  canonical name. The value is unchanged. The bit layout and how to mask for a type are on the
  provider's docs page (GH-1916)
- Interpolation and summary by station id answer at that station's altitude, it being the one case
  where the elevation is known without being given. **This changes what `interpolate_by_station_id`
  and `summarize_by_station_id` return** where the stations drawn on stand at other altitudes -- for
  the reading uncorrected, pass the station's coordinates to `interpolate` or `summarize` instead
- Dependencies: the `bufr` extra is the whole of what reading BUFR takes. pdbufr requires eccodes
  but asks for any version, and the two were named as separate extras with the docs telling you to
  install both, neither being any use without the other. `pybufrkit` is no longer pulled in by
  `bufr`: nothing in the library imports it, only the radar tests do, and they skip on it now
- Dependencies: shapely is required from 2.0.6 rather than 2.0.4. The two releases before it raise
  out of `create_collection` under numpy 2, which is what every other dependency here resolves to
- REST API: `/api/summarize` answers a window that ends before it starts with a 400 rather than a
  404, as `/api/interpolate` already did. Both endpoints decide that from one place now

### Fixed

- Unit conversion: the mile and the knot are derived from the metres they are defined as, rather
  than from decimals rounded to four figures. `1.944` left knots to metres per second 0.0080% from
  its km/h route, so the same quantity converted differently depending on which unit its source
  published -- the Met Office publishes wind in knots and the speed target is m/s, so every one of
  its wind speeds carried the error. A round trip hid all three, both directions sharing the
  rounding
- Interpolation: four stations that surround the target point are a valid group however they are
  ordered. The check drew a polygon through them in the order they are held -- by distance from the
  point, which says nothing about the order around it -- so roughly half of all groups described a
  self-intersecting shape, where `covers` is undefined: 11676 of the 37415 groups that do surround
  the point the tests use were rejected. The convex hull decides now, which is also the region
  `LinearNDInterpolator` can answer for. No interpolated value in the test suite changes
- Interpolation: stations that do not span a triangle are no group, and four on a line come back
  without a value rather than raising scipy's `QhullError`. A hull with no width still covers a
  point lying on it, so such a set counted as valid -- which is what stops the collection of further
  stations, so a set that cannot be interpolated at all could end a search that would have found one
  that can
- Interpolation: a point the interpolation has no answer for comes back empty rather than as a zero.
  `LinearNDInterpolator` answers NaN outside the stations it was given, and for the quantities
  carrying an occurrence test -- precipitation, new snow -- `NaN >= 0.5` is False, so the NaN was
  reported as a precipitation of exactly none
- Interpolation: whether four stations surrounding the point exist is answered from the hull of all
  of them rather than by enumerating groups, which costs C(N,4) hulls -- 91390 for the 40 stations a
  wide radius reaches, seconds per station against 0.2 ms
- DWD road: a station with two road sensors is read as having two, and a reading is one sensor's.
  The sensors are a delayed replication inside the station's subset, so the rank on the key names
  the sensor where `positionOfRoadSensors` reads 0 or missing in all 1199 subsets measured. Only
  what is inside that replication can arrive twice -- 3 of the dataset's 14 parameters -- so a row
  can never hold one sensor's air temperature beside another's road surface. Of 75 stations whose
  sensors both reported a surface temperature the median disagreement was 0.3 K. Everything
  contested is taken from the one sensor reporting most of it, and what is dropped is logged at
  debug (GH-1908)
- DWD road: a station's reading is kept whole where it arrives in parts. `read_bufr` emits an
  observation only where every column asked for is present, so asking for all fourteen parameters
  threw away every reading of anything not universally fitted -- against one file of the DD group
  the parse returned 105 values where the file held 121, the whole of `roadSurfaceTemperature` among
  the missing, on a road weather network. The file is read flat instead, one row per station and
  minute, and a parameter no subset carries comes back as a null column
- DWD road: a station group is read once for a request rather than once per station of it. A road
  file holds a whole group where the collection above asks one station at a time, so every file was
  decoded once per station and all but that station's rows thrown away: three stations of one group
  over two hours parsed nine files twenty-seven times, and now nine (GH-1922)
- DWD road: a subset that names no station or no minute is one reading lost rather than a file. One
  null minute made the whole of pandas' column a float, where 2026 written as "2026.0" took the
  timestamp of every station in the file with it
- DWD road: a listing entry is a file when it carries the timestamp the file index reads it by, and
  two entries never do -- the directory of a group that holds nothing, which made the listing
  non-empty so `No files found` never said so, and the `LATEST` alias duplicating each family's
  newest file, which a request without dates parsed twice. A name that is neither is reported, so a
  group publishing under two families cannot lose half its readings to a rename
- DWD road: having nothing to answer with is one shape. There were three -- no columns where the
  group published no file, five where its files held nothing, and the seven a reading has -- so the
  collection walk raised
  `ColumnNotFoundError: unable to find column "station_id"; valid columns: []` from its middle. A
  frame of no readings now carries the columns a reading does. The empty files of GH-1526 were
  turned away by their exact length, which is a guess at a shape rather than a reading of one, so
  one holding no subsets at another length reached the parse and raised `KeyError: 'year'`. This is
  what failed `test_pdbufr_examples` on every CI job
- REST API: a BUFR reader missing on the server answers 501 rather than 400. The blanket handler
  read every failure as the caller's, so a deployment installed without the `bufr` extra told the
  client to `pip install wetterdienst[bufr]` on a machine they do not administer, and `interpolate`
  and `summarize` called the same thing a 404. The install line moves to the server log
- CLI: a missing optional reader is reported rather than raised. `values`, `interpolate` and
  `summarize` caught `ValueError`, and the `ImportError` naming the extra is not one, so the
  sentence saying what to do arrived as the last line of a traceback. The refusal has a type of its
  own, `BufrReaderMissingError`, so a cycle or a typo inside a provider module keeps its traceback
- DWD road: a missing BUFR reader is refused at the request rather than at the parse. The values
  class called `ensure_pdbufr()` and threw the answer away, so the request went through and a bare
  `ImportError` came back out of the middle of a parse
- BUFR: asking whether this environment can read BUFR answers, whatever the import does. Each probe
  had a hole: `ensure_eccodes` did not catch the plain `ImportError` an eccodes with no compiled
  library raises, and `ensure_pdbufr` re-raised a `RuntimeError` matched on gribapi's phrasing of
  the day. A reader that is installed and does not work says why,
  `No module named 'gribapi.bindings'` being a broken install rather than an absent one
- Export: a file target renders what the matching format returns. `to_csv` joined a list of station
  ids into one field and the CSV file target did not, so `--target=file://out.csv` on an
  interpolation died with `CSV format does not support nested data` where `--format=csv` wrote the
  same data out fine. Zarr failed on the same column
- Export: station metadata can be filtered by SQL and written to Zarr, NetCDF or CrateDB. All three
  named the `date` column a values frame has, while a stations frame carries `start_date` and
  `end_date`, so `request.all().filter_by_sql(...)` raised `ColumnNotFoundError`. The CLI's `--sql`
  went through a second copy of the filter that worked but called whatever came back UTC; both run
  the one filter now
- CLI: an empty window is reported once, where `get_values` logged "No data available for given
  constraints" and the CLI logged the identical line again before exiting

## [0.136.0] - 2026-09-04

### Added

- DWD: new `poi` network (`dwd/poi`) covering DWD's POI current weather reports -- the hourly
  observations of roughly the last day, one `<station_id>-BEOB.csv` per station. 39 parameters at
  `hourly` resolution and the `now` period. This is the observed counterpart to `dwd/mosmix`: the
  two share the MOSMIX station catalogue, so a station keeps one id across both and a forecast can
  be compared against what was measured. About 970 of the catalogue's ~5600 stations report. The
  file's two 24-hour radiation columns are left unmapped, both declared W/m2, which a 24-hour figure
  cannot be -- sum the hourly column for a daily total

### Changed

- Periods: `periods` is an argument of every request rather than of the three that hand-rolled it,
  and is resolved against the periods the requested datasets declare. A dataset published under a
  single period is answered for that period and raises `NoPeriodsFoundError` for another. Left out,
  the periods are still derived from `start_date`/`end_date` where the provider has a release
  schedule (DWD observation and phenology) and are otherwise every period the requested datasets
  publish, which for a request naming one dataset is narrower than the provider-wide set it used to
  be. `TimeseriesRequest.available_periods()` replaces the per-provider `_available_periods`
- Parameter parsing: a parameter the provider does not have is logged as a warning naming what did
  not match -- resolution, dataset or parameter -- with the closest name as a "did you mean", where
  it used to be an `info` line saying only that it was not found. Half a request silently resolving
  to less data than was asked for is otherwise invisible
- Provider metadata: `MetadataModel` carries the name it was built with as a `name` field. Read
  `DwdObservationMetadata.name` rather than `DwdObservationMetadata.__name__`
- Lookups on the metadata models (`metadata["daily"]["kl"]`, `metadata.daily.kl`) match the source's
  own name case-insensitively, as looking one up by `name_original` in a request already did, and
  suggest the closest name when nothing matches
- Parameter parsing: the parts of a parameter must be strings. A tuple mixing in an enum member,
  `(Resolution.DAILY, "kl")`, raises a `TypeError` naming the accepted forms rather than an
  `AttributeError` from deep inside the parser
- Periods: narrowing the periods of a provider that does not read its data per period -- SMHI,
  MeteoSwiss, met.no Frost and Meteo-France observation fetch all of them by design -- is logged as
  a warning saying the request was not narrowed, rather than answered with everything in silence

### Fixed

- Dates: a date string covers everything it names instead of only the instant it starts with.
  `2020-05` is the month of May, `2020` the year, and `2020-05-01` a whole day. Every one of these
  formats is documented as supported, and `filter_by_date` matched a single date with `==`, so a
  month or a year of hourly data came back empty -- no reading falls exactly on the 1st at 00:00. An
  interval ran to the *first* instant of the span its second half names, so `2017-01/2019-12` ended
  on the 1st of December and `2010/2020` dropped all of 2020. The CLI and REST API read the string
  the same way. A date carrying a time still names one instant
- Periods: a period no requested dataset publishes is no longer silently turned into *every* period.
  `periods="future"` intersected the request with the available periods and the empty result read as
  "no periods requested", so asking for a period that does not exist returned more data than asking
  for one that does. It raises `NoPeriodsFoundError` now
- Periods: `periods` reaches providers that never accepted the argument. It was a per-provider
  constructor field, so `NoaaGhcnRequest(..., periods="historical")` was a `TypeError` and the CLI's
  `--periods` was dropped for every provider but DWD observation, derived and phenology -- including
  met.no Frost, whose datasets are published under both `historical` and `recent`
- Periods: a period derived from `start_date`/`end_date` is checked against the datasets like a
  requested one. An interval reaching into today derives `now`, which `daily/kl` has no release for,
  and the request then read no station index at all -- reporting *no stations* where asking for
  `periods="now"` outright raises. Where the interval reaches past a dataset's newest release, that
  release answers for it
- Periods: an explicit period is answered for a dataset published under a single one. The CLI and
  REST API forwarded `periods` only where some requested dataset had more than one, so asking DWD
  derived for `historical` on a `recent`-only dataset read every period the provider has
- Interpolation and summarization: the values of one station are no longer read together with
  another station's coordinates and distance. Both walks paired the distance-sorted stations frame
  against the values generator by position, but that frame carries a row per station *and* dataset
  while the generator yields one result per station and skips those that returned nothing, so any
  gap shifted every station after it onto its neighbour's location
- Interpolation and summarization: a result with no rows is a feature collection with no values
  rather than an `OutOfBoundsError`. The feature's id was read out of the frame's first row, so a
  point and window no station covers raised `gather indices are out of bounds` from `to_geojson`,
  where `to_dict` on the same result answered fine. The id belongs to the point
- Values: a request that collected nothing returns an empty frame carrying its columns rather than
  one with no columns at all, which wrote an empty file where a header was meant and raised
  `ColumnNotFoundError` from `get_column("date")`. Having no data for the constraints given is an
  ordinary outcome, so it is no longer logged with a traceback either
- Ranked station values: a station whose record lies entirely outside the requested window no longer
  counts against the station count of `filter_by_rank`. It was checked for data before the window
  was cut and never again after, so it spent one of the ranked slots on an empty frame and the walk
  stopped short of the stations that do cover the window -- which reads exactly like no data
  existing at all
- Values: a ranked request no longer reads the whole provider to answer for a window that predates
  it. A station returning nothing inside the window rightly does not count towards `rank`, but then
  nothing bounded the walk either. A station the index says began after the window ended is skipped
  without being downloaded; only that direction is read from the index, a station still reporting
  carrying an `end_date` a little behind what it can answer for
- Values: a dataset named more than once in a request -- interleaved with another -- is fetched and
  parsed once instead of once per run of consecutive mentions. The station index of NOAA GHCN,
  Geosphere and MeteoSwiss gained a duplicate row per station the same way
- Plots: a parameter is labelled with the unit its values are actually written in. The label mapping
  was keyed on the canonical name alone while a frame carries `name_original` unless `ts_humanize`
  is on, so nothing matched and the label repeated the name -- `sd_10 (sd_10)`. The symbol was also
  always the target unit's, though `ts_convert_units=False` leaves the values as published:
  `10_minutes/solar/sunshine_duration` comes in hours and was labelled seconds. Keyed by resolution
  and dataset as well as name now, a canonical name being unique only within its dataset
- Parameter parsing: a quality flag requested by name (`daily/kl/quality_wind`) says that quality
  flags come back in the `quality` column next to their parameter, where it used to be dropped as if
  it did not exist. Requesting one as a `ParameterModel` was dropped the same way
- Parameter parsing: parameters requested more than once -- a dataset and one of its parameters, or
  the same dataset twice -- are returned once rather than per mention, and an iterator of parameters
  no longer parses as empty, having been consumed by the checks that tell `("daily", "kl")` apart
  from a list
- Provider metadata: a misspelled key in a metadata declaration is rejected instead of dropped. Only
  `ParameterModel` forbade extra keys, so `date_requiered` anywhere else was silently ignored and
  the declaration fell back to a default. An invalid `periods` or `date_required` on a resolution is
  now reported as the validation error it is rather than a bare `KeyError('periods')`
- CI: the Coolify deploy step had failed on every run since 2026-08-17, so no release or nightly
  reached the live deployment. Coolify moved `/api/v1/deploy` from GET to POST and left the GET
  route answering `405`, which `curl --fail` turned into an exit 22 after the images had been pushed

## [0.135.0] - 2026-08-31

### Added

- DWD: new `phenology` network (`dwd/phenology`) covering the DWD phenological observation network
  -- the day of the year on which a plant reached a developmental phase, at `annual` resolution,
  reaching back to 1925. 110 datasets, one per plant and reporter group (`annual_common_hazel`,
  `immediate_winter_wheat`, ...), each carrying that plant's phases as parameters. A value is DWD's
  `Jultag` dated to the 1st of January of the reference year, so the entry date is that date plus
  the value. Both reporter groups are covered, with their own station catalogues

### Removed

- `Resolution.UNDEFINED` and `Period.UNDEFINED`, which no provider declared any more -- the last
  sources without a stated interval went when WSV and Hubeau began reporting theirs.
  `periods="undefined"` now raises `InvalidEnumerationError` where it used to parse and then match
  no dataset, which is the one visible change. `PeriodType` goes with it, as `ResolutionType` did
  before, and so does `Frequency.MINUTE_2`, which named a resolution that never existed

### Fixed

- Environment Agency: 15-minute values arrived empty for every window of the last decade and a half.
  The readings endpoint answers a request naming no window with its default page of 100_000
  readings, oldest first, and reports no truncation; at 15 minutes that page runs out after some 2.8
  years, so the readings of 2008 to 2011 came back whatever was asked for and the post-filter
  dropped all of them. The window is now asked for, and the page raised to what it can hold. Daily
  was never affected, 100_000 daily readings being 274 years, and this also stops a 22 MB download
  per station
- Environment Agency: the whole 15-minute resolution was unreachable, both `discharge` and
  `groundwater_level` raising `KeyError` while building the station listing from a hand-kept map
  that still spelled them `*_instant`. The measure parameter and the period are read off the
  notation the metadata declares -- `flow-i-900` is flow measured every 900 seconds -- so renaming a
  parameter cannot separate the two again
- Environment Agency: a station is listed once rather than once per matching measure. The listing
  carries a row per measure, so a station recording two of the requested parameters came back
  duplicated and `filter_by_rank` spent rank on it twice
- DWD observation: the `climate_urban` URL was pinned to the `recent` directory whatever period was
  requested, so a `now` request for a 10-minute urban dataset was answered with data ending at the
  previous midnight and `historical` could not be read at all. The hourly urban datasets are
  unchanged, DWD publishing a single `recent` directory that already holds the full record
- DWD observation: where two periods reported the same timestamp, which record survived was decided
  by neither of the two things that should decide it -- the periods were read in the iteration order
  of a set, varying between interpreter runs, and the deduplication ran over a frame `how="align"`
  had already reordered by value, so the survivor was the lower reading, or a null where one period
  was missing a measurement the other had. Values now settle on the quality-marked historical record
  and stations on their most current description
- DWD observation: station `history` returned nothing for the 10-minute urban datasets, looking for
  them under a `meta_data` directory only the non-urban high resolutions have, while the urban zips
  carry their `Metadaten_*.txt` files themselves. `describe_fields()` raised an opaque `.item()`
  length error for them, DWD publishing no description PDF at all, and now names what it looked at
- Network: the fsspec listings cache silently never hit for `CacheExpiry.INFINITE`. The expiry
  reaches `FileDirCache` as `False`, which diskcache read as `now + False == now`, so every entry
  was stored already expired and each listing was refetched. Falsy expiries now mean "never expire",
  as the download-side cache has always read them
- Network: a listing whose TTL lapsed between fsspec's `in dircache` probe and the following lookup
  raised a `KeyError` out of `ls()`/`find()`. The dircache is read with a single lookup now, which
  also stops a `detail=False` call from caching a name-only listing that later `detail=True` reads
  would receive
- Network: a disabled listings cache created a cache directory named `False`, `0.0` or `0.01` that
  nothing readable was ever written to. Those are no longer created, and any left by an earlier
  version are swept on the next run, guarded so that a folder still holding valid entries is kept
- Network: a float timeout in `fsspec_client_kwargs` reached aiohttp unwrapped and failed every
  request with `ValueError: timeout parameter cannot be of <class 'float'> type`, only int timeouts
  being wrapped in `ClientTimeout`. `download_file()` also raised
  `AttributeError: 'NoneType' object has no attribute 'get'` where `client_kwargs` was left at its
  `None` default, and `FileDirCache` could not be unpickled, its `__reduce__` passing three
  positional arguments in the wrong order to an `__init__` that takes one
- The app's `Resolution` type restates the backend enum and had drifted both ways: it still offered
  `undefined` and `dynamic`, and had never gained `6_minutes`, which Meteo-France is served under

## [0.134.0] - 2026-08-22

### Added

- The DWD climate indices as four datasets: `annual`/`monthly` `climate_indices` count tropical
  nights and frost, summer, hot and ice days, while `annual`/`monthly` `precipitation_indices` count
  the days reaching precipitation heights of 0.1 to 20 mm and snow depths of 1 and 5 cm. DWD derives
  them from the daily observations of the same stations and publishes them in the familiar CDC
  layout, so they arrive as metadata alone. Twelve canonical parameters are new with them, named for
  the index the literature knows (`count_days_frost`, `count_days_tropical_night`) rather than for
  its threshold, which the description carries
- The two interpolation search radii are settings of their own:
  `ts_geo_station_distance_homogeneous` (40 km, for a quantity that varies slowly across a region)
  and `ts_geo_station_distance_heterogeneous` (20 km, for one that decorrelates within a few tens of
  kilometres). They were module constants, so widening the search for everything meant naming all
  514 parameters individually in `ts_geo_station_distance`, which keeps its role as the
  per-parameter override. On the CLI as `--interpolation_station_distance_homogeneous` and
  `--…_heterogeneous` (`--summary_…` for `summarize`), and on the REST API under the same names
- `wetterdienst summarize` reaches the settings `interpolate` always could:
  `--summary_station_distance` and `--use_nearby_station_distance` had no command options at all, so
  the summary CLI always ran with the defaults

### Changed

- **Breaking**: WSV Pegelonline reports under the interval it actually records at, so its single
  `dynamic` resolution is replaced by `1_minute`, `5_minutes`, `10_minutes`, `15_minutes` and
  `hourly`, and `dynamic/data/...` no longer resolves. Pegelonline publishes an `equidistance` on
  every timeseries in the station listing the provider already downloads. The 77 of 787 stations
  recording different parameters at different intervals appear under each, serving only the
  parameters that belong there -- to find a station's resolution, request the parameter at every
  interval that could carry it and read the `resolution` column of the station list
- **Breaking**: Eaufrance Hubeau reports under the interval each station transmits at, so its single
  `dynamic` resolution is replaced by `5_minutes`, `6_minutes`, `10_minutes`, `15_minutes` and
  `hourly`, and `dynamic/data/...` no longer resolves. Hubeau publishes the interval nowhere, so
  unlike Pegelonline's declared `equidistance` it is measured from the timestamps a station has just
  published: of 3018 stations reporting over six hours, 2987 resolved to one of the five. A station
  that has published nothing to measure, or transmits every 20 or 30 minutes, is listed under no
  resolution rather than a guessed one, and returns as soon as it transmits on a covered interval.
  `Resolution.DYNAMIC` goes with these two, and `ResolutionType` with it
- **Breaking**: the heterogeneous search radius follows the resolution of the request, so an
  interpolation or summary that already worked returns different values without anything being
  changed by hand: daily precipitation is drawn from 40 km rather than 20, `minute_10` from 15 km. A
  quantity that decorrelates fast in space does so less the longer it is accumulated -- gauge
  studies put precipitation's correlation length at roughly 8 km over ten minutes and 33 to 94 km
  over a day. The factors are `ts_geo_station_distance_resolution_factors`: 0.75 for the minute
  resolutions, 1.0 hourly, 1.5 for `6_hour` and `subdaily`, 2.0 from daily upwards. Every factor set
  to 1.0 turns the scaling off; a radius written out per parameter in `ts_geo_station_distance` is
  used exactly as given. The table stops at 2.0 because past a day what binds is terrain, the
  interpolation reading UTM x/y and never station height
- **Breaking**: the `"default"` key of `ts_geo_station_distance` is gone in favour of the two radii
  settings above. It was undocumented and did more than it said: it rebuilt the mapping around the
  given number, so `{"default": 30}` gave precipitation, fresh snow and visibility 30 km as well as
  setting the fallback. Setting it now raises and names its replacements
- **Breaking**: `skip_empty` works through the CLI and the REST API. Neither surface ever set
  `ts_complete`, and `ts_skip_empty` was silently switched off wherever it was not, so
  `--skip_empty`, `--skip_threshold` and `--skip_criteria` did nothing at all and `filter_by_rank`
  never skipped a station over its coverage the way it is documented to. A CLI or REST request that
  passes `--skip_empty` starts skipping stations it used to return
- A station's coverage is the share of the readings the requested window can hold at the parameter's
  resolution that the station delivered, counted from the window and the resolution rather than by
  measuring a frame reindexed onto a grid first. The denominator is the one `ts_complete` produced,
  with two departures: a reading that does not land on the grid counts as delivered rather than
  missing, and a request naming no window is measured against the span of the station's own series.
  `subdaily` is measured on what came back, being a bucket rather than an interval whose two
  providers disagree on the spacing
- An NWS request asks the observations endpoint for its own window. The endpoint answers an
  unqualified request with its whole retention -- a rolling week, close to a megabyte -- however
  little was wanted, and the frame was trimmed only after it arrived

### Removed

- **Breaking**: the `ts_complete` setting is gone. It reindexed a series onto the grid its
  resolution implies, at the cost of a materialized timestamp per reading, a station-local-to-UTC
  window conversion and a three-way interlock with `ts_drop_nulls` and `ts_shape`. The join it built
  was exact, so a station reporting off the grid -- an hourly gauge at seven minutes past, which is
  how a good third of Hubeau's hourly stations report -- came back as a column of nulls. A caller
  who wants the grid can build it in a few lines of polars, where the phase is theirs to choose
- **Breaking**: `MetadataModel.timezone_data` is gone, and with it the `timezone_data` key all 29
  providers declared. It named the zone a provider's own `date` labels are stamped in and
  `ts_complete` was the only thing that read it. `metadata.timezone`, the provider's civil timezone,
  is a different field and remains. Every `date` a request returns is UTC either way

### Fixed

- **Breaking**: `ts_shape="wide"` puts one timestamp of one resolution in a row, and stops filling
  rows with values that belong to another. The row was keyed on the dataset as well while the
  parameters were joined on the date alone, so a request spanning two datasets emitted every
  timestamp once per dataset and filled all of those rows with all of the values -- the two rows
  were identical but for the label. Datasets recorded at one resolution now share a row, with
  `dataset` null where no single name describes it. The parameter joins are also outer rather than
  inner, so a parameter with no reading at a timestamp leaves a null instead of removing the
  timestamp: chained inner joins had reduced the result to the timestamps every requested parameter
  happened to share
- Values of two resolutions are sorted apart in both shapes. The row order was `dataset`,
  `parameter`, `date`, so an hourly and a 10-minute precipitation series came back shuffled into
  each other, one hourly row every six 10-minute ones
- Eaufrance Hubeau lists every station it has rather than the first thousand. The referential
  answers with a page of 1000 of its 4150 stations and a cursor to the rest, and the query named no
  page size and followed no cursor, so three quarters of the French gauges were unreachable --
  including by `filter_by_station_id`, which filters against that list
- Eaufrance Hubeau serves the overseas departments. Metropolitan station codes begin with the letter
  of their hydrographic basin and those of Guadeloupe, Martinique, Guyane, La Réunion and Mayotte
  with a digit, and the list kept only codes beginning with a letter -- excluding all 176 overseas
  gauges, 86 of them transmitting
- The NWS station list holds three American stations it used to leave out -- Barking Sands on Kauai
  and the two US Virgin Islands airports, which MADIS files under a state code rather than a country
  code. They are named one by one, that column not being readable as a state code in general: `PR`
  in it is Peru and `GU` is Guatemala. The list was also narrowed to
  `longitude < 0 and latitude > 0`, which is not where the United States ends -- the Aleutians west
  of Amchitka lie beyond the antimeridian and Pago Pago below the equator -- so that box is gone,
  having decided nationality by hemisphere
- An NWS station of unknown elevation reads as null rather than as standing 9999 m up. MADIS writes
  a missing elevation as 9999 and it was cast to a float and passed on unread, for 31 of 3120
  stations -- and height is what interpolation weighs a neighbouring station by
- An NWS request no longer rewrites the settings every other request shares. It stamped its own
  headers onto `Settings.fsspec_client_kwargs` in `__post_init__`, so a DWD request made after an
  NWS one went out under NWS's headers, naming a version eighty-five releases old
- A Zarr export names its group for what the whole frame holds rather than for whatever its first
  row says. A frame of two datasets was filed under whichever came first, and one merging them would
  have gone to the store root, where `mode="w"` clobbers every other group in it
- `ts_geo_station_distance` validates what it is given: a key that is not a canonical parameter is
  rejected rather than kept and never read, and a negative distance is rejected as it already was
  for `ts_geo_use_nearby_station_distance`. The CLI and REST API report the rejection as a bad
  parameter and a 400 rather than a pydantic traceback
- Settings round-trip through `model_dump()` faithfully: `ts_geo_station_distance` serializes the
  overrides it was given rather than the mapping they were expanded into, which came back as
  explicit per-parameter overrides that then won over a `ts_geo_station_distance_heterogeneous` set
  alongside
- `poe docs` builds the documentation again. It ran `make html` in `docs/`, which holds no Makefile,
  so it had failed with "No rule to make target" for as long as that file has been gone. It runs
  sphinx against `docs/conf.py` now, as Read the Docs does, and `poe docs:clean` removes the build
- Docs: `ts_geo_min_gain_of_value_pairs` is documented with its actual default of 0.1, not 1.2

## [0.133.0] - 2026-08-19

### Added

- Every parameter of every provider carries a description, 1681 of 1681, closing the last 508 gaps,
  and they are reported by `discover()` -- so by `GET /api/coverage`, the `coverage` MCP tool and
  `wetterdienst about coverage`. 388 come from the source itself: MeteoSwiss, met.no Frost, KNMI,
  FMI, AEMET, SMHI, CHMI, Météo-France, the Met Office's CEDA tables and LHMT publish per-field
  metadata, translated here where it is not in English, and DWD's English `DESCRIPTION_*_en.pdf`
  sheets and `MetElementDefinition.xml` cover its own. Those say what a canonical sentence cannot:
  that Météo-France's daily precipitation runs 06h to 06h UTC and is attributed to the earlier day,
  that Met Office pressure is uncorrected for altitude, that CHMI's daily temperature is the mean of
  three fixed observations. The rest are the canonical sentence for the quantity, kept in
  `DERIVED_DESCRIPTIONS` so generated text is never mistaken for a source's own wording
- A one-sentence description for all 505 canonical parameters, provider- and resolution-independent,
  so the glossary says what each quantity *is* rather than only which unit it comes back in.
  `metadata.source_descriptions` carries what a given provider's field means alongside it, for 1057
  parameters
- Parameter discovery across all three interfaces: `GET /api/glossary`, the `glossary` MCP tool and
  `wetterdienst about glossary`. `coverage` answers which parameters a provider offers; the glossary
  answers what any of them measures and which unit it comes back in, including any `ts_unit_targets`
  override. Filter with `parameter=` (substring over the 505 names), `unit_type=` (a closed
  vocabulary, so an unknown one is a 422 rather than an empty result) and `limit=`. A filter
  matching nothing is an empty list over HTTP and a non-zero exit on the CLI, following grep
- Dataset and resolution descriptions on the metadata models, 88 of 148 datasets and 2 resolutions.
  `DatasetModel.description` and `ResolutionModel.description` had been declared but never
  populated, so `metadata["hourly"]["data"].description` returned `None` for every provider
- 216 more parameters can be interpolated and summarized, 343 of 514 rather than 127: soil
  temperature under a named cover and depth (114), forecast probabilities (65), soil moisture (12),
  evaporation per crop and soil, concrete slab temperature, humidex, climatological normals, and at
  the shorter radius precipitation intensity and visibility. The classification was never about the
  data being unavailable, only about which names had been written into the list by hand. What stays
  out stays out on purpose: coded observations, quality flags, counts, directions, and the 14 GHCNd
  soil temperatures whose cover is recorded as `unknown`. One cost: `interpolate()` stops querying
  stations once *every* requested parameter has enough of them, so a whole-dataset request against
  MOSMIX now has 65 probabilities to satisfy and walks further down the ranking
- Canonical parameter table (`wetterdienst.metadata.parameter_table`) holding the `unit_type` of
  each of the 505 canonical names in one place, plus a test checking every provider declaration
  against it. `wetterdienst.metadata.unit_type.UnitType` types it, so a mistyped unit type is a type
  error rather than something only a test can catch
- ECCC monthly and hourly expose the fields that were previously left undeclared, with twelve new
  canonical parameters: the monthly day counts and the climatological normals, and hourly
  `temperature_humidex`. Units were taken from the values rather than assumed -- each normal matches
  the range of the quantity it is a normal of, and humidex sits at or above the air temperature in
  all 233 paired observations sampled
- DWD hourly solar `true_local_time_offset` (`mess_datum_woz`), holding how far true local solar
  time runs ahead of a record's timestamp -- the longitude correction plus the equation of time.
  Solar records are stamped with the UTC instant of a whole true-solar-time hour, so the correction
  sits in the minutes, which wetterdienst rounds away; it was not reachable at all. At station 00183
  it runs 40 to 71 minutes, tracing the equation of time about a 54.7 minute longitude term
- DWD's two measurement method indicators are returned instead of dropped:
  `cloud_cover_total_measurement_method` (`v_n_i`) and `visibility_range_measurement_method`
  (`v_vv_i`). DWD writes them as letters -- `P` for a person, `I` for an instrument -- in otherwise
  numeric files, and the value column is Float64, so both were declared but silently dropped.
  Decoded to 1 and 2; the digits are wetterdienst's, and 0 is left unused so "not measured" stays
  distinct
- New canonical parameters `radiation_global_intensity`, `radiation_sky_long_wave_intensity` and
  `radiation_sky_short_wave_diffuse_intensity` for sources reporting irradiance (power per area)
  rather than irradiation accumulated over the interval, plus `cooling_degree_day`, the counterpart
  of `heating_degree_day`, and the `mass_per_volume` and `degree_hour` unit types the audit turned
  up
- `GET /api/version` reports `mcp_enabled` alongside the version. Whether `/mcp` exists is a
  property of the installation, and a client had no way to find out short of opening a session
  against it
- Docs: a parameter glossary on the Parameters page, built from the canonical parameter table at
  build time, with every provider metadata row linking to its entry

### Changed

- **Breaking**: `discover()` nests its answer so that every level has a place for its description:
  `{resolution: {"description": ..., "datasets": {dataset: {..., "parameters": [...]}}}}`. Consumers
  reading `data[resolution][dataset]` as a list of parameters now read
  `data[resolution]["datasets"][dataset]["parameters"]`
- **Breaking**: irradiance (`power_per_area`) is returned in W/m² rather than W/cm², so affected
  values are 10⁴ times larger. W/m² is what WMO specifies and what every source here publishes --
  MeteoSwiss global radiation now reads 0–1344 where it read 0–0.1344. Affects the 17 declarations
  using `power_per_area`: KNMI, MeteoSwiss, met.no Frost and RMI. Set
  `ts_unit_targets={"power_per_area": "watt_per_square_centimeter"}` to keep the old output.
  Irradiation (`energy_per_area`) is unchanged, still J/cm²
- **Breaking**: KNMI (10 minutes), RMI, MeteoSwiss and met.no reported irradiance under the
  `radiation_global`, `radiation_sky_long_wave` and `radiation_sky_short_wave_diffuse` names, which
  elsewhere mean irradiation in J/cm². These declarations moved to the `radiation_*_intensity`
  names. KNMI is the clearest case: its 10-minute `qg` is W/m² while its hourly `Q` is J/cm², so one
  name covered two quantities no conversion relates without the accumulation interval
- **Breaking**: Geosphere 10-minute and hourly radiation is returned as published rather than
  silently rescaled. `cglo` and `chim` are irradiance in W/m² and the parser multiplied them by the
  interval length to present them as irradiation; values are 16.67× and 2.78× larger, so multiply by
  0.06 and 0.36 to recover the old numbers. Daily and monthly are unaffected, using a distinct
  upstream parameter genuinely accumulated over the interval. This was the last in-parser unit
  conversion in the library
- **Breaking**: Météo-France synop `visibility_range` was the only declaration of that parameter
  using `length_long`, so it was returned in km while all 15 others return m. It now uses
  `length_medium`
- How a parameter behaves in space is declared once, on `CanonicalParameter`, rather than as three
  hand-maintained name lists that had to agree: `TimeseriesRequest.interpolatable_parameters`, the
  `ts_geo_station_distance` defaults and `_OCCURRENCE_BASED_PARAMETERS` are all views of the new
  `interpolation` (`"homogeneous"` at 40 km, `"heterogeneous"` at 20 km, or `None`) and
  `zero_inflated` fields. The two are separate facts: visibility decorrelates over a few kilometres
  without being zero-inflated. `_OCCURRENCE_BASED_PARAMETERS` is gone -- ask
  `PARAMETERS[name].zero_inflated`
- **Breaking**, mildly: `TimeseriesRequest.interpolatable_parameters` is a `frozenset` rather than a
  `list`. Every caller in the library only tests membership, but it is public, so code that indexes
  or slices it or relies on its order needs updating
- The `Parameter` enum is no longer used inside the library. The three places that hard-coded
  parameter names used it purely to spell a lowercased string and now spell the canonical name
  directly; all 186 references resolve to the same names as before
- `uv` resolves with a three-day cooldown (`tool.uv.exclude-newer = "3 days"`), so a release has to
  survive its first days in the wild before entering the lockfile. Recorded as a relative span so it
  does not churn between runs
- Locked dependencies refreshed to their latest compatible versions (cryptography 50, fastapi
  0.141.1, starlette 1.6, numpy 2.5.2, zarr 3.3, mcp 1.29), and several floors raised to what the
  code actually needs: `aiohttp>=3.14.0`, `stamina>=25.1.0`, `pandas>=2.2.2`, `shapely>=2.0.4`,
  `h5py>=3.11`, `plotly>=6.1.1` with `kaleido>=1.0.0` and `click>=8.2`
- Provider docs tables no longer carry the `unit type` column or own the description text. The unit
  type is a property of the canonical parameter, stated once in the glossary; the descriptions lived
  only in markdown, where no interface could reach them and the two copies drifted apart in both
  directions -- three defects found during the unit audit were each caught by the *other* source
  being right

### Removed

- **Breaking**: the `Parameter` enum, exported from the package root. It listed the canonical names
  but could not be used to request them -- `parameters=` accepts strings, tuples, `ParameterModel`
  and `DatasetModel`, so passing a member raised
  `AttributeError: 'Parameter' object has no attribute 'strip'`. The names live in
  `wetterdienst.metadata.parameter_table` and are discoverable through the glossary endpoint, MCP
  tool and `wetterdienst about glossary`
- The `unit_type` key from provider metadata declarations, 1575 of them across 29 files. It is a
  property of the measured quantity rather than of the provider, and restating it once per
  declaration is what let one canonical name pick different output units in different providers. All
  1692 parameters resolve to the same `unit_type` as before, but a **third-party metadata dict that
  still declares `unit_type` will now fail to validate** and should drop the key. It is no longer
  part of `ParameterModel.model_dump()`
- **Breaking**: seven DWD observation parameters that were declared but never returned a value, so a
  request for one now says so instead of answering with an empty frame:
  `cloud_type_layer1..4_abbreviation`, `weather_text`, `end_of_interval` and `true_local_time`. Each
  was checked against the archive: `v_sN_csa` matches `v_sN_cs` exactly across 398,381 records,
  every `ww` maps to one text across 443,827 while two codes share a text, and `end_of_interval`
  names a column that does not exist in the solar files at all
- **Breaking**: five `Parameter` members no provider declared, so no request could return them:
  `HUMIDEX`, `PRECIPITATION_FREQUENCY`, `PRECIPITATION_HEIGHT_LIQUID_MAX`, `TIME_WIND_GUST_MAX` and
  `TIME_WIND_GUST_MAX_1MILE_OR_1MIN`
- The `magnetic_field_intensity` and `wave_period` unit types. Each existed for exactly one
  parameter and both turned out mis-typed: WSV `current` is a bearing in degrees and WSV
  `wave_period` a duration in seconds
- Docs: `eccc/observation/annual.md` and `humidex` under hourly -- ECCC's `annual` resolution was
  dropped when values moved to the OGC API, and the overview still described bulk CSV downloads and
  four resolutions. The `pressure_air_sea` row of IMGW meteorology daily goes too, that provider no
  longer exposing it

### Fixed

- **Breaking**: conductivity conversions between per-centimetre and per-metre units were wrong, 8 of
  the 12 pairs by 10²–10⁴. Conductivity is per unit *length*, so a shorter length in the denominator
  means a larger number -- 1 S/cm is 100 S/m -- and the conversions had that inverted on top of
  mishandling the µ prefix. Since `siemens_per_meter` was the default target, every conductivity
  value the library returned was affected: WSV station 71160198 read 0.0021 S/m where the correct
  figure is 0.2059. Only the two pairs the tests covered were right
- **Breaking**: conductivity is returned in µS/cm rather than S/m, which is the convention in
  hydrology and what the sources publish -- S/m is large enough that rounding to 4 decimals cost
  real precision, 8.481 µS/cm coming back as `0.0008`. Set
  `ts_unit_targets={"conductivity": "siemens_per_meter"}` for the old unit, which now also returns
  the correct value
- **Breaking**: WSV Pegelonline values are scaled to the unit the metadata declares. The service
  publishes the unit per *timeseries*, not per parameter, and its stations disagree, so a single
  declaration was silently wrong wherever a station differed: water level is `cm` at most gauges but
  `m+NN` at 66 and `m+PNP` at 2, conductivity `µS/cm` or `mS/cm`, wave height `cm` or `m`. Wave
  height at MELLUMPLATE came back as 0.07–1.32 next to 12.66–280.6 at LT ALTE WESER for the same
  quantity, both labelled cm. A station publishing a unit the provider does not know is skipped with
  an error rather than reported under the wrong one. The `m+NN` gauges measure against sea level
  rather than the gauge datum even once scaled -- the `gauge_zero` column says which
- **Breaking**: WSV `current` is renamed `flow_direction` and returned in degrees, the source's
  `MGN` unit being degrees relative to magnetic north rather than a magnetic quantity; `wave_period`
  is returned in seconds, having been declared with a unit whose symbol was `1/s`; and
  `clearance_height` is returned in centimetres, having been declared in metres while every station
  publishes centimetres, so values were 100× too large
- **Breaking**: WSV parameter names are humanized like every other provider's. The parser wrote the
  source name lowercased while the humanizing map is keyed on it as declared, so values came back as
  `sigh`, `tp` and `r` rather than `wave_height_sign`, `wave_period` and `flow_direction`. With
  `ts_humanize=False` the names are now the source's own casing (`SIGH`) rather than lowercased
- WSV `gauge_zero` is populated rather than always null for all 738 stations -- the station frame
  built the column as `gauge_datum`, which `_base_columns` then dropped. This is the column that
  says which datum a water level is on, so it matters most for the `m+NN` gauges above. Turbidity is
  checked against the station's own unit like the other scaled parameters: `FNU`, `TE/F` and `NTU`
  all name the same formazin scale so no value changes, but a unit that is not on it is now skipped
- **Breaking**: ECCC hourly and monthly return data at all. Both declared parameters the OGC API
  never publishes -- hourly carried a copy of the *daily* field list, monthly carried bulk-CSV
  column headers -- so every request came back empty, and monthly additionally crashed on a
  `"2023-06"` timestamp. The requested field list is derived from the declarations now rather than
  hand-maintained per resolution, which is what let hourly drift into a copy of daily. Parameter
  names change for both resolutions
- **Breaking**: ECCC value requests return the whole period rather than an arbitrary 500 records.
  The OGC endpoint pages at 500 features and a station-year of hourly data is ~8800, so every
  request was silently truncated -- June 1972 at station 4055 returned 16 timestamps where it holds
  697. ECCC also exposes its whole ~8600-station network rather than the first 500, so 94% of it
  could not be requested at all, including every station whose data the hourly collection holds
- ECCC no longer fails on the daylight-saving fall-back hour, and stations opened before standard
  time no longer fail the listing -- `America/Toronto` is `-5:17:32` in 1895, an offset that is not
  a whole number of minutes and that polars rejects, so the conversion to UTC happens in Python.
  Neither showed up while the listing stopped at 500 rows. ECCC hourly `wind_direction` is returned
  in degrees rather than tens of degrees
- **Breaking**: ECCC daily `cooling_degree_days` and `heating_degree_days` were mapped onto
  `count_days_cooling_degree` and `count_days_heating_degree`, which mean a number of days. ECCC
  publishes the degree day total for the single day the record covers -- for station 2 on 1979-11-02
  the mean temperature is 6.3 °C and the value is 11.7, which is `18 - 6.3` and not any count. They
  now use `heating_degree_day` and the new `cooling_degree_day`, in °Cd; the values are unchanged
- **Breaking**: ECCC `wind_direction_gust_max` is returned in degrees rather than tens of degrees.
  ECCC's own docs call the column `Dir of Max Gust (10s deg)` and the declaration said `degree`, so
  every bearing came back 10× too small: 17–26 where the true directions are 170–260. Because the
  wrong values still sit inside 0–360, no range check could have caught it
- **Breaking**: four DWD subdaily parameters named the wrong quantity, not merely the wrong unit,
  each contradicted by the `Metadaten_Parameter_*.txt` shipped inside every data ZIP. `e_tf_ter` is
  whether ice had formed on the wet bulb thermometer, carrying only 0 and 1 across 82901 values, and
  was declared `temperature_air_mean_0_05m` in °C -- now `temperature_wet_ice_formation`. `ek_ter`
  is a 0-9 ground-state code declared `temperature_soil_mean_0_05m` -- now `soil_state_index`.
  `vk_ter` is a 0-9 visibility code declared `visibility_range` in metres, so subdaily visibility
  returned "5 metres" for class 5 -- now `visibility_range_class`. `tf_ter` is the wet bulb
  temperature declared `temperature_air_mean_2m`, where DWD's hourly moisture dataset already maps
  the same quantity to `temperature_wet_mean_2m`; confirmed against 83994 paired observations, a
  median 1.6 °C below the air temperature and never above it
- **Breaking**: DWD's `v_n_i` and `v_vv_i` are named for what they hold, both being *measurement
  method* indicators where `cloud_cover_total_index` and `visibility_range_index` described a coded
  value. `visibility_range_class` takes the freed `visibility_range_index` name, which it only ever
  lacked because the method indicator held it; `cloud_cover_total_index` is removed, no provider
  declaring a coded cloud cover
- **Breaking**: DWD hourly cloud cover no longer reports -0.125 of the sky. `cloud_cover_total` and
  `cloud_cover_layer1` to `_layer4` carry -1 where the sky could not be seen at all, SYNOP's N = 9,
  which in eighths converted to -0.125. It is null now. DWD documents only -999, so the reading is
  from the data: -1 stands in 1.2% of station 00003's hourly observations and fog codes accompany
  69.1% of those against 0.8% of the rest. The cloud *type* codes keep their -1, being dimensionless
- **Breaking**: MET Norway's in-band codes are decoded rather than returned as measurements. Frost
  writes them into the value itself: snow depth -1 is "no snow", a depth of zero rather than an
  absent one, and cloud cover -3 and 9 both mean the cover could not be estimated -- in eighths
  those converted to -0.375 and 1.125 of the sky, the second looking like a plausible reading. Snow
  depth -1 returns 0 and cloud cover -3 and 9 return null. Frost keeps the codes out of its own
  means, so only the elements are touched
- **Breaking**: MET Norway `cloud_cover_total` was declared `percent` while Frost publishes octas --
  its own `unit` field says so and the values run 0 to 8 -- so a fully overcast sky was reported as
  `8 %`. Now `one_eighth`
- **Breaking**: Geosphere `cloud_cover_total` is returned as a fraction rather than a percentage
  passed off as one. It was declared `decimal` while Geosphere documents `bewm_mittel` as `1/100`
  and returns 0-100, so the raw percentage went through the `fraction` target unconverted and every
  value was 100x its stated meaning. Its own `humidity` already declared `percent`
- **Breaking**: DWD road `visibility_range` is returned in metres rather than 1000x too large. It
  was declared `kilometer`, but BUFR `0 20 001 horizontalVisibility` is metres, nothing in the
  parser converts, and the provider's docs page already said `m`
- **Breaking**: AEMET daily `dir` is `wind_direction_gust_max`, not `wind_direction`. AEMET
  documents it as the direction of the maximum gust, and its hourly block already separates the two
- DWD `humidity_absolute` (`absf_std`) was declared `dimensionless`. It is a mass of water vapour
  per volume of air published in g/m³ -- station 00433 reads 1.6 to 19.1 -- so it now uses
  `mass_per_volume`. DWD `cooling_degree_hour` was declared in degree days while it accumulates per
  hour, reporting a monthly 4179.8 °Ch as 4179.8 °Cd, a figure no month can reach. Both values are
  unchanged
- Requesting several parameters at once no longer fails when one of them has no data for the
  station. Concatenating the empty result raised polars'
  `ShapeError: unable to append to a DataFrame of width 6 with a DataFrame of width 0`. This
  affected every provider that reports parameters separately. A parameter whose *download* fails is
  indistinguishable from one that has no data at this point, so such a parameter is omitted from the
  result rather than failing the request
- `summarize()` searched for stations within 20 km whatever the parameter. It bounded its search
  with `max(ts_geo_station_distance.values())`, and that mapping only holds entries for the
  parameters that get the *shorter* radius, everything else being answered by the default factory.
  It takes the widest radius among the requested parameters now, as interpolation already did
- The three new `radiation_*_intensity` parameters are listed in
  `TimeseriesRequest.interpolatable_parameters`; without them `interpolate()` and `summarize()`
  silently dropped the renamed radiation parameters for the affected providers
- Descriptions no longer leak between resolutions. `build_metadata_model` wrote them into the
  metadata dicts it was given, and providers commonly build one resolution's parameter list from
  another's by comprehension, reusing those very dicts: AEMET's annual parameters are its monthly
  ones minus humidity, so annual reported "Monthly mean temperature" and its own seven descriptions
  went nowhere
- 34 docs rows named a field the provider does not use -- DWD MOSMIX and DMO documented low cloud
  cover as `n1` where the element is `nl`, DWD 1-minute and 5-minute carried `precipitation_form`
  for `precipitation_index`, and ECCC and IMGW carried names from before their APIs changed. Each
  was a row whose description could not reach the model, so correcting them recovered 25
  descriptions that already existed. DWD's layer cloud cover descriptions are correct too: the
  English sheet truncates `V_S1_NS` to "cloud cover of 1. laye" and repeats it for `V_S2_NS`, so the
  second layer was described as the first
- `CITATION.cff` names the released version again and is valid CFF 1.2.0 once more. It had lost
  `version` and `date-released` and carried an empty `identifiers:` key, which parses as null and
  fails the schema, so the file every citation tool reads described no particular release and could
  not be converted at all. A test now ties it to the sources it duplicates

## [0.132.0] - 2026-08-04

### Changed

- Bump the minimum supported polars version to `>=1.43.0` (from `>=1.15.0`), required by the
  `explode(empty_as_null=...)` and `concat(how="horizontal_extend")` APIs used below

### Fixed

- Resolve polars and pyarrow deprecation warnings surfaced in the test suite: pass explicit
  `empty_as_null=True` to all `explode()` calls, switch `concat(how="horizontal")` to
  `how="horizontal_extend"`, and read Feather exports via `pyarrow.ipc.open_file()` instead of the
  deprecated `pyarrow.feather.read_table`. Also vectorise two per-element `map_elements` calls
  (eaufrance/hubeau, ea/hydrology) that had native polars equivalents
- Type the station response-model `state` field as nullable so the `stations` MCP tool stops rejecting
  MOSMIX/DMO stations. These forecast stations have no state and serialise `state` as `null`, but
  `_Station.state` and `_OgcFeatureProperties.state` were typed non-null, so the derived MCP output
  schema failed validation with `Output validation error: None is not of type 'string'` for every
  `mosmix`/`dmo` station listing (the same schema drift fixed for `values`/`interpolate`/`summarize`)

## [0.131.0] - 2026-08-02

### Added

- Add a DWD SWSMOS network (`dwd`/`swsmos`) exposing the road weather forecast (Straßenwetter-MOS)
  for DWD's ~1800 road weather stations. Each model run provides an hourly forecast out to +167 hours
  (selectable via `issue`, default: the latest run): air, dew-point and road surface temperature,
  liquid precipitation, precipitation probabilities and the road surface condition. This is the
  forecast counterpart to the DWD `road` observation network
- Add the DWD `10_minutes` urban climate (Stadtklima) datasets to the `dwd`/`observation` network,
  served from DWD's `climate_urban/` path (recent period only): `urban_precipitation`,
  `urban_pressure`, `urban_solar`, `urban_temperature_air` (incl. the new
  `temperature_radiant_mean_2m` parameter), `urban_temperature_extreme`, `urban_temperature_soil`,
  `urban_wind` and `urban_wind_extreme`. These complement the existing hourly urban datasets. The
  urban station-description lists are parsed by content because they frequently leave the optional
  date and Bundesland fields blank
- Add an IPMA (Portugal) observation provider (`ipma`/`observation`) backed by the key-less
  `api.ipma.pt` open-data JSON feeds. Provides near-real-time hourly observations (temperature,
  humidity, sea-level pressure, wind speed/direction, precipitation, global radiation) from ~222
  stations. Recent-only (a rolling ~1-day window), so a date range within the last day is required.
  The `-99.0` missing sentinel becomes null and the 8-point wind-direction code is converted to
  degrees
- Add an LHMT (Lithuania) observation provider (`lhmt`/`observation`) backed by the key-less
  `api.meteo.lt` JSON REST API. Provides hourly observations (temperature, humidity, wind
  speed/gust/direction, cloud cover, sea-level pressure, precipitation, snow depth) from ~52
  stations, with historical data back to roughly 2016 fetched per station and day. Settled past days
  are cached indefinitely while the current day uses a short cache
- Add a Met Office (UK) observation provider (`metoffice`/`observation`) backed by the MIDAS Open
  archive on CEDA (UK Open Government Licence). Covers eight datasets across daily and hourly
  resolution (rain, temperature, weather, wind, radiation, soil temperature). Requires a free CEDA
  account (`WD_AUTH__CEDA=<username>:<password>`); the bearer token is minted from those credentials
  and cached in-process until shortly before it expires. Multiple report types per day are collapsed
  to one value per calendar day, multi-day rain accumulations are dropped, and native units are
  normalised (e.g. visibility from decametres to metres)

### Changed

- Sharpen the `interpolate`/`summarize` endpoint descriptions (which become the MCP tool
  descriptions) and the MCP instructions so agents stop routing plain weather questions to them.
  `stations` -> `values` is now stated as the default for weather at a named place even when a
  specific past date is given, and interpolate/summarize are called out as opt-in estimates -- used
  only on explicit request or when no station with data is near the point -- because they add
  inaccuracy

### Fixed

- Type the `interpolate`/`summarize` response-model items to match what the endpoints serialise, so
  their MCP output schemas stop rejecting valid results. `_InterpolatedValuesItemDict` and
  `_SummarizedValuesItemDict` now include the `resolution`/`dataset` keys (always present in the
  rows) and type `value`/`distance_mean`/`distance`/`taken_station_id` as nullable: interpolating or
  summarizing a point with no station in reach serialises `null` for those fields, which the previous
  non-null schema rejected (the same schema drift fixed for `values` in 0.130.0)

## [0.130.0] - 2026-07-30

### Changed

- Raise stale/incorrect dependency lower bounds to honest, still-compatible floors (no change to the
  resolved/tested versions). Most importantly `fastapi>=0.115` (was `>=0.95.1`): the REST endpoints
  use Pydantic query-parameter models, a feature added in FastAPI 0.115, so the old floor advertised
  support the code never had. Also bump `httpx>=0.27`, `uvicorn>=0.30`, `duckdb>=1` (restapi/sql/
  duckdb extras), `xarray>=2024.6`, `fsspec>=2024.6`, `python-dateutil>=2.8.2`, `tabulate>=0.9`,
  `tqdm>=4.64`, `click>=8.1`, and add a lower bound to `sqlalchemy-cratedb>=0.40` (was unbounded
  below). Dev/docs groups are unchanged
- Rewrite the `history`, `summarize` and `interpolate` endpoint descriptions (which become the MCP
  tool descriptions) so small models stop mis-routing plain weather questions to them: they now say
  what each returns and that it is not measured weather -- `history` is station *metadata* history
  (name/location/sensor changes), `summarize`/`interpolate` estimate a value for a point *between*
  stations. Add a "Choosing a tool" note to the MCP instructions pointing weather questions at the
  `stations` -> `values` workflow

### Fixed

- Match station names with `WRatio` (was `token_sort_ratio`) in `filter_by_name`, so a bare place
  name finds its stations: `name="Kiel"` now returns `Kiel-Holtenau`/`Kiel-Kronshagen` instead of
  nothing (`token_sort_ratio` scored the length gap "Kiel" vs "Kiel-Holtenau" at ~47%, below the 0.8
  threshold). `WRatio` is a partial matcher, so a query that is a common sub-token (e.g. `name="Bad"`)
  matches many stations -- set `name_threshold=1.0` (keep only score-100 matches) or use the `sql`
  filter (`sql="name = 'Aach'"`) for an exact name match
- Honor the `rank` argument in `filter_by_name` (it was silently ignored, always returning up to 5
  matches): it now returns the `rank` best matches, best score first (default 1). The `stations`
  REST/CLI listing requests several name candidates by default and passes through an explicit `rank`
- Limit the `stations` listing to the requested `rank` on the REST API (`/api/stations`) and CLI
  (`stations`). A rank filter keeps every station in the frame (the `rank` limit is applied lazily
  during value collection), so a listing that asked for the N closest returned all stations instead
  -- e.g. `rank=3` near Kiel returned all 1284 DWD stations (a ~365 KB response that overwhelmed MCP
  clients). Listings now return the `rank` closest by distance
- Return `404` for the OAuth discovery paths (`/.well-known/oauth-authorization-server`,
  `/.well-known/oauth-protected-resource`) on the REST API so MCP clients treat the open `/mcp`
  server as no-auth instead of attempting (and failing) OAuth Dynamic Client Registration
- Type `value`/`quality` as `float | None` (was `str`) in the `_ValuesItemDict` response model, so
  the `/api/values` OpenAPI schema matches the numbers actually serialised. The MCP `values` tool
  derives its output schema from that model, and the wrong `str` type made FastMCP reject valid
  results with `9.0 is not of type 'string'`. This fixes the real schema instead of the previous
  workaround (`validate_output=False`), so MCP output validation is now enabled again

## [0.129.0] - 2026-07-27

### Added

- Add an optional Model Context Protocol (MCP) endpoint at `/mcp` on the REST API, exposing the data
  endpoints as MCP tools over the streamable-HTTP transport (via [FastMCP](https://gofastmcp.com/)).
  The tools are made agent-friendly (workflow `instructions`, clean tool names, hidden noise
  endpoints, permissive output validation) so even small models can drive them. Enable it with the
  `mcp` extra (`pip install wetterdienst[mcp]`), which is included in the Docker image
- Add DWD weather alerts (CAP warnings) provider (`dwd/alerts`) with Python API, CLI `alerts`
  command and REST `/api/alerts` endpoint: all active warnings, one row per alert, with a GeoJSON
  MultiPolygon geometry, on community (Gemeinde) or district (Landkreis) granularity; a `date`
  selects a historical snapshot from DWD's rolling ~48-hour window
- Parse DWD radar site BUFR products (echo top, reflectivity) into a polars DataFrame on
  `RadarResult.df`, opt-in via the `read_bufr` setting (requires the `eccodes` and `bufr` extras)
- Add RMI (Belgium) observation provider with 10-minute, hourly and daily resolution
  from the automatic weather station (AWS) network (no authentication required)
- Add CHMI (Czechia) observation provider with 10-minute, hourly, daily, monthly and annual
  resolution (no authentication required)
- Add FMI (Finland) observation provider with hourly and daily resolution
  (no authentication required)

### Changed

- Add descriptions to every field of the REST request models (stations, values, interpolate,
  summarize, history, issues). They surface in the REST API's OpenAPI schema (`/docs`) and in the
  generated MCP tool parameters, making both surfaces self-documenting.
- REST API and CLI: the `with_metadata` and `with_stations` options now default to `false` on the
  `stations`, `values`, `interpolate`, `summarize` and `history` commands/endpoints, so output
  contains just the requested data by default. Pass `with_metadata=true` / `with_stations=true`
  (or `--with_metadata=true` / `--with_stations=true`) to include the provider-metadata and station
  blocks as before.
- Reduce DWD MOSMIX/DMO KML parsing memory by streaming the zipped KML instead of
  decompressing it fully in memory (~6.5x lower peak RSS on MOSMIX-S)
- Refresh locked dependencies to their latest compatible versions (polars 1.43.1, pyarrow 25,
  fastapi 0.140.7, uvicorn 0.51, and others). Update the dev toolchain (ruff 0.16, ty 0.0.64) and
  adopt their new checks: ignore `CPY001` (no per-file copyright headers) and `PLR0917`
  (too-many-positional-arguments, sibling of the already-ignored `PLR0913`), fix a
  `log.exception()` call outside an exception handler, wrap implicitly concatenated test URLs, and
  narrow the DWD-derived available-dates set so `min()`/`max()` no longer see `datetime | None`

### Fixed

- Parse NOAA GHCN-hourly (GHCNh) timestamps from the provided ISO date column instead of
  reconstructing them from separate year/month/day/hour/minute fields
- Fix the `about fields` CLI command, which crashed with a `TypeError` because it forwarded
  `resolution` as a separate argument to `describe_fields()`
- Report coverage cleanly for metadata-less standalone networks (`dwd/radar`, `dwd/alerts`):
  `about coverage` and `/api/coverage` now return a clear message instead of crashing with an
  `AttributeError` / HTTP 500

## [0.128.0] - 2026-07-22

### Added

- Add KNMI (Netherlands) observation provider with 10-minute, hourly and daily resolution
  (requires a free KNMI Data Platform API key)
- Add DMI (Denmark) climate data observation provider with hourly, daily, monthly and
  annual resolution (no authentication required)
- Add AEMET (Spain) observation provider with hourly (real-time), daily, monthly and
  annual resolution
- Add SMHI (Sweden) observation provider with 1-minute, hourly, daily and monthly resolution
- Add Météo-France (France) synop network (subdaily, 3-hourly)
- Add Météo-France (France) observation network (6-minute, hourly, daily, monthly)
- Add MeteoSwiss (Switzerland) observation provider with 10-minute, hourly, daily, monthly and annual resolution

### Changed

- Reduce the memory footprint of aggregated value results (`.values.all()`) by storing the
  `station_id`, `resolution`, `dataset` and `parameter` columns as polars `Enum` instead of `String`
  (roughly halves the size of tidy frames); note that the dtype of these columns is now `Enum`. To
  get plain `String` columns back (e.g. for `.str` operations or strict dtype checks), cast them via
  `df.with_columns(pl.col(pl.Enum).cast(pl.String))`

## [0.127.0] - 2026-07-07

### Added

- `[REST API]` The `/api/coverage` endpoint now reports a `date_required` flag per
  provider/network, true if any of its resolutions require a date range for value
  queries (e.g. MET Norway Frost). Lets frontends surface this before submitting a
  query rather than after the query fails.

### Changed

- `[MET Norway Frost]` Value requests now fetch all parameters of a dataset/resolution in
  a single batched request (comma-separated `elements=`) instead of one request per
  parameter, cutting the number of HTTP requests by up to 11x for multi-parameter queries.
  Falls back to the previous per-parameter behavior (including historical time-series
  discovery) if the batched request itself returns a 404.
- `[IMGW]` File listing now prunes IMGW's per-period subfolders (named `YYYY` or
  `YYYY_YYYY`, encoding the exact date range they cover) to only those overlapping the
  requested date range, instead of recursively listing the entire directory tree on every
  request. Cuts the number of HTTP requests from ~33 (meteorology) / ~74 (hydrology) down
  to the 1-2 folders that actually matter for a given query.

### Removed

- `[IMGW]` Removed the hardcoded lat/lon override for hydrology station `150190410`,
  a workaround for a corrupted upstream CSV line from ~2024-02. The station's data has
  been clean upstream for a while, so the override had become a no-op; keeping it around
  risked silently clobbering a legitimate future coordinate change for that station.

### Fixed

- `[IMGW]` Station listing for both meteorology and hydrology no longer fails: the
  upstream station CSVs gained an extra "founding year" column and switched from a
  Windows codepage to UTF-8, which broke column parsing and produced mojibake names.
  Also fixed a station-list column-index bug (hydrology latitude/longitude were reading
  the wrong columns), a missing `return_dtype` on the lat/lon DMS-to-decimal conversion,
  and station rows no longer carrying a `resolution`/`dataset` tag, which made
  `.values.all()` fail outright.
- `[IMGW]` Hydrology value downloads now honor `WD_USE_CERTIFI`/`use_certifi`, matching
  the station list fetch and the meteorology provider. Previously it was silently ignored
  for the actual data downloads.
- `[IMGW]` Hydrology daily requests touching 2023 or later no longer crash with
  `ValueError: month must be in 1..12`. IMGW switched from twelve monthly zips per year
  to one consolidated yearly zip starting 2023, which broke the date-range parsing that
  assumed a `codz_YYYY_MM.zip` filename. Also handles the two different (and, for 2024,
  outright malformed) CSV export quirks IMGW has used for these consolidated files since,
  for both daily and monthly hydrology data: semicolon-separated unquoted rows in 2023,
  and in 2024 every row wrapped in a broken extra pair of quotes with doubled inner quotes.
- `[IMGW]` Meteorology `synop` daily requests no longer crash with
  `TypeError: '<' not supported between instances of 'NoneType' and 'NoneType'`. Unlike
  every other IMGW meteorology dataset, `synop` daily has always been archived one file
  per station per period (e.g. `2024_100_s.zip` for the station whose id ends in `100`)
  rather than one file per month across all stations, going back to at least the 1966-1970
  archive — the URL selection logic never accounted for this, so `synop` daily was
  non-functional for any date range.

## [0.126.0] - 2026-07-07

### Fixed

- `[REST API]` Station listing no longer fails with `StartDateEndDateError` for providers
  with `date_required` datasets (e.g. MET Norway Frost hourly, 10-minute, 6-hour). The
  date requirement only applies to value fetching, not to listing available stations. Also
  fixed a `TypeError` when constructing requests for providers that declare multi-period
  datasets but do not accept a `periods` constructor argument.

## [0.125.0] - 2026-07-06

### Added

- `[MET Norway Frost]` Add new provider `metno/frost` for the Norwegian Meteorological
  Institute's Frost API. Supports 10-minute, hourly, 6-hour, daily, monthly and annual
  resolutions with ~2200 stations across Norway. Authentication via free API key
  (`WD_AUTH__METNO_FROST` env var). Historical synoptic 6-hourly data is retrieved
  via an `availableTimeSeries` fallback that resolves the time-series-specific query
  parameters required by the Frost API.
- `[Settings]` Load `.env` files automatically via `env_file=".env"` and support nested
  env vars via `env_nested_delimiter="__"` (e.g. `WD_TS_UNIT_TARGETS__temperature=degree_fahrenheit`).
- `[Metadata]` Add `auth: bool = False` field to `MetadataModel` so providers requiring
  an API key can declare it. Defaults to `False` for all existing providers.
- `[API]` Add `is_configured() -> bool` and `is_valid() -> bool` classmethods to
  `TimeseriesRequest`. `is_configured` checks whether credentials are present (cheap,
  offline); `is_valid` probes the API to confirm they actually work (should be cached
  by the implementation). Both default to `True` for providers that need no auth.
- `[REST API]` `GET /api/coverage` (no parameters) now returns
  `{provider: {network: {auth: bool, configured: bool, valid: bool}}}` instead of
  `{provider: [network]}`, exposing per-network auth status to API consumers.
- `[REST API]` Add `GET /api/auth?provider=&network=` endpoint that returns
  `{provider, network, auth, configured, valid}` for a specific provider/network,
  allowing clients to re-check credential validity without fetching all coverage.
  `valid` is always `false` when `configured` is `false` (probe cannot run without credentials).

## [0.124.0] - 2026-06-30

### Added

- `[DWD MOSMIX / DMO]` Add `available_issues(station_id, settings)` classmethod to
  `DwdMosmixRequest` and `DwdDmoRequest` that lists the model-run datetimes currently
  available on DWD's OpenData server for a given station (MOSMIX_L single-station KMZ
  files and ICON single-station KMZ files respectively).
- `[CLI]` Add `wetterdienst issues --provider <p> --network <n> --station <id>` command
  that prints available issue datetimes as a JSON array.
- `[REST API]` Add `GET /api/issues?provider=<p>&network=<n>&station=<id>` endpoint
  returning `{"issues": ["<UTC ISO datetime>", ...]}`. Currently supported:
  `provider=dwd, network=mosmix` and `provider=dwd, network=dmo`.

### Fixed

- `[DWD MOSMIX / DMO]` Fix `issue` (and DMO `lead_time`) parameters being silently
  ignored when calling the REST API or `_get_stations_request` directly. The guard used
  `isinstance(api, DwdMosmixRequest)` where `api` is the *class* itself (not an instance),
  so the condition was always `False` and `DwdForecastDate.LATEST` was used regardless of
  the caller's intent. Changed to `issubclass` and added a `None`-guard so that omitting
  `issue` still falls through to the dataclass default (`DwdForecastDate.LATEST`).
- `[Frontend / Meteogram]` Fix x-axis tick labels overlapping massively on narrow mobile
  screens. Tick interval is now chosen based on actual chart pixel width: a 7-day MOSMIX
  forecast on a ~360 px phone uses 24-hour ticks instead of 6-hour ones (28 → 7 labels).
  Day-name annotations above the chart also shorten to weekday-only (`Mo`) when a day
  occupies fewer than 44 px, preventing header collisions on long forecasts.

## [0.123.0] - 2026-06-18

### Fixed

- `[DWD Observation]` Skip periods where all file downloads fail (empty `filenames_and_files`)
  before passing to the parser, preventing a `polars.exceptions.InvalidOperationError` from
  `pl.concat(..., how="align")` caused by a schema-less `LazyFrame` being mixed with valid ones.
- Reduce stamina retry attempts in `download_file` from 3 to 2 to limit worst-case wait time
  per file on persistent network failures.
- Add a default `aiohttp.ClientTimeout(total=30)` to `fsspec_client_kwargs` in `Settings` so
  HTTP connections time out after 30 seconds instead of hanging indefinitely.
- Wrap bare `int` timeouts in `aiohttp.ClientTimeout` inside `HTTPFileSystem.__init__` so that
  aiohttp >= 3.9 (which rejects plain int timeouts) works correctly with `fsspec_client_kwargs`.

## [0.122.0] - 2026-06-07

### Fixed

- Fix `download_file` retry mechanism: the previous `@stamina.retry` decorator was broken
  (the `on=` predicate checked `ClientResponse` instead of an exception, and all errors were
  swallowed before stamina could see them). Replaced with `stamina.retry_context` wrapping the
  `filesystem.cat_file` call directly. Retries are now triggered on `FileNotFoundError`,
  `FSTimeoutError`, `ClientConnectorError`, `ClientResponseError` and `ClientPayloadError`; all exhausted errors are
  returned as `File` objects rather than propagated.
- `[DWD Dmo]` Convert latitude and longitude from degrees and minutes to decimal degrees using `convert_dm_to_dd`.
- Fix station history parsing and add tests

## [0.121.1] - 2026-05-26

### Fixed

- Propagate `Settings.use_certifi` through `NetworkFilesystemManager.get` and the
  download helpers (`download_file`, `download_files`, `list_remote_files_fsspec`) so
  that fsspec's HTTP clients use the certifi certificate bundle when requested. This
  ensures provider code using these helpers respects the global `use_certifi` setting.
  Fixes #1669.
  Thanks to @KonstantinWaser for reporting the issue.

## [0.121.0] - 2026-05-09

### Added

- Interpolation / summarize: greatly expanded the set of interpolatable parameters
  beyond the original six. All continuous, spatially-correlated meteorological fields
  are now supported, organised into two distance classes:
    - **~40 km** (homogeneous / large-scale): all temperature variants at 2 m and 0.05 m
      (mean, max, min, last-24 h, multiday, mean-of-extremes), dew point, wet-bulb,
      wind-chill, surface temperature, soil temperatures (0.02 m – 2 m depth),
      heating/cooling degree aggregates, all humidity variants (`humidity`,
      `humidity_absolute`, `humidity_max`, `humidity_min`, `humidex`), all wind-speed
      variants and gust-max variants, wind movement, Beaufort scale, all sunshine-duration
      variants, global / diffuse / direct / long-wave radiation, all pressure variants
      (site, sea-level, reduced, max, min, tendency, vapour), total / effective / time-
      windowed cloud cover, and evapotranspiration / evaporation fields.
    - **~20 km** (heterogeneous / locally variable): all precipitation-height variants
      (including liquid, droplet, rocker, last-1 h … last-24 h, multiday, significant-
      weather, max), precipitation duration, new-snow depth and its multiday / max
      variants, and new-snow water-equivalent variants.
    - Fixes #1651 (`sunshine_duration` was silently dropped by both `interpolate` and
      `summarize` because it was absent from `interpolatable_parameters`).
- Interpolation: occurrence-threshold zeroing (previously only applied to
  `precipitation_height`) is now applied to **all** zero-inflated accumulation
  parameters: every precipitation-height variant, precipitation duration, new-snow
  depth variants, and new-snow water-equivalent variants. This prevents spurious
  small positive values when the surrounding stations recorded no event.
- Tests: five new unit tests for the occurrence-threshold logic in
  `core/interpolate.py` (`test_occurrence_threshold_*`) and two new remote
  integration tests (`test_interpolation_sunshine_duration_daily`,
  `test_interpolation_snow_depth_new_daily`).

- CLI: `--start-date` / `--end-date` options added to the `values`, `interpolate`, and
  `summarize` commands as a user-friendly alternative to the `--date` ISO-8601 interval
  syntax. Passing only `--start-date` treats it as a single-point date; passing only
  `--end-date` likewise. `--date` and `--start-date`/`--end-date` are mutually exclusive
  and raise a `UsageError` when combined.
- CLI: comprehensive `help` text added to all options across the `values`, `stations`,
  `interpolate`, and `summarize` commands, including `--provider`, `--network`,
  `--parameters`, `--periods`, all station-filtering options, `--format`, `--target`,
  `--shape`, `--humanize`, `--convert_units`, `--unit_targets`, `--skip_empty`,
  `--skip_criteria`, `--skip_threshold`, `--drop_nulls`, `--with_metadata`,
  `--with_stations`, `--pretty`, and `--issue`.

### Fixed

- Station name filtering (`filter_by_name`, `--name`) was case-sensitive, causing
  lowercase queries like `"darmstadt"` to return no results. Fixed by adding
  `processor=fuzz_utils.default_process` to the rapidfuzz call.
- NOAA GHCN hourly: adapted to upstream format changes — the station list CSV now
  contains non-integer values in the `WMO_ID` column (e.g. `"open"`), and the
  per-station PSV files renamed the station identifier column from `Station_ID` to
  `STATION`.
- DWD observation requests no longer raise `MetaFileNotFoundError` when a period's
  station description file is absent on the server (e.g. `10_minutes/precipitation/now`).
  The missing period is skipped with a warning and remaining periods are still returned.
- No internet connection no longer raises an error; instead, an empty result is
  returned. `ClientConnectorError` (TCP/DNS failures) is caught in `download_file`
  and stored as `NoInternetError` in the `File` object. All provider call sites
  return empty `DataFrame`/`LazyFrame` values accordingly. Fixes #1624.
- `NetworkFilesystemManager` now uses `threading.local()` instead of a class-level
  `dict` so each thread in `ThreadPoolExecutor`-based parallel downloads gets its
  own `WholeFileCacheFileSystem` instance, eliminating a race condition in the
  in-memory metadata cache that caused `TypeError: cannot unpack non-iterable bool
  object` at `fsspec/implementations/cached.py:716`.
- Reverted the directory-listing cache from `shelved-cache` + `cachetools` back to
  `diskcache`. `shelved-cache` wraps Python's `dbm`/`shelve`, which is not safe for
  concurrent access; parallel pytest-xdist workers sharing the same cache directory
  caused `_dbm.error` cascades and cascading test failures. `diskcache` uses SQLite
  and is both thread- and process-safe.
- `FileDirCache` mapping semantics corrected: `__getitem__` now raises `KeyError` on a
  cache miss (previously returned `None`) and short-circuits when `use_listings_cache`
  is `False`; `__contains__` uses a proper existence check so falsy cached values (e.g.
  an empty directory listing `[]`) are no longer misreported as absent; `__len__`
  delegates to the underlying cache directly instead of materialising all keys.

### Security

- `diskcache` advisory GHSA-w8v5-vhqr-4h9v (CVE-2025-69872, pickle deserialization)
  acknowledged and suppressed in `pysentry` and `dependency-review`. Exploitation
  requires write access to the local user cache directory, which is not a realistic
  attack vector for this project.
- `lxml` upgraded to 6.1.0, resolving GHSA-vfmq-68hx-4jfw (local file read via
  `resolve_entities`).

### Changed

- Station name filtering now uses `token_sort_ratio` instead of `token_set_ratio`,
  making word-order variations (e.g. `"Koeln Bonn"` → `"Köln/Bonn"`) match correctly.
  Zero regressions across all 1281 stations; 149 stations now resolve to their correct
  match when searched by exact name.
- Default fuzzy-match threshold for `filter_by_name` lowered from `0.9` to `0.8`,
  allowing single-character typos and common shorthands to match while maintaining
  100% precision.
- `name_threshold` is now exposed in the CLI (`--name-threshold`) for the `stations`
  and `values` commands, and wired through `StationsRequest` / `ValuesRequest` models
  so the REST API `/api/stations` and `/api/values` endpoints honour it automatically.
  All previously stale `0.9` defaults in stripes endpoints updated to `0.8`.

## [0.120.0] - 2026-04-11

### Added

- Add DWD Derived data for hourly climate (duett), daily soil, and monthly soil datasets,
  including parameters for evapotranspiration, soil moisture, soil temperature, frost/thaw depth,
  radiation, sunshine duration, and heating/cooling degree days, thanks @mspils and @jb-at-bdr

### Changed

- ECCC observation: migrate data retrieval from legacy CSV bulk download to
  the `api.weather.gc.ca` OGC API. Updates parameter metadata to match new
  column naming, rewrites wide-to-long pivoting to handle `*_flag` quality
  columns, and expands timezone mapping to include daylight saving variants.

### Fixed

- DWD `describe_fields`: adapt to updated PDF location and format. Description
  PDFs moved from the period subdirectory (e.g. `daily/kl/recent/`) to the
  dataset directory (`daily/kl/`). The PDF content now uses a structured table
  format with column name and description on the same line. The German section
  header changed from `Parameter` to `CSV Inhaltsbeschreibung`.

## [0.119.0] - 2026-02-17

### Added

- New API endpoint for climate stripes data

### Changed

- Improve interpolation and summary
- DWD DMO: Remove unnecessary validation for minimum dataframe length in date extraction
- Rename API endpoint /stripes/values to /stripes/image
- Migrate from `diskcache` to `cachetools` and `shelved-cache` for caching functionality. The new
  implementation uses `shelved_cache.PersistentCache` wrapping `cachetools.TTLCache` for improved
  maintainability while preserving all existing functionality and API compatibility.

### Fixed

- Update API endpoint for geosphere data retrieval

## [0.118.0] - 2026-02-01

### Added

- Implement station history retrieval; added API and request support to query historical station
  snapshots and lifecycle events (created, updated, decommissioned) by station id and dataset.
- Add `use_certifi` setting to use certifi certificate bundle instead of system certificates for
  HTTPS connections. Default is `False` for backward compatibility. Can be enabled via
  `Settings(use_certifi=True)` or environment variable `WD_USE_CERTIFI=true`.

### Changed

- Move code to src directory
- Filter By Rank: Sort stations by distance and station id
- Soften validation for numbers and integers in UI core request models

## [0.117.0] - 2026-01-03

### Added

- Restapi: Add /api/version endpoint to get current version of wetterdienst backend (used in frontend)

## [0.116.0] - 2025-12-09

### Changed

- Improve polars code, thanks @SeeBastion524

### Fixed

- Allow concatenation of station data with varying columns, thanks @jb-at-bdr
- Adjust data type of "name" column, thanks @jb-at-bdr

## [0.115.0] - 2025-11-24

### Added

- Add classifier for python 3.14
- Add new data of DWD Derived, thanks @jb-at-bdr

### Changed

- Update docker image to use python 3.14

### Fixed

- Cast value in interpolate function to float

  @ninjeanne reported that wetterdienst lately quirks when running interpolation. This issue is related to one of the
  new polars versions > 1.33.1. A shorthand fix would be to cast the value coming from the scipy interpolate function to
  a float.

## [0.114.3] - 2025-11-07

### Fixed

- \[DWD Obs\] Fix encoding issue

## [0.114.2] - 2025-11-05

### Fixed

- \[DWD DMO\] Fix path for `icon_eu` and minor fixes

## [0.114.1] - 2025-11-01

### Fixed

- Fix global import of duckdb exception in `to_target` method

## [0.114.0] - 2025-10-31

### Added

- \[DWD Obs\] Use utf8 encoding for parsing data
- Add `if_exists` argument to `to_target`
- Use more polars-native methods

### Fixed

- \[DWD Road\]: Skip empty files

### Changed

- Bump polars minimum to 1.15.0

## [0.113.0] - 2025-09-21

### Added

- Make Mosmix and DMO a lot faster for multiple stations requests

### Changed

- Bump pypdf to <7
- Make pypdf optional

## [0.112.0] - 2025-09-06

### Changed

- Switch back to `WholeFileCacheFileSystem` for caching
- Improve more things on caching
- Update uv.lock
- Polars: Set format and timezone on datetime conversion

## [0.111.0] - 2025-08-03

### Added

- Make humidity interpolatable
- Improve interpolation configuration
- Set missing `return_dtype` in fileindex function
- Set `return_dtype` for polars functions

### Changed

- Pin zarr to `>=3.1;python_version>=3.11`
- Docker: Copy uv bin from uv image
- Pin lxml to <7

### Fixed

- Parse parameters only if any are given
- Fix export for interpolated values to csv
- Round timestamps of hourly solar data to nearest hour
- Fix several polars issues
- Docker: Install chromium to fix png export

## [0.110.0] - 2025-07-23

### Added

- Make retry of `download_file` more robust
- Overhaul docs switching to `sphinx` and `myst-parser`
- Improve exception handling in restapi
- Improve download of files

### Changed

- Drop upper version pins for fsspec and tzdata
- Introduce `wetterdienst.model`, streamline others
- Bump minimum kaleido version to `0.2.2`

### Fixed

- Export: Fix influx tags and fields
- \[NOAA GHCN hourly\] Fix metadata creation
- Include resolution column in wide format
- Disallow `polars==1.31.0` due to issues

## [0.109.0] - 2025-06-03

### Changed

- Split `coordinates` and `bbox` into separate arguments
- Bump dependencies

## [0.108.0] - 2025-04-25

### Added

- Improve restapi look and add impressum
- Add uvloop and httptools for speed via `uvicorn[standard]`

### Changed

- Use dataclass everywhere
- Refactor query method
- Adjust retry of function `download_file`

### Fixed

- Fix numerous radar tests

## [0.107.0] - 2025-03-25

### Changed

- Refactor `download_file`

### Fixed

- Fix false attribute parsing by pydantic model in cli
- Fix datetime parsing for generic radar data

## [0.106.0] - 2025-03-05

### Fixed

- Improve parameter unpacking in `ParameterSearch.parse`
- Fix docker manifest

## [0.105.0] - 2025-03-01

### Added

- Add user agent to default `fsspec_client_kwargs`
- Adjust apis to track resolution and dataset (allows querying data for different resolutions and datasets in one
  request)

### Changed

- Improve date parsing across multiple apis
- Cleanup docker image
- Improve numerous apis

### Fixed

- \[WSV Pegel\] Fix characteristic values and improve date parsing

## [0.104.0] - 2025-02-15

### Changed

- Reduce the margin of the stations plot
- Make pydantic models for uis simpler
- Migrate from `sklearn+numpy` to `pyarrow` for location querying
- Remove command from Docker file
- Improve workflow for Docker
- Get rid of columns enumeration
- \[NOAA GHCN\] Improve date parsing and other fixes

## [0.103.0] - 2025-02-02

### Added

- Stripes: Replace matplotlib by plotly
- Explorer: Add download button for plot
- Split up plotting extras into `plotting` and `matplotlib`
- Interpolation/Summary: Add dataset to DataFrame
- Add plotting capabilities

### Changed

- Update docker image extras

### Removed

- Remove unused cachetools dependency

### Fixed

- Fix benchmark code
- Make fastexcel a polars extra
- Drop click-params dependency
- Make pyarrow a polars extra

## [0.102.0] - 2025-01-17

### Added

- Add cmd to docker image

### Changed

- Use `to_list()[0]` instead of `first()`

## [0.101.0] - 2025-01-13

### Added

- Move more details into `MetadataModel`

### Changed

- \[DWD Obs\] Make the download function more flexible using threadpool
- \[DWD Obs\] Cleanup parser function
- \[DWD Obs\] Improve fileindex and metaindex

### Fixed

- \[DWD Obs\] Reduce unnecessary file index calls during retrieval of data for stations with multiple files

## [0.100.0] - 2025-01-06

### Added

- Add logo for restapi
- **Breaking:** Add dedicated unit converter

  Attention: Many units are changed to be more consistent with typical meteorological units. We now use `°C` for
  temperatures. Also, length units are now separated in `length_short`, `length_medium` and `length_long` to get more
  reasonable decimals. For more information, see the new units chapter (usage/units) in the documentation.

### Changed

- Add reasonable upper bounds for dependencies

### Fixed

- Filter out invalid underscore prefixed files

## [0.99.0] - 2024-12-30

### Added

- Add setting `ts_complete=False` that allows to prevent building a complete time series

### Changed

- Docs: Change to markdown using mkdocs
- Settings: Switch to `pydantic_settings` for settings management
- Improve wetterdienst api class
- Dissolve wetterdienst notebook into examples
- Use `duckdb.sql` and ask only for WHERE clause
- Update restapi annotations
- Use `Settings` in restapi/cli core functions
- Restapi/Cli: Use pydantic models for request parameters
- Rename `dropna` to `drop_nulls`
- Change default of `drop_nulls` to True
- Replace occurrences of `dt.timezone.utc` by `ZoneInfo("UTC")`
- Improve release workflow using `uv build` and `uv publish`
- Improve docker-publish workflow to use `uv build`

## [0.98.0] - 2024-12-09

### Added

- Add support for Python 3.13

### Changed

- **Breaking:** Add new metadata model: Requests now use `parameters` instead of `parameter` and `resolution` e.g.
  `parameters=[("daily", "kl")]` instead of `parameter="kl", resolution="daily"`

### Deprecated

- Deprecate Python 3.9

## [0.97.0] - 2024-10-06

### Fixed

- DWD Road: Use correct 15 minute resolution

## [0.96.0] - 2024-10-04

### Changed

- Bump polars to `>=1.0.0`
- Change `DWDMosmixValues` and `DWDDmoValues` to follow the core `_collect_station_parameter` method
- Allow only single issue retrieving with `DWDMosmixRequest` and `DWDDmoRequest`

## [0.95.1] - 2024-09-04

### Fixed

- Fix `state` column in station list creation for DWD Observation

## [0.95.0] - 2024-08-27

### Changed

- Make fastexcel non-optional
- Remove upper dependency bounds

## [0.94.0] - 2024-08-10

### Added

- DWD Road: Add new station groups, log warning if no data is available, especially if the station group is one of the
  temporarily unavailable ones

### Fixed

- Explorer: Fix DWD Mosmix request kwargs setup

## [0.93.0] - 2024-08-06

### Fixed

- Fix multiple Geosphere parameter and unit enums
- Explorer: Fix wrap `(parameter, dataset)` in iterator
- Adjust parameter typing of apis

## [0.92.0] - 2024-07-31

### Changed

- Rename parameters
    - units in parameter names are now directly following the number
    - temperature parameters now use meter instead of cm and also have a unit
    - e.g. TEMPERATURE_AIR_MEAN_2M, CLOUD_COVER_BETWEEN_2KM_TO_7KM, PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0MM_LAST_6H

### Fixed

- Bump pyarrow version to <18
- Fix EaHydrology station list parsing
- Rename `EaHydrology` to `EAHydrology`
- Fix propagation of settings through `EAHydrology` values

## [0.91.0] - 2024-07-14

### Fixed

- Fix DWD Road api

## [0.90.0] - 2024-07-14

### Changed

- Bump `environs` to <12

### Fixed

- Explorer: Fix json export

## [0.89.0] - 2024-07-03

### Fixed

- EaHydrology: Fix date parsing
- Hubeau: Use correct frequency unit
- Fix group by unpack

## [0.88.0] - 2024-06-14

### Added

- Allow passing `--listen` when running the explorer to specify the host and port

## [0.87.0] - 2024-06-06

### Added

- Add precipitation version

### Changed

- Rename warming stripes to climate stripes
- Replace custom Settings class with pydantic model

## [0.86.0] - 2024-06-01

### Changed

- Interpolation/Summary: Require start and end date
- Enable interpolation and summarization for all services

### Fixed

- Fix multiple issues with interpolation and summarization

## [0.85.0] - 2024-05-29

### Fixed

- Fix `dropna` argument for DWD Mosmix and DMO
- Adjust DWD Mosmix and DMO kml reader to parse all parameters
- Fix `to_target(duckdb)` for stations
- Fix init of `DwdDmoRequest`

## [0.84.0] - 2024-05-15

### Fixed

- Fix DWD Obs station list parsing again

## [0.83.0] - 2024-04-26

### Added

- Allow `wide` shape with multiple datasets

## [0.82.0] - 2024-04-25

### Fixed

- Adjust column specs for DWD Observation station listing
- Maintain order during deduplication
- Change threshold in `filter_by_name` to 0.0...1.0

## [0.81.0] - 2024-04-09

### Added

- Warming stripes: Add option to enable/disable showing only active stations

## [0.80.0] - 2024-04-08

### Added

- Migrate explorer to streamlit
- UI: Add warming stripes

### Changed

- Explorer: Disable higher than daily resolutions for hosted version

## [0.79.0] - 2024-03-21

### Fixed

- Fix parsing of DWD Observation stations where name contains a comma

## [0.78.0] - 2024-03-09

### Added

- Docker: Install more extras

### Fixed

- Cli/Restapi: Return empty values if no data is available

## [0.77.1] - 2024-03-08

### Fixed

- Fix setting NOAA GHCN-h date to UTC

## [0.77.0] - 2024-03-08

### Changed

- Refactor index caching -> Remove monkeypatch for fsspec

## [0.76.1] - 2024-03-03

### Fixed

- NOAA GHCN Hourly: Fix date parsing

## [0.76.0] - 2024-03-02

### Added

- Add NOAA GHCN Hourly API (also known as ISD)

## [0.75.0] - 2024-02-25

### Changed

- Remove join outer workaround for polars and use `outer_coalesce` instead
- Allow duckdb for Python 3.12 again
- Update REST API index layout
- Bump polars to 0.20.10
- Docker: Bump to Python 3.12
- Docker: Reduce image size

## [0.74.0] - 2024-02-22

### Added

- Restapi: Add health check endpoint

## [0.73.0] - 2024-02-09

### Changed

- Set upper version bound for Python to 4.0
- Make pandas optional

### Fixed

- Add temporary workaround for bugged line in IMGW Hydrology station list
- Fix parsing of dates in NOAA GHCN api

## [0.72.0] - 2024-01-13

### Added

- Allow for passing kwargs to the `to_csv` method

### Fixed

- Fix issue when using `force_ndarray_like=True` with pint UnitRegistry

## [0.71.0] - 2024-01-03

### Added

- CI: Add support for Python 3.12

### Fixed

- Fix issue with DWD DMO api

## [0.70.0] - 2023-12-30

### Added

- Docker: Enable interpolation in wetterdienst standard image

### Changed

- Replace partial with lambda in most places
- IMGW: Use ttl of 5 minutes for caching

### Fixed

- IMGW Meteorology: Drop workaround for mixed up station list to fix issue
- WSV Hydrology: Fix issue with station list characteristic values
- DWD Observation: Remove redundant replace empty string in parser
- NWS Observation: Read json data from bytes
- EA Hydrology: Read json data from bytes

## [0.69.0] - 2023-12-18

### Added

- Restapi: Unify station parameter and add alias
- Interpolation: Make maximum station distance per parameter configurable via settings

### Fixed

- Result: Convert date to string only if dataframe is not empty
- Restapi: Move restapi from /restapi to /api

## [0.68.0] - 2023-12-01

### Added

- Add example for comparing Mosmix forecast and Observation data

### Fixed

- Fix parsing of DWD Observation 1 minute precipitation data

## [0.67.0] - 2023-11-17

### Changed

- **Breaking:** Use start_date and end_date instead of from_date and to_date
- Use artificial station id for interpolation and summarization
- Rename taken station ids columns for interpolation and summarization

## [0.66.1] - 2023-11-08

### Fixed

- Add workaround for issue with DWD Observation station lists

## [0.66.0] - 2023-11-07

### Added

- Add lead time argument - one of short, long - for DWD DMO to address two versions of icon

### Changed

- Rework dict-like export formats and tests with extensive support for typing
- Improve radar access
- Style restapi landing page
- Replace timezonefinder by tzfpy

### Fixed

- Fix DWD DMO access again

## [0.65.0] - 2023-10-24

### Changed

- Cleanup error handling
- Make cli work with DwdDmoRequest API
- Cleanup cli docs

### Fixed

- Fix DWD Observation API for 5 minute data

## [0.64.0] - 2023-10-12

### Added

- Export: Add support for InfluxDB 3.x

### Changed

- Remove direct tzdata dependency
- Replace pandas read_fwf calls by polars substitutes

## [0.63.0] - 2023-10-08

### Added

- \[Streamlit\] Add sideboard with settings
- \[Streamlit\] Add station information json
- \[Streamlit\] Add units to DataFrame view and plots
- \[Streamlit\] Add JSON download

### Fixed

- Return data correctly sorted

## [0.62.0] - 2023-10-07

### Changed

- Raise minimum version of polars to 0.19.6 due to breaking changes

### Fixed

- Fix multiple issues with DwdObservationRequest API

## [0.61.0] - 2023-10-06

### Added

- Make parameters TEMPERATURE_AIR_MAX_200 and TEMPERATURE_AIR_MIN_200 summarizable/interpolatable
- Add streamlit app for DWD climate stations
- Add sql query function to streamlit app

### Fixed

- Fix imgw meteorology station list parsing
- Improve streamlit app plotting capabilities
- Fix DWD DMO api

## [0.60.0] - 2023-09-16

### Added

- Add implementation for DWD DMO

## [0.59.3] - 2023-09-11

### Fixed

- Fix DWD solar date string correction

## [0.59.2] - 2023-09-06

### Fixed

- Fix documentation and unit conversion for Geosphere 10minute radiation data

## [0.59.1] - 2023-07-18

### Fixed

- Fix Geosphere parameter names

## [0.59.0] - 2023-07-30

### Changed

- Revise type hints for parameter and station_id

### Fixed

- Fix Geosphere Observation parsing of dates in values -> thanks to @mhuber89 who discovered the bug and delivered a fix

## [0.58.1] - 2023-07-26

### Fixed

- Fix bug with Geosphere parameter case

## [0.58.0] - 2023-07-10

### Added

- Add retry to functions
- Add IMGW Hydrology API
- Add IMGW Meteorology API

### Changed

- Rename FLOW to DISCHARGE and WATER_LEVEL to STAGE everywhere

## [0.57.1] - 2023-06-28

### Fixed

- Fix pyarrow dependency

## [0.57.0] - 2023-05-15

### Added

- Sources: Add DWD Road Weather data

### Changed

- **Breaking:** Backend: Migrate from pandas to polars

  Switching to Polars may cause breaking changes for certain user-space code heavily using pandas idioms, because
  Wetterdienst now returns a [Polars DataFrame](https://pola-rs.github.io/polars/py-polars/html/reference/dataframe/).
  If you absolutely must use a pandas DataFrame, you can cast the Polars DataFrame to pandas by using the `.to_pandas()`
  method.

## [0.56.2] - 2023-05-11

### Fixed

- Fix Unit definition for RADIATION_GLOBAL

## [0.56.1] - 2023-05-10

### Fixed

- Fix JOULE_PER_SQUARE_METER definition from kilojoule/m2 to joule/m2

## [0.56.0] - 2023-05-02

### Fixed

- Update docker images
- Fix now and now_local attributes on core class

## [0.55.2] - 2023-04-20

### Fixed

- Fix precipitation index interpolation

## [0.55.1] - 2023-04-17

### Fixed

- Fix setting empty values in DWD observation data
- Fix DWD Radar composite path

## [0.55.0] - 2023-03-19

### Changed

- Drop Python 3.8 support

### Fixed

- Explorer: Fix function calls

## [0.54.1] - 2023-03-13

### Fixed

- Fix DWD Observations 1 minute fileindex

## [0.54.0] - 2023-03-06

### Changed

- SCALAR: Improve handling skipping of empty stations, especially within .filter_by_rank function
- Make all parameter levels equal for all weather services to reduce complexity in code
- Change `tidy` option to `shape`, where `shape="long"` equals `tidy=True` and `shape="wide"` equals `tidy=False`
- Naming things: All things "Scalar" are now called "Timeseries", with settings prefix `ts_`
- Drop some unnecessary enums
- Rename Environment Agency to ea in subspace

### Fixed

- CLI: Fix cli arguments with multiple items separated by comma (,)
- Fix fileindex/metaindex for DWD Observation
- DOCS: Fix precipitation height unit
- DOCS: Fix examples with "recent" period

## [0.53.0] - 2023-02-07

### Added

- CLI: Add command line options `wetterdienst --version` and `wetterdienst -v` to display version number

### Changed

- SCALAR: Change tidy option to be set to True if multiple different entire datasets are queried (in accordance with
  exporting results to json where multiple DataFrames are concatenated)
- Further cleanups
- Change Settings to be provided via initialization instead of having a singleton

## [0.52.0] - 2023-01-19

### Added

- Add Geosphere Observation implementation for Austrian meteorological data

### Changed

- RADAR: Clean up code and merge access module into api

### Fixed

- DWD MOSMIX: Fix parsing station list
- DWD MOSMIX: Fix converting degrees minutes to decimal degrees within the stations list. The previous method did not
  produce correct results on negative lat/lon values.

## [0.51.0] - 2023-01-01

### Added

- Update wetterdienst explorer with clickable stations and slightly changed layout

### Fixed

- Improve radar tests and certain dict comparisons
- Fix problem with numeric column names in method gain_of_value_pairs

## [0.50.0] - 2022-12-03

### Added

- Interpolation/Summary: Now the queried point can be an existing station laying on the border of the polygon that it's
  being checked against
- UI: Add interpolate/summarize methods as subspaces

### Changed

- Geo: Change function signatures to use latlon tuple instead of latitude and longitude
- Geo: Enable querying station id instead of latlon within interpolate and summarize
- Geo: Allow using values of nearby stations instead of interpolated values

### Fixed

- Fix timezone related problems when creating full date range

## [0.49.0] - 2022-11-28

### Added

- Add NOAA NWS Observation API
- Add Eaufrance Hubeau API for French river data (flow, stage)

### Fixed

- Fix bug where duplicates of acquired data would be dropped regarding only the date but not the parameter
- Fix NOAA GHCN access issues with timezones and empty data

## [0.48.0] - 2022-11-11

### Added

- Add example to dump DWD climate summary observations in zarr with help of xarray

### Fixed

- Fix DWD Observation urban_pressure dataset access (again)

## [0.47.1] - 2022-10-23

### Fixed

- Fix DWD Observation urban_pressure dataset access

## [0.47.0] - 2022-10-14

### Added

- Add support for reading DWD Mosmix-L all stations files

## [0.46.0] - 2022-10-14

### Added

- Add summary of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

## [0.45.2] - 2022-10-11

### Fixed

- Make DwdMosmixRequest return data according to start and end date

## [0.45.1] - 2022-10-10

### Fixed

- Fix passing an empty DataFrame through unit conversion and ensure set of columns

## [0.45.0] - 2022-09-22

### Added

- Add interpolation of multiple weather stations for a given lat/lon point (currently only works for
  DWDObservationRequest)

### Fixed

- Fix access of DWD Observation climate_urban datasets

## [0.44.0] - 2022-09-18

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Slightly adapt the conversion function to satisfy linter
- Adjust Docker images to fix build problems, now use python 3.10 as base
- Adjust NOAA sources to AWS as NCEI sources currently are not available
- Make explorer work again for all services setting up Period enum classes instead of single instances of Period for
  period base

### Fixed

- Fix parameter names:
    - we now use consistently INDEX instead of INDICATOR
    - index and form got mixed up with certain parameters, where actually index was measured/given but not the form
    - global radiation was mistakenly named radiation_short_wave_direct at certain points, now it is named correctly

## [0.43.0] - 2022-09-05

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Use lxml.iterparse to reduce memory consumption when parsing DWD Mosmix files
- Fix Settings object instantiation
- Change logging level for Settings.cache_disable to INFO

## [0.42.1] - 2022-08-25

### Fixed

- Fix DWD Mosmix station locations

## [0.42.0] - 2022-08-22

### Changed

- Move cache settings to core wetterdienst Settings object

### Fixed

- Fix two parameter names

## [0.41.1] - 2022-08-04

### Fixed

- Fix correct mapping of periods for solar daily data which should also have Period.HISTORICAL besides Period.RECENT

## [0.41.0] - 2022-07-24

### Fixed

- Fix passing through of empty dataframe when trying to convert units

## [0.40.0] - 2022-07-10

### Changed

- Update dependencies

## [0.39.0] - 2022-06-27

### Changed

- Update dependencies

## [0.38.0] - 2022-06-09

### Added

- Add DWD Observation 5 minute precipitation dataset
- Add test to compare actually provided DWD observation datasets with the ones we made available with wetterdienst

### Fixed

- Fix one particular dataset which was not correctly included in our DWD observations resolution-dataset-mapping

## [0.37.0] - 2022-06-06

### Fixed

- Fix EA hydrology access
- Update ECCC observation methods to acquire station listing

## [0.36.0] - 2022-05-31

### Fixed

- Fix using shared FSSPEC_CLIENT_KWARGS everywhere

## [0.35.0] - 2022-05-29

### Added

- Add option to skip empty stations (option tidy must be set)
- Add option to drop empty rows (value is NaN) (option tidy must be set)

## [0.34.0] - 2022-05-22

### Added

- Add UKs Environment Agency hydrology API

## [0.33.0] - 2022-05-14

### Fixed

- Fix acquisition of DWD weather phenomena data
- Set default encoding when reading data from DWD with pandas to 'latin1'
- Fix typo in `EcccObservationResolution`

## [0.32.4] - 2022-05-14

### Fixed

- Fix acquisition of historical DWD radolan data that comes in archives

## [0.32.3] - 2022-05-12

### Fixed

- Fix creation of empty DataFrame for missing station ids
- Fix creation of empty DataFrame for annual data

## [0.32.2] - 2022-05-10

### Fixed

- Revert ssl option

## [0.32.1] - 2022-05-09

### Fixed

- Circumvent DWD server ssl certificate problem by temporary removing ssl verification

## [0.32.0] - 2022-04-24

### Added

- Add implementation of WSV Pegelonline service

### Changed

- Clean up code at several places

### Fixed

- Fix ECCC observations access

## [0.31.1] - 2022-04-03

### Fixed

- Change integer dtypes in untidy format to float to prevent loosing information when converting units

## [0.31.0] - 2022-03-29

### Changed

- Improve integrity of dataset, parameter and unit enumerations with further tests
- Change source of hourly sunshine duration to dataset sun
- Change source of hourly total cloud cover (+indicator) to dataset cloudiness

## [0.30.1] - 2022-03-03

### Fixed

- Fix naming of sun dataset
- Fix DWD Observation monthly test

## [0.30.0] - 2022-02-27

### Fixed

- Fix monthly/annual data of DWD observations

## [0.29.0] - 2022-02-27

### Added

- Add datasets EXTREME_WIND (subdaily) and MORE_WEATHER_PHENOMENA (daily)
- Add support for Python 3.10

### Changed

- Simplify parameters using only one enumeration for flattened and detailed parameters
- Rename dataset SUNSHINE_DURATION to SUN to avoid complications with similar named parameter and dataset
- Rename parameter VISIBILITY to VISIBILITY_RANGE

### Removed

- Drop Python 3.7 support

## [0.28.0] - 2022-02-19

### Added

- Extend explorer to use all implemented APIs

### Fixed

- Fix cli/restapi: return json and use NULL instead of NaN

## [0.27.0] - 2022-02-16

### Added

- Add support for Python 3.10

### Fixed

- Fix missing station ids within values result
- Add details about time interval for NOAA GHCN stations
- Fix falsely calculated station distances

### Removed

- Drop support for Python 3.7

## [0.26.0] - 2022-02-06

### Added

- Add Wetterdienst.Settings to manage general settings like tidy, humanize,...
- Instead of "kind" use "network" attribute to differ between different data products of a provider

### Changed

- Rename DWD forecast to mosmix

### Fixed

- Change data source of NOAA GHCN after problems with timeouts when reaching the server
- Fix problem with timezone conversion when having dates that are already timezone aware

## [0.25.1] - 2022-01-30

### Fixed

- Fix cli error with upgraded click ^8.0 where default False would be converted to "False"

## [0.25.0] - 2022-01-30

### Fixed

- Fix access to ECCC stations listing using Google Drive storage
- Remove/replace caching entirely by fsspec (+monkeypatch)
- Fix bug with DWD intervals

## [0.24.0] - 2022-01-24

### Added

- Add NOAA GHCN API

### Fixed

- Fix radar index by filtering out bz2 files

## [0.23.0] - 2021-11-21

### Fixed

- Add missing positional dataset argument for _create_empty_station_parameter_df
- Timestamps of 1 minute / 10 minutes DWD data now have a gap hour at the end of year 1999 due to timezone shifts

## [0.22.0] - 2021-10-01

### Added

- Introduce core Parameter enum with fixed set of parameter names. Several parameters may have been renamed!
- Add FSSPEC_CLIENT_KWARGS variable at wetterdienst.util.cache for passing extra settings to fsspec request client

## [0.21.0] - 2021-09-10

### Changed

- Start migrating from `dogpile.cache` to `filesystem_spec`

## [0.20.4] - 2021-08-07

### Added

- Enable selecting a parameter precisely from a dataset by passing a tuple like [("precipitation_height", "kl")]
  or [("precipitation_height", "precipitation_more")], or for cli/restapi use "precipitation_height/kl"
- Rename `wetterdienst show` to `wetterdienst info`, make version accessible via CLI with `wetterdienst version`

### Fixed

- Bug when querying an entire DWD dataset for 10_minutes/1_minute resolution without providing start_date/end_date,
  which results in the interval of the request being None
- Test of restapi with recent period
- Get rid of pandas performance warning from DWD Mosmix data

## [0.20.3] - 2021-07-15

### Fixed

- Bugfix acquisition of DWD radar data
- Adjust DWD radar composite parameters to new index

## [0.20.2] - 2021-06-26

### Fixed

- Bugfix tidy method for DWD observation data

## [0.20.1] - 2021-06-26

### Changed

- Update readme on sandbox developer installation

### Fixed

- Bugfix show method

## [0.20.0] - 2021-06-23

### Added

- Change cli base to click
- Add support for wetterdienst core API in cli and restapi
- Export: Use InfluxDBClient instead of DataFrameClient and improve connection handling with InfluxDB 1.x
- Export: Add support for InfluxDB 2.x
- Add show() method with basic information on the wetterdienst instance

### Fixed

- Fix InfluxDB export by skipping empty fields

## [0.19.0] - 2021-05-14

### Changed

- Make tidy method a abstract core method of Values class

### Fixed

- Fix DWD Mosmix generator to return all contained dataframes

## [0.18.0] - 2021-05-04

### Added

- Add origin and si unit mappings to services
- Use argument "si_units" in request classes to convert origin units to si, set to default
- Improve caching behaviour by introducing optional `WD_CACHE_DIR` and `WD_CACHE_DISABLE` environment variables. Thanks,
  @meteoDaniel!
- Add baseline test for ECCC observations
- Add DWD Observation hourly moisture to catalogue

## [0.17.0] - 2021-04-08

### Added

- Add capability to export data to Zarr format
- Add Wetterdienst Explorer UI. Thanks, @meteoDaniel!
- Add MAC ARM64 support with dependency restrictions
- Add support for stations filtering via bbox and name
- Add support for units in distance filtering

### Changed

- Rename station_name to name
- Rename filter methods to .filter_by_station_id and .filter_by_name, use same convention for bbox, filter_by_rank (
  previously nearby_number), filter_by_distance (nearby_distance)

### Fixed

- Radar: Verify HDF5 responses instead of returning invalid data
- Mosmix: Use cached stations to improve performance

## [0.16.1] - 2021-03-31

### Changed

- Make .discover return lowercase parameters and datasets

## [0.16.0] - 2021-03-29

### Added

- Add capability to export to Feather- and Parquet-files to I/O subsystem
- Add `--reload` parameter to `wetterdienst restapi` for supporting development
- Add Environment and Climate Change Canada API

### Changed

- Use direct mapping to get a parameter set for a parameter
- Rename DwdObservationParameterSet to DwdObservationDataset as well as corresponding columns
- Merge metadata access into Request
- Repair CLI and I/O subsystem
- Improve spreadsheet export
- Increase I/O subsystem test coverage
- Make all DWD observation field names lowercase
- Make all DWD forecast (mosmix) field names lowercase
- Rename humanize_parameters to humanize and tidy_data to tidy

### Deprecated

- Deprecate support for Python 3.6

### Fixed

- Radar: Use OPERA as data source for improved list of radar sites

## [0.15.0] - 2021-03-07

### Added

- Add StationsResult and ValuesResult to allow for new workflow and connect stations and values request
- Add accessor .values to Stations class to get straight to values for a request
- Add top-level API

### Fixed

- Fix issue with Mosmix station location

## [0.14.1] - 2021-02-21

### Fixed

- Fix date filtering of DWD observations, where accidentally an empty dataframe was returned

## [0.14.0] - 2021-02-05

### Added

- DWD: Add missing radar site "Emden" (EMD, wmo=10204)

### Changed

- Change key STATION_HEIGHT to HEIGHT, LAT to LATITUDE, LON to LONGITUDE
- Rename "Data" classes to "Values"
- Make arguments singular

### Fixed

- Mosmix stations: fix longitudes/latitudes to be decimal degrees (before they were degrees and minutes)

## [0.13.0] - 2021-01-21

### Added

- Create general Resolution and Period enumerations that can be used anywhere
- Create a full dataframe even if no values exist at requested time
- Add further attributes to the class structure
- Make dates timezone aware
- Restrict dates to isoformat

## [0.12.1] - 2020-12-29

### Fixed

- Fix 10minutes file index interval range by adding timezone information

## [0.12.0] - 2020-12-23

### Changed

- Move more functionality into core classes
- Add more attributes to the core e.g. source and timezone
- Make dates of internal data timezone aware, set start date and end date to UTC
- Add issue date to Mosmix class that actually refers to the Mosmix run instead of start date and end date
- Use Result object for every data related return
- In accordance with typical naming conventions, DWDObservationSites is renamed to DWDObservationStations, the same is
  applied to DWDMosmixSites
- The name ELEMENT is removed and replaced by parameter while the actual parameter set e.g. CLIMATE_SUMMARY is now found
  under PARAMETER_SET

### Removed

- Remove StorageAdapter and its dependencies
- Methods self.collect_data() and self.collect_safe() are replaced by self.query() and self.all() and will deprecate at
  some point

## [0.11.1] - 2020-12-10

### Fixed

- Bump `h5py` to version 3.1.0 in order to satisfy installation on Python 3.9

## [0.11.0] - 2020-12-04

### Added

- Upgrade Docker images to Python 3.8.6
- Radar data: Add non-RADOLAN data acquisition

### Changed

- Change wherever possible column type to category
- Increase efficiency by downloading only historical files with overlapping dates if start_date and end_date are given
- Use periods dynamically depending on start and end date

### Fixed

- InfluxDB export: Fix export in non-tidy format (#230). Thanks, @wetterfrosch!
- InfluxDB export: Use "quality" column as tag (#234). Thanks, @wetterfrosch!
- InfluxDB export: Use a batch size of 50000 to handle larger amounts of data (#235). Thanks, @wetterfrosch!
- Update radar examples to use `wradlib>=1.9.0`. Thanks, @kmuehlbauer!
- Fix inconsistency within 1 minute precipitation data where historical files have more columns
- Improve DWD PDF parser to extract quality information and select language. Also, add an example at
  `example/dwd_describe_fields.py` as well as respective documentation.
- Move intermediate storage of HDF out of data collection
- Fix bug with date filtering for empty/no station data for a given parameter

## [0.10.1] - 2020-11-14

### Fixed

- Upgrade to dateparser-1.0.0. Thanks, @steffen746, @noviluni and @Gallaecio! This fixes a problem with timezones on
  Windows. The reason is that Windows has no zoneinfo database and `tzlocal` switched from `pytz` to
  `tzinfo`. https://github.com/earthobservations/wetterdienst/issues/222

## [0.10.0] - 2020-10-26

### Added

- CLI: Obtain "--tidy" argument from command line
- Extend MOSMIX support to equal the API of observations
- DWDObservationData now also takes an individual parameter independent of the pre-configured DWD datasets by using
  DWDObservationParameter or similar names e.g. "precipitation_height"
- Newly introduced coexistence of DWDObservationParameter and DWDObservationParameterSet to address parameter sets as
  well as individual parameters

### Changed

- DWDObservationSites now filters for those stations which have a file on the server
- Imports are changed to submodule thus now one has to import everything from wetterdienst.dwd
- Renaming of time_resolution to resolution, period_type to period, several other relabels

## [0.9.0] - 2020-10-09

### Added

- Rename `DWDStationRequest` to `DWDObservationData`
- Add `DWDObservationSites` API wrapper to acquire station information
- Move `discover_climate_observations` to `DWDObservationMetadata.discover_parameters`
- Add PDF-based `DWDObservationMetadata.describe_fields()`

### Changed

- Large refactoring
- Make period type in DWDObservationData and cli optional
- Activate SQL querying again by using DuckDB 0.2.2.dev254. Thanks, @Mytherin!

### Fixed

- Fix coercion of integers with nans
- Fix problem with storing IntegerArrays in HDF

## [0.8.0] - 2020-09-25

### Added

- Add TTL-based persistent caching using dogpile.cache
- Add `example/radolan.py` and adjust documentation
- Export dataframe to different data sinks like SQLite, DuckDB, InfluxDB and CrateDB
- Query results with SQL, based on in-memory DuckDB
- Split get_nearby_stations into two functions, get_nearby_stations_by_number and get_nearby_stations_by_distance
- Add MOSMIX client and parser. Thanks, @jlewis91!
- Add basic HTTP API

## [0.7.0] - 2020-09-16

### Added

- Add test for Jupyter notebook
- Add function to discover available climate observations (time resolution, parameter, period type)
- Make the CLI work again and add software tests to prevent future havocs
- Use Sphinx Material theme for documentation

### Fixed

- Fix typo in enumeration for TimeResolution.MINUTES_10

## [0.6.0] - 2020-09-07

### Changed

- Enhance usage of get_nearby_stations to check for availability
- Output of get_nearby_stations is now a slice of meta_data DataFrame output

## [0.5.0] - 2020-08-27

### Added

- Add RADOLAN support
- Change module and function naming in accordance with RADOLAN

## [0.4.0] - 2020-08-03

### Added

- Extend DWDObservationData to take multiple parameters as request
- Add documentation at readthedocs.io
- \[cli\] Adjust methods to work with multiple parameters

## [0.3.0] - 2020-07-26

### Added

- Add option for data collection to tidy the DataFrame (properly reshape) with the "tidy_data" keyword and set it to be
  used as default

### Changed

- Establish code style black
- Setup nox session that can be used to run black via nox -s black for one of the supported Python versions

### Fixed

- Fix integer type casting for cases with nans in the column/series
- Fix humanizing of column names for tidy data

## [0.2.0] - 2020-07-23

### Added

- \[cli\] Add geospatial filtering by distance.
- \[cli\] Filter stations by station identifiers.
- \[cli\] Add GeoJSON output format for station data.
- Improvements to parsing high resolution data by setting specific datetime formats and changing to concurrent.futures

### Changed

- Change column name mapping to more explicit one with columns being individually addressable
- Add full column names for every individual parameter
- More specific type casting for integer fields and string fields

### Fixed

- Fix na value detection for cases where cells have leading and trailing whitespace

## [0.1.1] - 2020-07-05

### Added

- \[cli\] Add geospatial filtering by number of nearby stations.
- Simplify release pipeline
- Small updates to readme

### Changed

- Parameter, time resolution and period type can now also be passed as strings of the enumerations e.g. "
  climate_summary" or "CLIMATE_SUMMARY" for Parameter.CLIMATE_SUMMARY
- Enable selecting nearby stations by distance rather than by number of stations

### Fixed

- Change updating "parallel" argument to be done after parameter parsing to prevent mistakenly not found parameter
- Remove find_all_match_strings function and extract functionality to individual operations

## [0.1.0] - 2020-07-02

### Added

- Initial release
- Update README.md
- Update example notebook
- Add Gh Action for release
- Rename library

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/v0.141.0...HEAD
[0.141.0]: https://github.com/earthobservations/wetterdienst/compare/v0.140.0...v0.141.0
[0.140.0]: https://github.com/earthobservations/wetterdienst/compare/v0.139.0...v0.140.0
[0.139.0]: https://github.com/earthobservations/wetterdienst/compare/v0.138.0...v0.139.0
[0.138.0]: https://github.com/earthobservations/wetterdienst/compare/v0.137.0...v0.138.0
[0.137.0]: https://github.com/earthobservations/wetterdienst/compare/v0.136.0...v0.137.0
[0.136.0]: https://github.com/earthobservations/wetterdienst/compare/v0.135.0...v0.136.0
[0.135.0]: https://github.com/earthobservations/wetterdienst/compare/v0.134.0...v0.135.0
[0.134.0]: https://github.com/earthobservations/wetterdienst/compare/v0.133.0...v0.134.0
[0.133.0]: https://github.com/earthobservations/wetterdienst/compare/v0.132.0...v0.133.0
[0.132.0]: https://github.com/earthobservations/wetterdienst/compare/v0.131.0...v0.132.0
[0.131.0]: https://github.com/earthobservations/wetterdienst/compare/v0.130.0...v0.131.0
[0.130.0]: https://github.com/earthobservations/wetterdienst/compare/v0.129.0...v0.130.0
[0.129.0]: https://github.com/earthobservations/wetterdienst/compare/v0.128.0...v0.129.0
[0.128.0]: https://github.com/earthobservations/wetterdienst/compare/v0.127.0...v0.128.0
[0.127.0]: https://github.com/earthobservations/wetterdienst/compare/v0.126.0...v0.127.0
[0.126.0]: https://github.com/earthobservations/wetterdienst/compare/v0.125.0...v0.126.0
[0.125.0]: https://github.com/earthobservations/wetterdienst/compare/v0.124.0...v0.125.0
[0.124.0]: https://github.com/earthobservations/wetterdienst/compare/v0.123.0...v0.124.0
[0.123.0]: https://github.com/earthobservations/wetterdienst/compare/v0.122.0...v0.123.0
[0.122.0]: https://github.com/earthobservations/wetterdienst/compare/v0.121.1...v0.122.0
[0.121.1]: https://github.com/earthobservations/wetterdienst/compare/v0.121.0...v0.121.1
[0.121.0]: https://github.com/earthobservations/wetterdienst/compare/v0.120.0...v0.121.0
[0.120.0]: https://github.com/earthobservations/wetterdienst/compare/v0.119.0...v0.120.0
[0.119.0]: https://github.com/earthobservations/wetterdienst/compare/v0.118.0...v0.119.0
[0.118.0]: https://github.com/earthobservations/wetterdienst/compare/v0.117.0...v0.118.0
[0.117.0]: https://github.com/earthobservations/wetterdienst/compare/v0.116.0...v0.117.0
[0.116.0]: https://github.com/earthobservations/wetterdienst/compare/v0.115.0...v0.116.0
[0.115.0]: https://github.com/earthobservations/wetterdienst/compare/v0.114.3...v0.115.0
[0.114.3]: https://github.com/earthobservations/wetterdienst/compare/v0.114.2...v0.114.3
[0.114.2]: https://github.com/earthobservations/wetterdienst/compare/v0.114.1...v0.114.2
[0.114.1]: https://github.com/earthobservations/wetterdienst/compare/v0.114.0...v0.114.1
[0.114.0]: https://github.com/earthobservations/wetterdienst/compare/v0.113.0...v0.114.0
[0.113.0]: https://github.com/earthobservations/wetterdienst/compare/v0.112.0...v0.113.0
[0.112.0]: https://github.com/earthobservations/wetterdienst/compare/v0.111.0...v0.112.0
[0.111.0]: https://github.com/earthobservations/wetterdienst/compare/v0.110.0...v0.111.0
[0.110.0]: https://github.com/earthobservations/wetterdienst/compare/v0.109.0...v0.110.0
[0.109.0]: https://github.com/earthobservations/wetterdienst/compare/v0.108.0...v0.109.0
[0.108.0]: https://github.com/earthobservations/wetterdienst/compare/v0.107.0...v0.108.0
[0.107.0]: https://github.com/earthobservations/wetterdienst/compare/v0.106.0...v0.107.0
[0.106.0]: https://github.com/earthobservations/wetterdienst/compare/v0.105.0...v0.106.0
[0.105.0]: https://github.com/earthobservations/wetterdienst/compare/v0.104.0...v0.105.0
[0.104.0]: https://github.com/earthobservations/wetterdienst/compare/v0.103.0...v0.104.0
[0.103.0]: https://github.com/earthobservations/wetterdienst/compare/v0.102.0...v0.103.0
[0.102.0]: https://github.com/earthobservations/wetterdienst/compare/v0.101.0...v0.102.0
[0.101.0]: https://github.com/earthobservations/wetterdienst/compare/v0.100.0...v0.101.0
[0.100.0]: https://github.com/earthobservations/wetterdienst/compare/v0.99.0...v0.100.0
[0.99.0]: https://github.com/earthobservations/wetterdienst/compare/v0.98.0...v0.99.0
[0.98.0]: https://github.com/earthobservations/wetterdienst/compare/v0.97.0...v0.98.0
[0.97.0]: https://github.com/earthobservations/wetterdienst/compare/v0.96.0...v0.97.0
[0.96.0]: https://github.com/earthobservations/wetterdienst/compare/v0.95.1...v0.96.0
[0.95.1]: https://github.com/earthobservations/wetterdienst/compare/v0.95.0...v0.95.1
[0.95.0]: https://github.com/earthobservations/wetterdienst/compare/v0.94.0...v0.95.0
[0.94.0]: https://github.com/earthobservations/wetterdienst/compare/v0.93.0...v0.94.0
[0.93.0]: https://github.com/earthobservations/wetterdienst/compare/v0.92.0...v0.93.0
[0.92.0]: https://github.com/earthobservations/wetterdienst/compare/v0.91.0...v0.92.0
[0.91.0]: https://github.com/earthobservations/wetterdienst/compare/v0.90.0...v0.91.0
[0.90.0]: https://github.com/earthobservations/wetterdienst/compare/v0.89.0...v0.90.0
[0.89.0]: https://github.com/earthobservations/wetterdienst/compare/v0.88.0...v0.89.0
[0.88.0]: https://github.com/earthobservations/wetterdienst/compare/v0.87.0...v0.88.0
[0.87.0]: https://github.com/earthobservations/wetterdienst/compare/v0.86.0...v0.87.0
[0.86.0]: https://github.com/earthobservations/wetterdienst/compare/v0.85.0...v0.86.0
[0.85.0]: https://github.com/earthobservations/wetterdienst/compare/v0.84.0...v0.85.0
[0.84.0]: https://github.com/earthobservations/wetterdienst/compare/v0.83.0...v0.84.0
[0.83.0]: https://github.com/earthobservations/wetterdienst/compare/v0.82.0...v0.83.0
[0.82.0]: https://github.com/earthobservations/wetterdienst/compare/v0.81.0...v0.82.0
[0.81.0]: https://github.com/earthobservations/wetterdienst/compare/v0.80.0...v0.81.0
[0.80.0]: https://github.com/earthobservations/wetterdienst/compare/v0.79.0...v0.80.0
[0.79.0]: https://github.com/earthobservations/wetterdienst/compare/v0.78.0...v0.79.0
[0.78.0]: https://github.com/earthobservations/wetterdienst/compare/v0.77.1...v0.78.0
[0.77.1]: https://github.com/earthobservations/wetterdienst/compare/v0.77.0...v0.77.1
[0.77.0]: https://github.com/earthobservations/wetterdienst/compare/v0.76.1...v0.77.0
[0.76.1]: https://github.com/earthobservations/wetterdienst/compare/v0.76.0...v0.76.1
[0.76.0]: https://github.com/earthobservations/wetterdienst/compare/v0.75.0...v0.76.0
[0.75.0]: https://github.com/earthobservations/wetterdienst/compare/v0.74.0...v0.75.0
[0.74.0]: https://github.com/earthobservations/wetterdienst/compare/v0.73.0...v0.74.0
[0.73.0]: https://github.com/earthobservations/wetterdienst/compare/v0.72.0...v0.73.0
[0.72.0]: https://github.com/earthobservations/wetterdienst/compare/v0.71.0...v0.72.0
[0.71.0]: https://github.com/earthobservations/wetterdienst/compare/v0.70.0...v0.71.0
[0.70.0]: https://github.com/earthobservations/wetterdienst/compare/v0.69.0...v0.70.0
[0.69.0]: https://github.com/earthobservations/wetterdienst/compare/v0.68.0...v0.69.0
[0.68.0]: https://github.com/earthobservations/wetterdienst/compare/v0.67.0...v0.68.0
[0.67.0]: https://github.com/earthobservations/wetterdienst/compare/v0.66.1...v0.67.0
[0.66.1]: https://github.com/earthobservations/wetterdienst/compare/v0.66.0...v0.66.1
[0.66.0]: https://github.com/earthobservations/wetterdienst/compare/v0.65.0...v0.66.0
[0.65.0]: https://github.com/earthobservations/wetterdienst/compare/v0.64.0...v0.65.0
[0.64.0]: https://github.com/earthobservations/wetterdienst/compare/v0.63.0...v0.64.0
[0.63.0]: https://github.com/earthobservations/wetterdienst/compare/v0.62.0...v0.63.0
[0.62.0]: https://github.com/earthobservations/wetterdienst/compare/v0.61.0...v0.62.0
[0.61.0]: https://github.com/earthobservations/wetterdienst/compare/v0.60.0...v0.61.0
[0.60.0]: https://github.com/earthobservations/wetterdienst/compare/v0.59.3...v0.60.0
[0.59.3]: https://github.com/earthobservations/wetterdienst/compare/v0.59.2...v0.59.3
[0.59.2]: https://github.com/earthobservations/wetterdienst/compare/v0.59.1...v0.59.2
[0.59.1]: https://github.com/earthobservations/wetterdienst/compare/v0.59.0...v0.59.1
[0.59.0]: https://github.com/earthobservations/wetterdienst/compare/v0.58.1...v0.59.0
[0.58.1]: https://github.com/earthobservations/wetterdienst/compare/v0.58.0...v0.58.1
[0.58.0]: https://github.com/earthobservations/wetterdienst/compare/v0.57.1...v0.58.0
[0.57.1]: https://github.com/earthobservations/wetterdienst/compare/v0.57.0...v0.57.1
[0.57.0]: https://github.com/earthobservations/wetterdienst/compare/v0.56.2...v0.57.0
[0.56.2]: https://github.com/earthobservations/wetterdienst/compare/v0.56.1...v0.56.2
[0.56.1]: https://github.com/earthobservations/wetterdienst/compare/v0.56.0...v0.56.1
[0.56.0]: https://github.com/earthobservations/wetterdienst/compare/v0.55.2...v0.56.0
[0.55.2]: https://github.com/earthobservations/wetterdienst/compare/v0.55.1...v0.55.2
[0.55.1]: https://github.com/earthobservations/wetterdienst/compare/v0.55.0...v0.55.1
[0.55.0]: https://github.com/earthobservations/wetterdienst/compare/v0.54.1...v0.55.0
[0.54.1]: https://github.com/earthobservations/wetterdienst/compare/v0.54.0...v0.54.1
[0.54.0]: https://github.com/earthobservations/wetterdienst/compare/v0.53.0...v0.54.0
[0.53.0]: https://github.com/earthobservations/wetterdienst/compare/v0.52.0...v0.53.0
[0.52.0]: https://github.com/earthobservations/wetterdienst/compare/v0.51.0...v0.52.0
[0.51.0]: https://github.com/earthobservations/wetterdienst/compare/v0.50.0...v0.51.0
[0.50.0]: https://github.com/earthobservations/wetterdienst/compare/v0.49.0...v0.50.0
[0.49.0]: https://github.com/earthobservations/wetterdienst/compare/v0.48.0...v0.49.0
[0.48.0]: https://github.com/earthobservations/wetterdienst/compare/v0.47.1...v0.48.0
[0.47.1]: https://github.com/earthobservations/wetterdienst/compare/v0.47.0...v0.47.1
[0.47.0]: https://github.com/earthobservations/wetterdienst/compare/v0.46.0...v0.47.0
[0.46.0]: https://github.com/earthobservations/wetterdienst/compare/v0.45.2...v0.46.0
[0.45.2]: https://github.com/earthobservations/wetterdienst/compare/v0.45.1...v0.45.2
[0.45.1]: https://github.com/earthobservations/wetterdienst/compare/v0.45.0...v0.45.1
[0.45.0]: https://github.com/earthobservations/wetterdienst/compare/v0.44.0...v0.45.0
[0.44.0]: https://github.com/earthobservations/wetterdienst/compare/v0.43.0...v0.44.0
[0.43.0]: https://github.com/earthobservations/wetterdienst/compare/v0.42.1...v0.43.0
[0.42.1]: https://github.com/earthobservations/wetterdienst/compare/v0.42.0...v0.42.1
[0.42.0]: https://github.com/earthobservations/wetterdienst/compare/v0.41.1...v0.42.0
[0.41.1]: https://github.com/earthobservations/wetterdienst/compare/v0.41.0...v0.41.1
[0.41.0]: https://github.com/earthobservations/wetterdienst/compare/v0.40.0...v0.41.0
[0.40.0]: https://github.com/earthobservations/wetterdienst/compare/v0.39.0...v0.40.0
[0.39.0]: https://github.com/earthobservations/wetterdienst/compare/v0.38.0...v0.39.0
[0.38.0]: https://github.com/earthobservations/wetterdienst/compare/v0.37.0...v0.38.0
[0.37.0]: https://github.com/earthobservations/wetterdienst/compare/v0.36.0...v0.37.0
[0.36.0]: https://github.com/earthobservations/wetterdienst/compare/v0.35.0...v0.36.0
[0.35.0]: https://github.com/earthobservations/wetterdienst/compare/v0.34.0...v0.35.0
[0.34.0]: https://github.com/earthobservations/wetterdienst/compare/v0.33.0...v0.34.0
[0.33.0]: https://github.com/earthobservations/wetterdienst/compare/v0.32.4...v0.33.0
[0.32.4]: https://github.com/earthobservations/wetterdienst/compare/v0.32.3...v0.32.4
[0.32.3]: https://github.com/earthobservations/wetterdienst/compare/v0.32.2...v0.32.3
[0.32.2]: https://github.com/earthobservations/wetterdienst/compare/v0.32.1...v0.32.2
[0.32.1]: https://github.com/earthobservations/wetterdienst/compare/v0.32.0...v0.32.1
[0.32.0]: https://github.com/earthobservations/wetterdienst/compare/v0.31.1...v0.32.0
[0.31.1]: https://github.com/earthobservations/wetterdienst/compare/v0.31.0...v0.31.1
[0.31.0]: https://github.com/earthobservations/wetterdienst/compare/v0.30.1...v0.31.0
[0.30.1]: https://github.com/earthobservations/wetterdienst/compare/v0.30.0...v0.30.1
[0.30.0]: https://github.com/earthobservations/wetterdienst/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/earthobservations/wetterdienst/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/earthobservations/wetterdienst/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/earthobservations/wetterdienst/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/earthobservations/wetterdienst/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/earthobservations/wetterdienst/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/earthobservations/wetterdienst/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/earthobservations/wetterdienst/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/earthobservations/wetterdienst/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/earthobservations/wetterdienst/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/earthobservations/wetterdienst/compare/v0.20.4...v0.21.0
[0.20.4]: https://github.com/earthobservations/wetterdienst/compare/v0.20.3...v0.20.4
[0.20.3]: https://github.com/earthobservations/wetterdienst/compare/v0.20.2...v0.20.3
[0.20.2]: https://github.com/earthobservations/wetterdienst/compare/v0.20.1...v0.20.2
[0.20.1]: https://github.com/earthobservations/wetterdienst/compare/v0.20.0...v0.20.1
[0.20.0]: https://github.com/earthobservations/wetterdienst/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/earthobservations/wetterdienst/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/earthobservations/wetterdienst/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/earthobservations/wetterdienst/compare/v0.16.1...v0.17.0
[0.16.1]: https://github.com/earthobservations/wetterdienst/compare/v0.16.0...v0.16.1
[0.16.0]: https://github.com/earthobservations/wetterdienst/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/earthobservations/wetterdienst/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/earthobservations/wetterdienst/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/earthobservations/wetterdienst/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/earthobservations/wetterdienst/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/earthobservations/wetterdienst/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/earthobservations/wetterdienst/compare/v0.11.1...v0.12.0
[0.11.1]: https://github.com/earthobservations/wetterdienst/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/earthobservations/wetterdienst/compare/v0.10.1...v0.11.0
[0.10.1]: https://github.com/earthobservations/wetterdienst/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/earthobservations/wetterdienst/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/earthobservations/wetterdienst/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/earthobservations/wetterdienst/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/earthobservations/wetterdienst/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/earthobservations/wetterdienst/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/earthobservations/wetterdienst/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/earthobservations/wetterdienst/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/earthobservations/wetterdienst/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/earthobservations/wetterdienst/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/earthobservations/wetterdienst/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/v0.1.0
