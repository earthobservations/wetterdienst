# Migrating from 0.139.0

What to change in your code, scripts and deployment to move from wetterdienst 0.139.0 to 0.176.0, collected from
the **Breaking** entries of the [changelog](../changelog.md) of the releases in between (0.140.0 to 0.176.0), grouped
by what you touch, and checked against the code. The numbers are the issues the changelog names (`GH-2626`); the
version says the release that made the change. For what stays stable from 1.0 on, see
[Compatibility](compatibility.md).

Most of what changed is refused with an error that names what to use instead, so the quickest way through is to
run your code on the new release and fix the errors one at a time: a renamed argument, attribute, option, query
parameter, column or parameter says `... was renamed to ...`. What cannot be refused is a change in the data
(a value, a unit, a timestamp), and a change in what happens on a failure; those are in
[Values, units and timestamps](#values-units-and-timestamps) and [Failures](#failures). If you come from a release
before 0.139.0, read the **Breaking** entries up to it first.

The web app is released as a pair with the backend: `app-v0.38.0` goes with 0.176.0. Upgrade both
([The web app and the image](compatibility.md#the-web-app-and-the-image)).

Two things that still worked in 0.172.0 are removed in 0.173.0, earlier than announced for 1.0.0:
`Wetterdienst(provider, network)` and `wetterdienst stripes values`. Write
`Wetterdienst.resolve(provider, network)` and `wetterdienst stripes image`
(both are in [The request](#the-request) and [Command line](#command-line) below). The import path of a request class
(`from wetterdienst.provider.dwd.observation import DwdObservationRequest`) does not move: it is frozen from 1.0.

## Installation

| Before | Now | Release, issue |
| --- | --- | --- |
| Python 3.10 | Python 3.11 or newer; pip on an older Python keeps resolving the last release that supports it | 0.145.0, GH-2568 |
| `export` extra with any xarray; `radarplus` with any xradar | `export` needs `xarray>=2025.6.0` (2024.6 cannot write Zarr), `radarplus` needs `xradar>=0.8` | 0.145.0, GH-2704 |
| `postgresql` extra installs psycopg2 | it installs psycopg 3; for `postgresql+psycopg2://` install `psycopg2-binary` yourself, and drop `+psycopg2` in the Docker image, which has psycopg 3 only | 0.140.0, GH-2202 |
| `.env` read in the locale's encoding | read as UTF-8; a `.env` in a Windows code page with a non-ASCII value raises `UnicodeDecodeError` on `Settings()`: save it as UTF-8 | 0.147.0, GH-2568 |
| `fsspec_client_kwargs` (or `WD_FSSPEC_CLIENT_KWARGS`) replaced the defaults | it is merged into them, `headers` one level deep; give `"timeout": None` for aiohttp's own timeout, a `User-Agent` of your own to replace ours | 0.140.0, GH-2269 |

## Python API

### The request

| Before | Now | Release, issue |
| --- | --- | --- |
| `start_date=`, `end_date=` of every request, `DwdRadarValues`; `.start_date`, `.end_date` | `start=`, `end=`; `.start`, `.end`. The old keyword is a `TypeError` that names the new one | 0.142.0, GH-2437 |
| `DwdWeatherAlertRequest(date=...)`, `.date` | `timestamp=...`, `.timestamp` | 0.142.0, GH-2438 |
| `end="2026-01-31"` or a `datetime.date` ended at midnight and left the day out | a date without a time is the whole day, to 23:59:59.999999 UTC, as REST's `timestamp` always read it. A `datetime` or a string with a time is still that instant: end a window at midnight with `end="2026-01-31T00:00:00"`. `start="2020-05"` and `end="2020-05"` name the month and `"2020"` the year | 0.160.0, GH-3133, GH-3155 |
| `start=2020` (an int) raised `AttributeError` | a `TypeError` | 0.155.0, GH-2636 |
| `Wetterdienst(provider, network)`, the constructor form that returns a class | a `TypeError` that names the replacement, since 0.173.0: write `Wetterdienst.resolve(provider, network)`. `dwd/radar` and `dwd/alerts` are no `TimeseriesRequest`: `Wetterdienst.resolve` refuses them with an `ApiNotFoundError` that names `Wetterdienst.resolve_standalone(provider, network)`; `Wetterdienst.is_standalone(provider, network)` tells which is which | 0.173.0, GH-3128 (deprecated in 0.156.0, GH-3045; announced for removal in 1.0.0) |
| `Wetterdienst.get_network_names("foo")` raised `KeyError`, `discover()` returned `{}` for a resolution or dataset the network lacks | `ApiNotFoundError` and `MetadataNotFoundError`, both a `NotFoundError` and a `LookupError`; catch those instead of `KeyError` | 0.155.0, GH-2636 |
| a parameter the provider does not have was logged and skipped | `InvalidParameterError` (a `RequestError`) naming each with its close match. Fix the name, or pass `on_unknown="warn"` for the old behaviour. When none resolves it is the same error, no longer `NoParametersFoundError`: catch `RequestError` for both | 0.155.0, GH-2636 |
| `DwdDmoRequest.available_issues` listed every lead time | lists `lead_time="short"`; pass `lead_time="long"`, or `lead_time=None` for all | 0.140.0, GH-2009 |
| a DMO parameter its lead time does not carry gave an empty frame | `ParameterNotCarriedError` (a `ValueError`) naming the lead time that does | 0.140.0, GH-1976 |
| a SWSMOS `issue` DWD does not hold gave no rows | `IssueNotFoundError` | 0.140.0, GH-2324 |
| `DwdRadarParameter.HG_REFLECTIVITY`, `PG_REFLECTIVITY`, `PX_REFLECTIVITY`, `PF_REFLECTIVITY`, `RE_REFLECTIVITY`, `RQ_REFLECTIVITY` | removed: DWD publishes no file of them (`composite/hg`, `composite/pg`, `sites/pf`, `radvor/re`, `radvor/rq` empty, `sites/px` stale files of one site, 2026-10-22); `RADAR_PARAMETERS_RADVOR` is gone with them. A request by name is an `InvalidEnumerationError` that says so; use `RV_REFLECTIVITY` or `WN_REFLECTIVITY`, `PX250_REFLECTIVITY` | 0.167.0, GH-3279 |
| `DwdRadarValues` for `RV_REFLECTIVITY`, `WN_REFLECTIVITY` (RADOLAN binary in a `.tar.bz2` or `.bz2`); for `LMAX_VOLUME_SCAN`, `PE_ECHO_TOP`, `PR_VELOCITY`, `PX250_REFLECTIVITY`, `PZ_CAPPI` with `fmt=BINARY` or `BUFR` | ODIM HDF5: the composites a `.tar` of one file per lead time, the site products one file each; decode with h5py or wradlib's ODIM reader. `fmt` can be left out, and a format the product is not served in is a `RequestError` naming the one it is | 0.167.0, GH-3279 |
| `read_radar_bufr`, `DwdRadarDataFormat.BUFR`, `RadarResult.df`, the `read_bufr` setting (and its environment variable) | removed: DWD publishes no radar product as BUFR (its index of `weather/radar` holds no BUFR file, 2026-10-22). `fmt="bufr"` is an `InvalidEnumerationError` and `Settings(read_bufr=...)` a `ValueError`, each saying why; read the ODIM HDF5 `result.data`. The `bufr` and `eccodes` extras and the BUFR of `dwd/road` are unchanged; `radarplus` no longer installs `pybufrkit` and `bitstring` | 0.168.0, GH-3287 |
| `sql`, `sql_values` could read files, URLs and DuckDB settings and run a statement | a DuckDB connection with only the frame: one condition (no `;`, `ORDER BY`, `LIMIT`), one thread, a memory limit. Join or sort the returned frame with polars | 0.140.0, GHSA-rpwr-qmm5-m9wp |

### The results

| Before | Now | Release, issue |
| --- | --- | --- |
| `StationsResult.stations`, `StationsResult(stations=...)` | `StationsResult.request`, `request=`; the stations were and are in `.df`. `values.stations.request` is the request behind a values result | 0.156.0, GH-2626 |
| `stations.values.all()`, `.values.query()`, `.history.query()` | `stations.values().all()`, `.values().query()`, `.history().query()`: `values` and `history` are methods | 0.156.0, GH-2626 |
| `result.df = ...` | results are frozen: `FrozenInstanceError` | 0.156.0, GH-2626 |
| `values.filter_by_date(d)`, `values.filter_by_sql(s)` replaced the frame and returned it | `values = values.filtered_by_date(d)`, `values = values.filtered_by_sql(s)` return a new result; `.df` is the frame | 0.156.0, GH-2626 |
| `ValuesResult.values`, `ValuesResult(values=...)` | gone: get a reader from `stations.values()`. `df_stations` names the stations that have a row, also after `filtered_by_sql`, and `InterpolatedValuesResult` and `SummarizedValuesResult` have it | 0.156.0, GH-2626 |
| `ValuesResult(df, stations)` | keyword only: `ValuesResult(stations=..., df=...)`, for all five results | 0.156.0, GH-3044 |
| `StationsResult.df_all`, `.stations_filter`, `.rank` | private, `_df_all`, `_stations_filter`, `_rank`: read `df` | 0.160.0, GH-3128 |
| `StationsResult.get_metadata()` | gone: `to_dict(with_metadata=True)`, `to_json`, `to_geojson` write the block; `request.metadata` is the provider's `MetadataModel` (`request.metadata.license`); `Info().to_dict()` is the library's | 0.158.0, GH-3047 |
| `TimeseriesValues.stations_counter`, `.stations_collected`, and their constructor arguments | gone: the stations a query returned are in the `station_id` column | 0.158.0, GH-3037 |
| `to_geojson`, `to_ogc_feature_collection`, `to_plot` took and dropped any keyword | the arguments they declare: `to_geojson(with_metdata=True)` is a `TypeError`. `to_image` takes `fmt`, `width`, `height`, `scale`, `max_side`. `to_format(fmt, **kwargs)` still gives each format the ones it takes | 0.156.0, GH-3043 |
| `Wetterdienst.discover()`, `/api/coverage`, `wetterdienst about coverage` listed `valid` for every network | `valid` is gone: read `configured`, and ask `Wetterdienst.is_valid(api)`, `/api/auth` or `wetterdienst about auth` whether a provider accepts the credentials | 0.147.0 (GH-2564), 0.155.0 (GH-2641) |
| `is_valid()` of `metno/frost` and `aemet/observation` was `False` when it could not tell | `False` only when the provider rejects the credential, `None` when it could not tell (no network, TLS, timeout, 429, 5xx); treat `None` as unknown | 0.147.0, GH-2550, GH-2562 |

### Settings and options

| Before | Now | Release, issue |
| --- | --- | --- |
| `Settings(ts_shape=...)` and the other 14 `ts_*` settings, `settings.ts_*`, `settings={"ts_...": ...}` | a `ValidationError` that names the option: `options=Options(shape=...)` or `options={"shape": ...}` on the request. The `WD_TS_*` variables are unchanged. Warned from 0.148.0, removed in 0.160.0 | 0.160.0, GH-3128, GH-2639 |
| `geo_station_distance_resolution_factors={"6_hour": ...}`, `Resolution` `6_hour` | `{"6_hours": ...}`; the value is `6_hours`, as `10_minutes` is (`metno/frost`) | 0.155.0, GH-2641, GH-2561 |
| a `ts_geo_station_distance` override keyed by an old `_mean_` name | the row takes the default radius: key the override by the new name | 0.145.0, GH-2651, GH-2657, GH-2660 |
| `ts_skip_threshold` above 1 or 0 was accepted and skipped every station | refused: such a `WD_TS_SKIP_THRESHOLD` fails every `Settings()`; `/api/values` answers a `skip_threshold` of 0 with a 422 | 0.140.0, GH-2334 |
| the REST API and MCP accepted `sql` and `sql_values` | a 403 unless the server runs with `WD_RESTAPI_SQL=true` | 0.140.0, GHSA-rpwr-qmm5-m9wp |

### Export targets

| Before | Now | Release, issue |
| --- | --- | --- |
| an `influxdbs://` or `influxdb1s://` target accepted any TLS certificate of the server | the certificate is verified: a self-signed or private-CA server fails with an SSL error; set `REQUESTS_CA_BUNDLE` to a CA bundle that includes it (or its CA) | 0.174.0, GH-3342 |
| `duckdb:////home/me/my%20data/obs.duckdb` opened `obs.duckdb` in a directory named `my%20data` | the path is a URI path, as in `file://`: it opens `/home/me/my data/obs.duckdb`; write a literal `%20` as `%2520` | 0.143.0, GH-2515 |
| an `@` in an InfluxDB org, password or token, a `%` in an InfluxDB database or a CrateDB schema | the target is read as SQLAlchemy reads it: write `@` as `%40` and a literal `%` followed by two hex digits as `%25` | 0.140.0, GH-2248 |
| `influxdb3://` went to https on port 443 | `influxdb3://` is http and `influxdb3s://` https, on the target's port or 8181 (http) and 443 (https); write InfluxDB Cloud as `influxdb3s://` | 0.140.0, GH-2279 |

## Frames and columns

| Before | Now | Release, issue |
| --- | --- | --- |
| station columns `start_date`, `end_date` (every provider, the exports, the REST and MCP stations, OGC properties) | `start_timestamp`, `end_timestamp`; rename the columns of a database table you append stations to; a `sql` filter on the old name fails naming the new | 0.142.0, GH-2439 |
| history records `start_date`, `end_date` (Python `History`, `/api/history`, the MCP and CLI `history`) | `valid_from`, `valid_to` | 0.142.0, GH-2440 |
| `end_timestamp` was the time of the call or the day before for a station the provider gives no end (`eaufrance/hubeau`, `dwd/observation` 1-minute precipitation historical) | null: a station the provider has not closed | 0.142.0, GH-2482 |
| the current position in a DWD station history had a `valid_to` of the time the history was read | null: a position that still applies | 0.142.0, GH-2474 |
| the `quality` number (wide: `<parameter>_quality`) | one nullable string `quality_flags` (wide: `<parameter>_quality_flags`), every flag the source publishes, comma-separated: the flag plain, further kinds as `kind:code` (`G,measurement:T,source:7`), the text of a missing value as `raw:<text>`. Where you used the number, `pl.col("quality_flags").cast(pl.Int64, strict=False)` (`Z` of IMGW is no number). Interpolated and summarized frames have no flags column | 0.147.0, GH-2018, GH-2755, GH-2757, GH-2758 |
| `station_id`, `resolution`, `dataset`, `parameter` of `.values().all().df` were polars `Enum` | `String`, as in an empty, an interpolated and a summarized result: drop the casts back to `String`; take the categories from the data | 0.155.0, GH-2633 |
| timestamps in History, alerts, issue lists and stripes as `1926-05-01T00:00:00+00:00`, in CSV `+0000` | the one form of values, ISO 8601 in UTC to the microsecond, `2026-09-01T00:00:00.000000+00:00`: read with a parser that takes a fraction | 0.155.0, GH-2633 |
| `dmi/observation` `region` held `DNK`, `GRL`, `FRO`; `imgw/meteorology` `region` held the catchment (`Odra (1)`) | `region` is null; `country` (DMI) and `river` (IMGW) are the new columns | 0.147.0, GH-2019 |
| Hub'Eau stations listed the gauge's zero as `elevation` | `gauge_zero` | 0.140.0, GH-2020 |
| `ea/hydrology` `quality_flags` was the quality alone (`Good`) | `Good,completeness:Complete` or `Good,completeness:Incomplete` for daily readings that carry it: use `str.starts_with('Good')`, not `== 'Good'` | 0.153.0, GH-2762 |
| `imgw/meteorology` `daily/precipitation` left out a day the file leaves out of a month the station reports in | 0 mm with `quality` 11 for that day: drop quality 11 to get the rows as before | 0.140.0, GH-2000 |
| a null whose source wrote a missing-value marker (`-999`) had nothing to tell it from no reading (not marked Breaking) | the text the source wrote is the last token of `quality_flags`, `raw:-999` (`3,raw:-999`); the long frame drops null rows by default, so read the token with `drop_nulls=False` or in the wide shape, where a null `quality_flags` no longer means "no flag" for these rows | 0.147.0 |
| a table `to_target` wrote under the old column or parameter names | write it anew: a wide table holds the old names, a long one the old `parameter` values | 0.140.0 (GH-1977), 0.145.0 (GH-2696) |

## Failures

What happens when a download fails or a request is refused changed, so a `try` that relied on the old behaviour
needs a new `except`. The classes are those of [Errors](python-api.md#errors).

| Before | Now | Release, issue |
| --- | --- | --- |
| a download followed a redirect to another registered domain, and one from `https` down to `http`; the links an answer names (next page, `datos`, asset, measure) were fetched wherever they pointed | a redirect to another registered domain is not followed, nor, for a session that holds a credential, one from `https` down to `http`: the download fails with a `DownloadError`. A session holds a credential with a credential header, `auth`, cookies, `trust_env`, a proxy or middleware among its `fsspec_client_kwargs`; one without any still follows an `http` hop inside the provider's domain (withdrawn in 0.175.0, see the next row). Nothing else to change for the providers. The links are fetched only at the provider's own domain, over `https` (KNMI and Météo-France also at the object store of their files) | 0.174.0, GH-3338, GH-3339, GH-3398 |
| a session without a credential followed a redirect from `https` down to `http` (0.174.0), and data.gouv.fr's maintenance redirect to `http://sorry.data.gouv.fr` was followed to its 503 page | `https` never steps down to `http`, whatever the session holds: the download fails with a `DownloadError`. The hop it was allowed for was that maintenance page, which no provider needs. A request that data.gouv.fr redirects to it fails with a `DownloadError` saying that data.gouv.fr is in maintenance (REST 502), and is not asked again. Nothing to change | 0.175.0, GH-3400 |
| a download or an archive of any size was read into memory | a download over 2 GiB or one hour, and an archive that unpacks to more than its ceiling (1 GiB; 256 MiB for DWD SWSMOS and alerts, 2 GiB for DWD radar, 4 GiB for the KML of MOSMIX and DMO, 8 GiB for Météo-France climate files), fail with a `DownloadError` (REST 502); `download_file(max_bytes=...)` sets the size per call | 0.174.0, GH-3340 (not marked Breaking; the files served today are below the figures) |
| a failed download raised the stored error (`FSTimeoutError`, `ClientResponseError`, `FileNotFoundError`, aiohttp's connection errors) | `wetterdienst.exceptions.DownloadError`, `Failed to download <url>: <reason>`, the original on `__cause__`; catch `DownloadError` or `UpstreamError` | 0.142.0, GH-2460 |
| a timeout (`dwd/observation`, `dwd/derived`, `imgw`) or a timeout or 5xx (`dwd/phenology`, `poi`, `swsmos`, `chmi`, `fmi`, `ipma`, `dmi`, `rmi`, `metoffice`, `lhmt`, `meteofrance`) in the values was logged and read as no data. Not marked Breaking | `DownloadError`. A 404 still gives no data at most of them | 0.141.0 (GH-2430), 0.142.0 (GH-2461) |
| a timeout, a dropped connection, a cut-short body or a 5xx in the values of `aemet`, `knmi`, `smhi` (0.155.0) and `metno/frost` and the station lists of AEMET and KNMI (0.157.0) was logged and read as no data; a TLS failure too | `DownloadError`; REST 502 (504 after a timeout), the command line exits 1. A 404, a 412 and other 4xx but a refused credential stay the empty result | 0.155.0 (GH-2965), 0.157.0 (GH-3022) |
| the token exchange of `metoffice/observation` that did not answer was a warning and an empty result | `DownloadError` | 0.158.0, GH-3022 |
| AEMET's rate limit that outlasts the retries (429) skipped the chunk | `DownloadError`, the 429 its `__cause__`; retry later | 0.159.0, GH-2989 |
| a remote listing that was reset, dropped, timed out or was refused raised the raw aiohttp error; a TLS failure the bare `ssl.SSLError` | `DownloadError` naming the URL, the original on `__cause__`. A connection that cannot be made stays `NoInternetError` | 0.159.0 (GH-3004), 0.160.0 (GH-3099) |
| reading a `dwd/mosmix` or `dwd/dmo` run that failed raised a bare `ssl.SSLError` (TLS), the aiohttp or fsspec error (a reset, timeout, 5xx or cut-short body) or `FileNotFoundError` (a missing run, or any failure with the cache disabled) | `DownloadError`, or `NoInternetError` where no connection could be made, the failure on `__cause__`; REST answers 502, 503 or 504, not 500 | 0.161.0, GH-3120 |
| a credential the provider rejects (401, 403) gave an empty result and a warning | `CredentialRejectedError`, a `ConfigurationError` and a `PermissionError`, in the values and station lists of `metno/frost`, `aemet`, `knmi`, `metoffice` | 0.157.0, GH-3018 |
| no connection gave an empty frame, for `dwd/observation` a bare `FileNotFoundError`; `knmi`, `aemet`, `lhmt`, `dmi` returned what they had read before the connection dropped | `NoInternetError`, naming the URL, the connection error on `__cause__`, for every provider; catch it where an empty result is wanted offline | 0.155.0, GH-2640 |
| `DwdWeatherAlertRequest` raised `OSError` for a snapshot that did not download or is no zip | `DownloadError`; a granularity, language or timestamp it cannot read is a `RequestError` | 0.156.0, GH-2985 |
| an invalid time interval, enumeration or bounding box raised a bare `ValueError`, `IndexError` or `OverflowError`; a point outside UTM raised `utm.error.OutOfRangeError` | `InvalidTimeIntervalError`, `InvalidEnumerationError`, `InvalidBoundingBoxError`, `LocationOutOfRangeError`, `IssueNotFoundError`, each still a `ValueError` or `IndexError`; the `9999-12-31` day and the UTM range are those two | 0.140.0, GH-2252 |

## Parameters renamed

A canonical parameter was renamed where its name claimed another statistic, window or quantity than its source
states. The old name is refused and the error names the new one (`'wind_speed' was renamed to 'wind_speed_mean' in
this dataset`); the same applies to a name in a request, in a `parameter` filter, in a wide column and in a
`geo_station_distance` key. A name the source itself uses still selects its row (`wind_speed` of `metno/frost`,
`wind_direction` of `eccc/observation` and of the Met Office hourly weather) and comes back under the new name. The
rule is [The statistic in a name](../data/parameters.md#the-statistic-in-a-name), and its page lists every row of the
0.176.0 renames by network, resolution and dataset.

Moves of the same parameter between 0.145.0 and 0.176.0 are shown from the name of 0.139.0 to the name of 0.176.0.

These are hard breaks of the 0.x releases and stay refused, with their hint, after 1.0. A rename after 1.0 is different:
the old name keeps working as an alias, with a warning, for at least two minor releases and goes only in a major
release ([Parameter names](compatibility.md#parameter-names-units-and-timestamps)).

### The statistic in the name

| Name in 0.139.0 | Name now | Where | Release, issue |
| --- | --- | --- | --- |
| `temperature_air_mean_2m` | `temperature_air_2m` | the sub-daily rows whose source states no mean (22 networks: DWD 10-minute, hourly and sub-daily, MOSMIX, DMO, POI, road, SWSMOS; AEMET, CHMI, ECCC, FMI, Geosphere, KNMI, LHMT, Météo-France, MeteoSwiss, met.no, Met Office, NOAA GHCN hourly, NWS, SMHI, WSV; the road, SWSMOS and WSV air temperatures were renamed again, see the rows below) | 0.145.0, GH-2651, GH-2657, GH-2660 |
| `temperature_dew_point_mean_2m`, `temperature_air_mean_0_05m`, `temperature_wet_mean_2m`, `temperature_radiant_mean_2m` | `temperature_dew_point_2m`, `temperature_air_0_05m`, `temperature_wet_2m`, `temperature_radiant_2m` | the same rows (the road and SWSMOS dew points were renamed again, see the rows below) | 0.145.0 |
| `temperature_soil_mean_0_02m` to `temperature_soil_mean_2m` | `temperature_soil_0_02m` to `temperature_soil_2m` | the same rows | 0.145.0 |
| `temperature_surface_mean` | `temperature_surface` | `dwd/road`, `dwd/swsmos` | 0.145.0, GH-2660 |
| `wind_speed`, `wind_direction` | `wind_speed_mean`, `wind_direction_mean` | rows whose source states the mean of the row's interval (46 rows, 13 networks) | 0.160.0, GH-3151 |
| `wind_speed`, `wind_direction` | `wind_speed_mean_last_10min`, `wind_direction_mean_last_10min` | hourly means over the last 10 minutes: `aemet`, `dwd` (wind synoptic, POI), `fmi`, `knmi` (direction), `meteofrance` (observation and SYNOP), `metno/frost`, `smhi` | 0.145.0 to 0.160.0, GH-2697, GH-2707, GH-2733, GH-2835, GH-3151 |
| `wind_speed`, `wind_direction` | `wind_speed_mean_last_2min`, `wind_direction_mean_last_2min` | `nws/observation`; `eccc/observation` hourly direction | 0.155.0, GH-2837, GH-2838 |
| `humidity_relative`, `pressure_air_site`, `pressure_air_sea_level`, `pressure_vapor`, `cloud_cover_total`, `visibility` | the same with `_mean` | rows whose source states a mean (81 rows, 14 networks, e.g. DWD daily and monthly, MeteoSwiss, DMI, IMGW, MET Norway); NOAA GHCN's average cloudiness is `cloud_cover_total_mean_midnight_to_midnight` and its three siblings | 0.160.0, GH-3151 |
| `radiation_global_intensity`, `radiation_sky_long_wave_intensity`, `radiation_sky_short_wave_diffuse_intensity`, `precipitation_intensity`, `snow_depth`, `wind_force_beaufort` | the same with `_mean` | where the source states a mean (35 rows, 6 networks); `soil_moisture_<cover>_<soil>_<depth>` of DWD derived is `soil_moisture_mean_<cover>_<soil>_<depth>`; `wsv/pegel` stayed, and has no `precipitation_intensity` since 0.166.0 (see below) | 0.160.0, GH-3151 |
| `temperature_air_mean_2m` | `temperature_air_mean_minmax_2m` | the mean computed as (maximum + minimum) / 2: `eccc/observation` daily and monthly, `geosphere/observation` daily (Geosphere monthly keeps `temperature_air_mean_2m`) | 0.155.0, GH-2839 |
| `count_days_valid_temperature_air_mean_2m`, `temperature_air_mean_2m_normal` | `count_days_valid_temperature_air_mean_minmax_2m`, `temperature_air_mean_minmax_2m_normal` | `eccc/observation` monthly | 0.156.0, GH-3017 |
| `temperature_air_max_2m`, `temperature_air_min_2m` | `temperature_air_max_2m_last_12h`, `temperature_air_min_2m_last_12h` | `dwd/mosmix`, `dwd/dmo` (`tx`, `tn`) | 0.145.0, GH-2614 |
| `temperature_air_max_2m`, `temperature_air_min_2m` | `temperature_air_max_2m_mean`, `temperature_air_min_2m_mean` | `chmi/observation` monthly and annual (the mean of the daily extremes) | 0.145.0, GH-2614 |
| `temperature_air_max_2m_multiday`, `temperature_air_min_2m_multiday` | `temperature_air_max_2m`, `temperature_air_min_2m` | `aemet/observation` monthly and annual | 0.145.0, GH-2614 |
| `temperature_air_mean_0_05m` | `temperature_surface_mean` | `rmi/observation` (grass thermometer) | 0.155.0, GH-2846 |
| `error_absolute_temperature_air_mean_2m`, `error_absolute_temperature_dew_point_mean_2m` | `error_absolute_temperature_air_2m`, `error_absolute_temperature_dew_point_2m` | `dwd/mosmix` hourly large | 0.152.0, GH-2659 |

A mean that a source states keeps its `_mean_` name in sub-daily rows too (IPMA, MeteoSwiss hourly means, KNMI 10-minute
`tg` and `tb`, DMI and RMI). If a rule above does not tell you the name, request the old one and read the error.

### Windows, gusts and other quantities

| Name in 0.139.0 | Name now | Where | Release, issue |
| --- | --- | --- | --- |
| `wind_gust_max` | `wind_gust_max_last_10min` | `fmi/observation` hourly, `meteofrance/synop`, `metoffice/observation` hourly weather, `nws/observation` | 0.155.0, GH-2836 |
| `wind_gust_max` | `wind_speed_rolling_mean_max` | `meteofrance/observation` hourly (`FXY` is the hour's highest 10-minute mean, no gust) | 0.149.0, GH-2834 |
| `wind_direction_gust_max` | not served | `meteofrance/observation` hourly (`DXY` is the direction of no gust) | 0.155.0, GH-2836 |
| `wind_speed_rolling_mean_max_yesterday` | `wind_speed_rolling_mean_max_last_6h` | `dwd/poi` | 0.155.0, GH-2817 |
| `pressure_air_site_reduced` | `pressure_air_sea_level` | `dwd/mosmix`, `dwd/dmo` (`pppp`) | 0.155.0, GH-2840 |
| `pressure_air_site` | `pressure_air_site_reduced` | `nws/observation` (the altimeter setting) | 0.155.0, GH-2842 |
| `precipitation_amount` | `precipitation_amount_since_last_routine_report` | the METAR precipitation group: `noaa/ghcn` hourly, `nws/observation` | 0.156.0, GH-2841 |
| `precipitation_amount_last_6h` | `precipitation_amount_liquid_last_6h` | `dwd/swsmos` (`RR6`) | 0.155.0, GH-2845 |
| `probability_radiation_global_last_1h` | `radiation_global_relative_last_1h` | `dwd/mosmix` large (`rrad1`) | 0.155.0, GH-2843 |
| `weather_last_3h`, `weather_secondary_last_3h` | `weather_past`, `weather_secondary_past` | `dwd/poi` | 0.155.0, GH-2844 |
| `radiation_global_last_3h` | `radiation_short_wave_net_last_3h` | `dwd/dmo` `icon` (`rads3`, DWD's short-wave radiation balance of the last 3 hours, positive downward into the surface); the values and the unit are unchanged | 0.164.0, GH-2614 |
| `radiation_sky_long_wave_last_3h` | `radiation_long_wave_net_last_3h` | `dwd/dmo` `icon` (`radl3`, DWD's long-wave radiation balance of the last 3 hours, negative in almost every value); the values and the unit are unchanged | 0.164.0, GH-2614 |
| `snow_depth` | `snow_depth_sum` | `dwd/observation` monthly and annual `precipitation_more` (`mo_sh_s`, `ja_sh_s`: the sum of the daily depths, in cm times days); `snow_depth` of the daily rows is a depth | 0.164.0, GH-2614 |
| `temperature_air_min_0_05m` | `temperature_air_min_0_05m_night` | `geosphere/observation` daily (`tsmin`, the night minimum from 18 UTC of the previous day to 06 UTC); the 10-minute and hourly rows keep the name | 0.164.0, GH-2614 |
| `precipitation_amount_max` | `precipitation_amount_max_30min` | `dmi/observation` daily (`max_precip_30m`, the largest 30 minutes of the day); the monthly and annual rows (`max_precip_24h`, the largest day) keep the name | 0.164.0, GH-2614 |
| `temperature_air_2m` (and `temperature_air_mean_2m` of 0.139.0) | `temperature_air` | `dwd/road` (`airTemperature`, a sensor 4 to 5 m above ground by BUFR 0 07 032, never 2 m); the values and the unit are unchanged | 0.164.0, GH-2614 |
| `temperature_dew_point_2m` (and `temperature_dew_point_mean_2m` of 0.139.0) | `temperature_dew_point` | `dwd/road` (`dewpointTemperature`, the same sensor); the values and the unit are unchanged | 0.164.0, GH-2614 |
| `humidity_relative_mean` | `humidity_relative` | `dwd/road` (`relativeHumidity`, BUFR 0 13 003 with no statistic: a reading, as it was before 0.160.0); the values and the unit are unchanged | 0.164.0, GH-2614 |
| `humidity_relative` | `humidity_relative_mean` | `ipma/observation` hourly (`humidade`, "média da hora") | 0.164.0, GH-2614 |
| `pressure_air_sea_level` | `pressure_air_sea_level_mean` | `ipma/observation` hourly (`pressao`, "média da hora") | 0.164.0, GH-2614 |
| `radiation_global_intensity` | `radiation_global_intensity_mean` | `geosphere/observation` 10-minute and hourly (`cglo`, "kalibriert, Mittelwert"); the values and the unit are unchanged | 0.165.0, GH-2614 |
| `radiation_sky_short_wave_diffuse_intensity` | `radiation_sky_short_wave_diffuse_intensity_mean` | `geosphere/observation` 10-minute (`chim`, "kalibriert, Mittelwert") | 0.165.0, GH-2614 |
| `wind_direction` | `wind_direction_mean` | `geosphere/observation` 10-minute and hourly (`dd`, "vektorieller 10-Minuten- / Stunden-Mittelwert") | 0.165.0, GH-2614 |
| `wind_speed` | `wind_speed_mean` | `geosphere/observation` 10-minute and hourly (`ff`, "vektorieller 10-Minuten- / Stundenmittelwert"); `ffam` stays `wind_speed_arithmetic` | 0.165.0, GH-2614 |
| `snow_depth` | `snow_depth_mean` | `geosphere/observation` 10-minute (`sh`, "10-Minuten-Mittelwert"); the hourly and daily rows keep `snow_depth` | 0.165.0, GH-2614 |
| `pressure_air_site` | `pressure_air_site_mean` | `geosphere/observation` monthly (`p`, "Monatsmittel der Terminwerte"); the 10-minute and hourly rows keep `pressure_air_site` | 0.165.0, GH-2614 |
| `temperature_air_max_2m_last_24h`, `temperature_air_min_2m_last_24h` | not served | `nws/observation` hourly (`maxTemperatureLast24Hours`, `minTemperatureLast24Hours`: null in all 49,688 observations of 108 stations read on 2026-10-21); `meteofrance/synop` still has both | 0.165.0, GH-2614 |
| `temperature_air_2m` (and `temperature_air_mean_2m` of 0.139.0) | `temperature_air` | `wsv/pegel` (`LT`, `LUFTTEMPERATUR`: PEGELONLINE states no height); the values and the unit are unchanged | 0.166.0, GH-3242 |
| `chloride_concentration`, `precipitation_amount`, `precipitation_intensity` | not served | `wsv/pegel` (`CL`, `NIEDERSCHLAG`, `NIEDERSCHLAGSINTENSITÄT`: `stations.json?timeseries=<shortname>` answers 0 stations for each, 786 stations read on 2026-10-21); `chloride_concentration` is no parameter of any provider any more, the other two stay names of other providers | 0.166.0, GH-3242 |
| `temperature_air_2m` (and `temperature_air_mean_2m` of 0.139.0) | `temperature_air` | `dwd/swsmos` (`TL`, "Lufttemperatur": the sheet states no height); the values and the unit are unchanged | 0.166.0, GH-3263 |
| `temperature_dew_point_2m` (and `temperature_dew_point_mean_2m` of 0.139.0) | `temperature_dew_point` | `dwd/swsmos` (`TD`, "Taupunkttemperatur": the sheet states no height); the values and the unit are unchanged | 0.166.0, GH-3263 |
| `road_surface_condition` | `road_surface_condition_forecast` | `dwd/swsmos` (`RC`: 1 dry, 2 moist, 3 snow, 4 hoar frost, 5 freezing wetness, 6 glaze ice); `dwd/road` keeps `road_surface_condition` with the BUFR codes (0 dry, 1 moist, 2 wet, ...), so the two are never one parameter | 0.166.0, GH-3263 |
| `soil_moisture_winter_wheat_<soil>_00cm_60cm`, `soil_moisture_mean_winter_wheat_<soil>_00cm_60cm`, `evaporation_amount_winter_wheat_<soil>` | `soil_moisture_winter_cereals_<soil>_00cm_60cm`, `soil_moisture_mean_winter_cereals_<soil>_00cm_60cm`, `evaporation_amount_winter_cereals_<soil>` | `dwd/derived` daily and monthly (`bfws_ag`, `bfwl_ag`, `vrws_ag`, `vrwl_ag` and their monthly `mittel von` and `summe von`: DWD's sheets say "Wintergetreide", winter cereals; the monthly `soil_moisture_winter_wheat_<soil>_00cm_60cm` is answered with `soil_moisture_mean_winter_cereals_<soil>_00cm_60cm`); `<soil>` is `sand` or `loamy_silt`; the values and the unit are unchanged. The `winter_wheat` of `dwd/phenology` is a crop and stays | 0.166.0, GH-3263 |
| `wind_gust_max` | `wind_speed_max` | `chmi/observation` daily (`Fmax`, "Max rychlost": the source says maximum speed and nothing of a gust); the values and the unit are unchanged | 0.166.0, GH-3264 |
| `radiation_sky_short_wave_direct_intensity` | `radiation_sky_short_wave_direct_perpendicular_intensity` | `dwd/poi` (`direct_solar_radiation_last_hour`: above the global radiation at French stations, 603 against 297 W/m2 at 07280 on 2026-10-22, because it is the irradiance on a plane perpendicular to the sun's rays, not the component on a horizontal surface); the values and the unit are unchanged | 0.169.0, GH-3263 |
| `radiation_sky_short_wave_direct` | `radiation_sky_short_wave_direct_perpendicular` | `metoffice/observation` hourly `radiation` (`direct_irad`: MIDAS table RO defines it as measured by a pyrheliometer "at normal incidence", so it is the energy of the hour on a plane perpendicular to the sun's rays, not on a horizontal surface); the values and units are unchanged | 0.173.0, GH-3316 |
| `cloud_cover_below_1000ft` | `cloud_cover_below_2km` | `dwd/mosmix`, `dwd/dmo` (`nl`) | 0.140.0, GH-1977 |
| `count_weather_type_sleet` | `count_weather_type_graupel` | `dwd/observation` daily, monthly, annual `weather_phenomena` and `weather_phenomena_more` | 0.145.0, GH-2696 |
| `evapotranspiration_potential_grass_fao_last_24h`, `..._haude_last_24h` | `evapotranspiration_potential_grass_fao`, `evapotranspiration_potential_grass_haude` | the daily and monthly totals: `dwd/derived`, `meteoswiss/observation` daily | 0.140.0 (GH-2042), 0.155.0 (GH-2847) |
| `groundwater_level_max`, `groundwater_level_min` (daily), `groundwater_level` (15 minutes) | `stage_max`, `stage_min`, `stage`, in centimetres, no longer metres: multiply stored values by 100. `15_minutes/groundwater_level` now holds the 1074 borehole loggers | `ea/hydrology`: the river level was filed as groundwater | 0.153.0, GH-2632 |

### Removed

| Name in 0.139.0 | Now | Release, issue |
| --- | --- | --- |
| `dwd/observation` `daily/temperature_soil/temperature_soil_mean_1m` (`v_te100m`) | not offered: DWD publishes no 100 cm column. A request that names it warns and drops it, or fails if it names nothing else | 0.151.0, GH-2700 |
| `dwd/mosmix` large `h_bsc` (`cloud_base_convective`), `rr1`, `rr3`, `rr6`, `rrh`, `rrd` (`precipitation_amount_last_1h` to `_24h`), `rads3` (`radiation_global_last_3h`), `radl3` (`radiation_sky_long_wave_last_3h`) | not declared: MOSMIX-L never delivers them. The precipitation totals have the nearest elements in `rr1c`, `rr3c`, `rr6c`, `rrhc`, `rrdc` (the totals consistent with the significant weather), `precipitation_amount_significant_weather_last_1h` to `_24h`, which the error names only as a guess | 0.155.0, GH-2851 |

### The resolution

`6_hour` is `6_hours` (`Resolution.HOUR_6.value`, `metno/frost`): a `6_hour/data` parameter raises
`InvalidParameterError`, which says it was renamed (0.155.0, GH-2641, GH-2561).

## Values, units and timestamps

These keep their names and their request, and give other numbers or other stamps. Nothing refuses your code, so a
series you stored before does not join the new one. From 1.0 a correction of this kind is marked
**Breaking** and made in a minor release, with an entry that says what to do with stored values
([Compatibility](compatibility.md#what-counts-as-breaking)).

### Units and meaning

| Provider and parameter | Before | Now | What to do with stored values | Release, issue |
| --- | --- | --- | --- | --- |
| `dwd/observation` `10_minutes/urban_solar` `sunshine_duration` | declared in minutes: a full-sun interval read 10.2 s | declared in hours: 612 s. With `convert_units=False` the number is unchanged and the unit is `h` | multiply by 60 | 0.151.0, GH-2698 |
| `dwd/dmo` `radiation_global` (`Rad1h`) and `radiation_global_last_3h` (`RadS3`) | read as kJ/m2 | DWD writes J/cm2: ten times larger | multiply by 10 | 0.150.0, GH-2821 |
| `ipma/observation` `wind_direction` | north (the codes 1 and 9 of the feed) was 0.0, beside a wind that blows | 360.0, as for every other provider; the code 0 ("sem rumo") stays null | a 0.0 stored beside a wind speed above 0 is north: read it as 360 | 0.175.0, GH-3135 |
| `noaa/ghcn` hourly `snow_depth` | declared in centimeters | millimeters, as GHCNh publishes it; with the default unit targets it is still centimeters, a tenth of what it was | divide by 10 | 0.150.0, GH-2848 |
| `dwd/observation` `hourly/precipitation` `precipitation_form` 9 | the code 9 | null, with `raw:9` as the last token of `quality_flags`; read the null as an unknown form | | 0.156.0, GH-2703 |
| `dwd/dmo` `precipitation_amount_last_1h` (`rr1`) and `precipitation_amount_last_3h` (`rr3`) below 0 | the little negative number ICON writes (to -0.10 and -0.04 mm), and `-0.0` for a `-0.00` | 0.0, with the number (`raw:-0.1`, for example) as the last token of `quality_flags` | nothing for a reading; filter on `raw:` for the old numbers | 0.169.0, GH-3263 |
| `ea/hydrology` river level | `groundwater_level` in metres | `stage` in centimetres | see above | 0.153.0, GH-2632 |

### Timestamps

| Provider | Before | Now | Release, issue |
| --- | --- | --- | --- |
| `noaa/ghcn` `daily` | the station's local standard midnight in UTC (Tokyo 15:00 the day before) | 00:00 UTC of the date: join on the date, and shift series stored with the old stamps | 0.146.0, GH-2683 |
| `eccc/observation` `daily`, `monthly` | the station's civil midnight in UTC | 00:00 UTC of the date, or of the first of the month | 0.146.0, GH-2683 |
| `eccc/observation` `hourly` | stations on daylight saving were stamped an hour early from March to November | the instant ECCC gives in `UTC_DATE`: summer stamps move one hour later, a station whose ECCC zone differs from its position's by the difference, and two lost hours are returned | 0.145.0, GH-2675 |
| `smhi/observation` `daily` `snow_depth`; `metno/frost` `daily` `snow_depth` | the time of the reading (06:00 UTC) | 00:00 UTC of the date, like the other daily parameters: join on the date | 0.146.0 (GH-2683), 0.147.0 (GH-2729) |
| `ea/hydrology` `daily` | 09:00 UTC for the mean, the instant of the extreme for the maximum and minimum | 00:00 UTC of the day it names; where the endpoint answers a day twice, the reading with a value is kept | 0.146.0, GH-2683 |
| `dmi/observation` daily `precipitation_amount_max` | the day before the one it ends on | the day it ends on, as DMI defines it: its series moves one day later | 0.146.0, GH-2676 |
| `meteofrance/observation` 6-minute and hourly, overseas departments (971-975, 984-988) | the file's fixed offset labelled UTC (Réunion 4 h late) | UTC: drop a shift you applied yourself | 0.145.0, GH-2677 |
| `dwd/observation` `hourly/temperature_air` `historical`, the periods DWD calls "Stundenwerte in MEZ (MD)" (up to 1991, 80 East German stations) | read as UTC | MEZ, so one hour earlier, with `zone:mez` in `quality_flags`: add an hour to flagged stamps to get the old ones | 0.155.0, GH-2709 |
| `dwd/observation` `hourly/temperature_soil` `historical`, the periods whose source is the archive of the eMD (up to 1991, 74 East German stations); `hourly/temperature_air` of Diepholz (00963) from 1995-02-01 00 to 1996-05-31 23 | read as UTC | MEZ, so one hour earlier, with `zone:mez` in `quality_flags` (the soil stamps 01, 04, ..., 22 are 00, 03, ..., 21 UTC): add an hour to flagged stamps to get the old ones; the stamp 1995-02-01 00 of Diepholz is the report of 1995-01-31 23 and its row is dropped | 0.170.0, GH-3029 |
| `knmi/observation` `hourly` | the start of the hour | the end of the hour, KNMI's own stamp: every hourly `timestamp` moves 1 hour later, and `start` = `end` = 12:00 returns the hour 11-12. `10_minutes` and `daily` are unchanged | 0.160.0, GH-2824 |

### Which rows are returned

| Provider | Before | Now | Release, issue |
| --- | --- | --- | --- |
| `noaa/ghcn` `daily` stations Torrevieja (SP000007038), Alice Holt Lodge (UKE00105927) and the RAF stations Molesworth, Chelveston, Bassingbourn and Huntington (UKW00015014, -15015, -15018, -15033) | placed east of Greenwich, 7 to 125 km off: `ghcnd-stations.txt` has lost the sign of their longitude | placed west of it, with a negative `longitude`; a filter on the old position needs the new one | 0.174.0, GH-2886 |
| `noaa/ghcn` `hourly` stations Chelveston (UKW00015015) and Huntington (Alconbury, UKW00015033) | placed east of Greenwich, 73 and 29 km off: `ghcnh-station-list.csv` has lost the sign of their longitude (the elevation of UKW00015033 now follows the daily one, 47.9 to 49.1 m, when both resolutions are requested) | placed west of it, with a negative `longitude`; a filter on the old position needs the new one | 0.175.0, GH-3384 |
| `eaufrance/hubeau` the 54 stations whose referential lists latitude and longitude swapped (Anor at 4.10 N, 49.99 E) | placed as the source lists them, a point near Somalia | placed where they are (Anor at 50.0 N, 4.1 E): swapped back when the listed position lies in none of metropolitan France, Guadeloupe and Martinique, Guyane, Reunion and Mayotte and the swapped one lies in one. `J543211003` (the Blavet) is not moved; a filter on the old position needs the new one | 0.176.0, GH-3468 |
| every provider whose source hands several rows for one reading (the same station, parameter and timestamp) | the first row, even when it had no value, so a later row's value was lost | the first row that has a value, with that row's `quality_flags`; a reading that was null is filled where another row had a value. Nothing to change | 0.176.0, GH-3450 |
| `nws/observation` `hourly` | the 12 observations an hour the endpoint serves | one for each station-hour, stamped with the full hour: the METAR or SPECI nearest to it, else the nearest 5-minute row. The minute of a report is gone | 0.155.0, GH-2857 |
| `noaa/ghcn` `hourly` | every report of the file under its own minute (up to seven an hour) | one reading for each parameter and full hour, the nearest to the hour, stamped with it: the METAR of 14:53 is 15:00 | 0.158.0, GH-3000, GH-3016 |
| `noaa/ghcn` `hourly` precipitation | every report | the one report of each UTC hour at the station's routine minute, else the last that is no SPECI | 0.156.0, GH-2841 |
| `values` with a `name` on the command line, REST and MCP | the best five stations, with the values of all five | the one best match, as `filter_by_name` does; pass `--rank` or `rank` for another number | 0.155.0, GH-2635 |
| the stations of a `name` (`filter_by_name`, `stations`, `values`), and `rank` | in the order of the station list; `rank` counted rows, so a station with several datasets used up the rank with its own rows, and two stations of the same name both came back | best match first, equal scores by `station_id`, and `rank` counts stations: `rank=3` is at most three stations, with all their rows. Sort the result yourself where you relied on the order of the list. `values` matches the name among the stations that have a record in the window | 0.161.0, GH-3025, GH-3026 |
| `values` of a station the provider does not publish a record for, no `timestamp` | not counted by `WD_RESTAPI_MAX_ROWS` | counted: from 1950 for historical data, two years for recent, two days for current. Can be a 400 `limit-exceeded`: give a `timestamp`, or use `format=ndjson` or `csv` | 0.159.0, GH-3089 |

## Command line

| Before | Now | Release, issue |
| --- | --- | --- |
| `--start-date`, `--end-date` | `--start`, `--end` | 0.142.0, GH-2437 |
| `--date` of `values`, `interpolate`, `summarize`, `alerts` | `--timestamp` | 0.142.0, GH-2438 |
| `--convert_units`, `--unit_targets`, `--sql_values`, `--skip_empty`, `--skip_criteria`, `--skip_threshold`, `--drop_nulls`, `--if_exists`, `--with_metadata`, `--with_stations`, `--lead_time`, `--start_year`, `--end_year`, `--name_threshold`, `--show_title`, `--show_years`, `--show_data_availability`, `--wmo_code`, `--country_name` and the `--interpolation_station_distance*`, `--summary_station_distance*` | the same with hyphens (`--convert-units`); the underscored name is refused with an error naming the hyphenated one | 0.156.0, GH-2561 |
| `--station` (a list) | `--stations`; the singular `--parameter`, `--period`, `--resolution`, `--dataset` of a list are refused naming the plural. `interpolate`, `summarize`, `issues` and `stripes` keep their one reference `--station` | 0.156.0, GH-2561 |
| `wetterdienst summarize --use_nearby_station_distance` | gone: leave it out (a summary takes the nearest station with data); `interpolate` keeps its own | 0.158.0, GH-3077 |
| `wetterdienst stripes values` wrote the image | `wetterdienst stripes image` writes it; `stripes values` is "No such command" since 0.173.0, and the name is not reused | 0.173.0, GH-3128 (deprecated in 0.159.0, GH-3035; announced for removal in 1.0.0) |
| an empty result exited 1 (a window without readings, a selection that finds no station, a glossary filter that matches nothing) | exit 0, as REST answers 200: the sentence goes to stderr and stdout holds what REST answers (`{"values": []}`, the CSV header). A script that told "no data" by exit 1 tests the output; exit 1 now only means failure | 0.155.0, GH-2635 |
| `wetterdienst stripes values` refusals exited 1 | exit 2, as click's usage errors do | 0.140.0, GH-2060 |
| `wetterdienst issues` for DMO listed every lead time | `--lead-time long` for the long runs, short by default | 0.140.0, GH-2009 |
| a download that failed printed a Python error | one line, exit 1 (`DownloadError`, `NoInternetError`) | 0.155.0 to 0.176.0, as under [Failures](#failures) |

## REST API

The routes are also served under `/api/v1`, with `/api` an alias of the current version; nothing about the paths has
to change.

### Requests

| Before | Now | Release, issue |
| --- | --- | --- |
| `debug` on a REST endpoint (all but `version`, `settings` and `health`), which set the log level of the whole server process | a 422 of type `removed`, `debug was removed`: drop it; the level is the operator's (`logging.getLogger("wetterdienst")`, or `wetterdienst restapi --debug`) | 0.174.0, GH-3336 |
| `date=` on `values`, `interpolate`, `summarize`, `alerts` | `timestamp=`: a 422 naming the new name | 0.142.0, GH-2438 |
| `station=` as a list on `stations`, `values`, `history` | `stations=` (comma-separated); the singular `parameter`, `period`, `resolution`, `dataset` of a list are refused naming the plural. The one reference `station` of `interpolate` and `summarize`, and the `station` of `issues` and `stripes`, stay | 0.156.0, GH-2561 |
| an unknown query parameter on `/api/auth`, `/api/coverage`, `/api/glossary`, `/api/stripes/stations`, `/api/alerts` was ignored | a 422, as `/api/stations` and `/api/values` always did; drop what an endpoint does not take, such as a cache buster | 0.142.0, GH-2479 |
| `station` with `name`, `rank` or `distance` beside anything but a point; no selection; half a point or box | a 422 located at the parameter, typed `missing_one_of`, `mutually_exclusive`, `missing_with` or `requires`. Send exactly one of `all`, `stations`, `name`, a point with `rank` or `distance`, a bounding box, or `sql` | 0.140.0, GH-2056 |
| `/api/stations` with `lead_time`, `issue` | a 422: they never changed the list; send them to `/api/values` | 0.157.0, GH-3056, GH-3061 |
| `/api/stations` and the MCP `stations` tool with `with_stations` (accepted and ignored) | a 422; `history` and the value endpoints keep it | 0.156.0, GH-3034 |
| `summarize` with `use_nearby_station_distance` | a 422 | 0.158.0, GH-3077 |
| `/api/stripes/*` matched a `name` at a threshold of 0.9 | 0.8, as the rest do; pass `name_threshold=0.9` to match as before | 0.140.0, GH-2063 |
| `/api/stripes/values` and `image` with neither or both of `station` and `name`, an `end_year` not after `start_year`, a `name_threshold` outside 0 to 1 gave a 400 with a string `detail` | a 422 with typed `errors`, as the other endpoints | 0.140.0, GH-2060 |
| `sql`, `sql_values` | a 403 (`sql-disabled`) unless the server runs with `WD_RESTAPI_SQL=true` | 0.140.0, GHSA-rpwr-qmm5-m9wp |
| `values` for `all=true` on any network, any number of stations | refused with the 400 `limit-exceeded` over 100 stations or over the row limits (500,000 as one body; `format=ndjson` and `csv` stream to 10,000,000). Request fewer stations or a shorter `timestamp`, stream, or raise `WD_RESTAPI_MAX_STATIONS`, `WD_RESTAPI_MAX_ROWS`, `WD_RESTAPI_MAX_STREAM_ROWS` on your own server | 0.158.0, GH-3065 |
| a chart with a side over 8192 px | a 400 naming the limit (the library and the CLI are not limited) | 0.147.0, GH-2765 (not marked Breaking) |

### Answers and errors

| Before | Now | Release, issue |
| --- | --- | --- |
| a 422 put pydantic's list under `detail`; every error had its own body | every error is an RFC 9457 `application/problem+json`: `type`, `title`, `status`, `detail` (always text), and `errors` (the list of a 422). Read `errors` for the invalid parameters, `detail` for a sentence. The MCP tools show the text of `detail` | 0.155.0, GH-2634, GH-2561 |
| the problem `type` was always `about:blank` | `urn:wetterdienst:problem:<kind>`: branch on it, not on `detail` | 0.158.0, GH-3065 |
| a station the stripes do not know, or a forecast run (`issue`) the source does not list, was a 400 | a 404 for a `NotFoundError`; the answer follows from the class: `RequestError` 400, `NotFoundError` 404, `ConfigurationError` 501, `UpstreamError` 502 | 0.155.0, GH-2634 |
| a failure on the data provider's side was a 400, 404 or 500 | 502 (a download refused or cut short, a file the parser does not expect), 504 after a timeout, 503 without a connection (`NoInternetError`); the body says the request was valid. Retry a 502, 503 or 504, and read a 500 as a defect of the server. `/api/alerts` decides by class like the rest | 0.140.0 to 0.156.0, GH-2252, GH-2276, GH-2294, GH-2985 |
| `/api/history` for a network without station history, `/api/issues` for a network that lists none: 404 and 400 | 501 | 0.158.0, GH-3065 |
| the answer of `stripes/values` had `station`, `resolution`, `dataset`, `parameter`, `unit` in `metadata` | in a `series` member: `answer["series"]["unit"]` where you read `answer["metadata"]["unit"]`; `metadata` is the metadata block only | 0.158.0, GH-3076 |
| timestamps in history, alerts, issues and stripes as `...T00:00:00+00:00` | ISO 8601 UTC to the microsecond, `...T00:00:00.000000+00:00`, in JSON, GeoJSON and CSV | 0.155.0, GH-2633 |
| `/api/coverage` probed credentials and listed `valid` | downloads nothing and answers at once; `valid` is gone from the listing: read `configured`, and `GET /api/auth` per network for whether the credentials are accepted. `valid` there is `true`, `false` or `null` for unknown | 0.147.0 (GH-2564), 0.155.0 (GH-2641) |
| the `/api/issues`, `/api/alerts` and `/api/stripes/*` answers had no `metadata` block (not marked Breaking) | they carry it; the MCP tools `alerts` and `stripes_*` answer `{"result": ...}` as `stations` does: read the answer from `result` | 0.158.0, GH-3059 |

## MCP

The tools are the REST routes, so the changes to the requests and answers above apply to them: the names of the
arguments are the query parameters. In addition:

| Before | Now | Release, issue |
| --- | --- | --- |
| the `debug` argument of the tools | a tool error, `debug was removed`: drop it (see the REST row above) | 0.174.0, GH-3336 |
| an argument a tool does not take was dropped, and the call answered as if it had not been given | refused with the names of the ones it takes | 0.142.0, GH-2479 |
| `stations` with `lead_time`, `issue` | a tool error | 0.157.0, GH-3056 |
| `summarize` with `use_nearby_station_distance` | refused | 0.158.0, GH-3077 |
| the endpoint kept a session | stateless: no `mcp-session-id`, no `initialize` needed before `tools/list` or `tools/call`; `DELETE` and the `GET` that opens a stream answer 405. A client that depended on being given a session id has to stop | 0.159.0, GH-3088 |
| `/mcp` | `/mcp/v1` is the endpoint to configure; `/mcp` stays as an alias of the current version | 0.158.0, GH-3074 (nothing to change) |

## Docker and deployment

| Before | Now | Release, issue |
| --- | --- | --- |
| the image ran as root | it runs as the user `wetterdienst` (uid 10001) in `/home/wetterdienst`, with `/home/wetterdienst/.cache/wetterdienst` as its cache. Mount a cache volume there or point `WD_CACHE_DIR` to one, and make a volume or host directory that root filled writable by uid 10001 once: `docker run --rm --user 0 -v <volume>:/c ghcr.io/earthobservations/wetterdienst chown -R 10001:10001 /c` | 0.148.0, GH-2770 |
| the image listened on 3000 | it listens on 7890, as `wetterdienst restapi` does, and `compose.yml` publishes 7890: map `3000:7890` (or `7890:7890`), or start it with `--listen 0.0.0.0:3000` | 0.159.0, GH-3106 |

## Verified

The parameter tables above were checked against the code of both releases. 404 parameters that a dataset of 0.139.0
has are not in the current release under the same name; each is requested from it, and a test
(`tests/metadata/test_gone_since_0_139_0.py`) holds each to the answer below; the numbers of this paragraph are
computed from the same list. 373 of the refusals name a replacement, and that replacement exists in the same network, resolution
and dataset. The other 31 are:

- the removals, with no replacement: `temperature_soil_mean_1m` of DWD daily (GH-2700), `wind_direction_gust_max` of
  Météo-France hourly (GH-2836), and the eight MOSMIX-L elements that the files never carry (GH-2851):
  `cloud_base_convective`, `radiation_global_last_3h`, `radiation_sky_long_wave_last_3h` and the five precipitation
  totals `precipitation_amount_last_1h`, `_3h`, `_6h`, `_12h` and `_24h`. The near spelling the error offers for the
  totals, `precipitation_amount_significant_weather_last_1h` and so on, is another element (`RR1c`, the total
  consistent with the significant weather) and a guess, not a rename. Also removed: `chloride_concentration`,
  `precipitation_amount` and `precipitation_intensity` of each of the five WSV Pegel resolutions, which no station of
  the service serves (GH-3245), and `temperature_air_max_2m_last_24h` and `temperature_air_min_2m_last_24h` of the NWS
  hourly observations, which the API leaves null at every station (GH-3235);
- the names the source itself uses, which still select their row and come back under the new name:
  `wind_speed` and `wind_direction` of the Met Office hourly weather, `wind_direction` of ECCC, and `wind_speed`
  of `metno/frost` (a request for it needs the met.no credential, so it was not run).
