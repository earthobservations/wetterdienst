# Architecture

How the library is put together: what a request turns into, what a provider has to hand over, how bytes reach the
provider, and how the command line, the REST API and the MCP server sit on top. It is an explanation for someone who is
about to change the core or add a provider; the words it uses are in [Concepts](../usage/concepts.md), the steps of
adding a provider are in [Services](services.md), and the classes themselves are in the [API reference](../library/core.md).

## The layers

```text
 surfaces    CLI               REST API  <--- in-process --- MCP server        app/ (Nuxt) --HTTP--> REST API
             ui/cli.py         ui/restapi.py                 ui/mcp.py
                  \               /
                   +--> ui/core.py     request models, get_stations, get_values, get_interpolate, ...
                          |
 library     Wetterdienst.resolve(provider, network)    the registry (api.py) gives the request class
                          |
             TimeseriesRequest --- all(), filter_by_*() ---> StationsResult
             model/request.py                                model/result.py
                                                                  | values()
                                                                  v
                                                       TimeseriesValues --- query(), all() ---> ValuesResult
                                                       model/values.py                          model/result.py
                          |                                 |
 providers   provider/<provider>/[<network>/]               one hook call per station and
             api.py  metadata.py  parser.py  ...            parameter (or dataset)
                          |
 base        util/network.py   fsspec, cache, retry, errors      settings.py   options.py
             io/export.py      formats and targets               core/interpolate.py   core/summarize.py
```

Everything below `ui/` is the Python library and is usable without any of the surfaces. The surfaces add nothing to what
a request can ask for: the command line and the REST API build the same request and call the same functions of
`ui/core.py`, and the MCP tools are the REST API's endpoints called in-process (see [The three surfaces](#the-three-surfaces)).

## Request, stations, values

A request is a `TimeseriesRequest` (`wetterdienst.model.request`), a dataclass every provider extends. It holds
`parameters`, `start`, `end`, `periods`, the `settings` and the `options`, and its `__post_init__` is the only
validation step: it turns `settings` and `options` into `Settings` and `Options`, converts the timestamps, parses the
parameters against the provider's metadata (`parse_parameters`, an `InvalidParameterError` for an unknown one unless
`on_unknown="warn"`) and resolves the periods to the set the datasets are published under. Nothing is downloaded yet.

The provider supplies three class attributes, no more: `metadata` (the metadata model, see [Metadata](#metadata)),
`_values` (the values class, a class and not an instance) and, optionally, `_history`.

**Stations.** `all()` calls the provider's `_all()`, collects the lazy frame, and lets the core shape it
(`add_resolution_and_dataset`, `shape_stations_frame`): the result is a `StationsResult`, a frozen dataclass holding
`request`, `df` (one row per resolution, dataset and station) and the private `_df_all`, `_stations_filter` and `_rank`
that say how `df` was selected. Every filter (`filter_by_station_id`, `filter_by_name`, `filter_by_rank`,
`filter_by_distance`, `filter_by_bbox`, `filter_by_sql`) starts from `all().df` and returns a new `StationsResult`; the
`StationsFilter` enum names which one it was. A provider never implements a filter.

**Values.** `StationsResult.values()` builds a fresh reader with `request._values.from_stations(self)`.
`TimeseriesValues.query()` walks the selected stations one at a time and yields a `ValuesResult` per station;
`all()` concatenates them. For one station the core does the following, and the provider takes part in the second step only:

1. Skip the station if its published start is after the end of the window (`_begins_after_window`).
2. For each requested dataset the station has, call the provider's `_collect_station_parameter_or_dataset`: once per
   parameter, or once per dataset when the dataset is declared `grouped`.
3. Shape what came back to the long form (`shape_provider_frame`), cut a `grouped` frame to the requested parameters,
   convert units (unless `convert_units` is off), remove duplicates, and drop null values (unless the options keep them).
4. Cut to the window, skip the station if it is empty or covered too sparsely (`skip_empty`), humanize the parameter
   names, widen if the shape is `wide`, and sort.

A station that returns nothing in the window does not count towards a `filter_by_rank` selection, so the ranked walk
goes on to the next one (`StationsResult._rank`).

The other results are made the same way. `history()` builds a `TimeseriesHistory` (`model/history.py`) from the
request's `_history` and raises `NotImplementedError` when the provider has none; its hook is `_collect_station_history`.
`InterpolatedValuesResult` and `SummarizedValuesResult` share their base with `ValuesResult` and come out of
`request.interpolate()` and `request.summarize()` (see [Interpolation, summary and export](#interpolation-summary-and-export)).
The results of stations and values share `ExportMixin` for their formats and targets.

## The registry

`Wetterdienst` (`wetterdienst.api`) is a registry and is never instantiated: `Wetterdienst(provider, network)` raises
a `TypeError` that names the replacement. `Wetterdienst.registry` maps provider and network to the dotted path of the
request class, and nothing is imported until it is asked for, so listing the registry does not import the providers.

| Call | Does |
| --- | --- |
| `Wetterdienst.resolve(provider, network)` | the request class of a timeseries network; `ApiNotFoundError` if it is not in the registry, or is a standalone network |
| `Wetterdienst.resolve_standalone(provider, network)` | the request class of `dwd/radar` or `dwd/alerts`, which have no stations, no values and no metadata model (`Wetterdienst.standalone`) |
| `Wetterdienst.discover()` | what every network is (name, country, URL, `kind`, whether it needs credentials and has them, whether a date is required), without downloading anything; a network that cannot be imported is left out with a logged warning |
| `Wetterdienst.get_provider_names()`, `get_network_names(provider)` | the names |
| `Wetterdienst.is_configured(api)`, `is_valid(api)` | whether the credentials of a provider are present, and whether the provider accepts them (this one asks the provider) |

A new provider is in the registry or it does not exist for the REST API, the command line and the MCP tools, which all
resolve through it. `tests/test_public_surface.py` holds every network of the registry to the committed snapshot of the
Python surface.

## Metadata

Everything the core knows about a provider comes from its `metadata.py`: a nested dict that `build_metadata_model()`
(`wetterdienst.model.metadata`) validates into pydantic models, `MetadataModel`, which holds `ResolutionModel`s, which
hold `DatasetModel`s, which hold `ParameterModel`s. All of them forbid fields they do not know, so a typo in a
declaration fails when the module is imported.

- **The provider** is described by the fields above `resolutions` (`name_short`, `country`, `license`, `attribution`,
  `url`, `kind`, `timezone`, `auth`, ...). The REST API reports them in every answer, and `Wetterdienst.discover()`
  reads `kind`, `auth` and `date_required` from them. `kind` is `observation`, `forecast` or `derived`.
- **Periods and `date_required`** can be declared on the resolution and are copied to every dataset that does not
  declare its own.
- **A parameter** declares the canonical `name`, the source's `name_original` and the `unit` the source publishes. It
  does not declare a unit type: that is read from the canonical parameter table (`wetterdienst.metadata.parameter_table`)
  through the canonical name, so one quantity cannot have two unit types.
- **Descriptions** are not declared in the dict. `build_metadata_model` attaches them from
  `wetterdienst.metadata.source_descriptions` and, for a parameter none of them describes, from the canonical table.
- **Access**: the models are indexable and attribute-accessible by name, which is why
  `DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m` and
  `("daily", "climate_summary", "temperature_air_mean_2m")` request the same thing.

The shared vocabulary lives in `wetterdienst/metadata/`: `Resolution`, `Period`, `CacheExpiry`, `UnitType`, the
canonical parameter table, the aliases and the renames. How a declaration looks is the first step of
[Services](services.md#step-1-metadata); what the canonical names mean is in the [glossary](../data/parameters.md).

## What a provider implements

A provider is a request class and a values class (and a history class where the source has one), usually in one
`api.py`, with its `metadata.py` beside it and whatever helpers the source needs (`parser.py` for the raw data,
`fileindex.py` for listings, `download.py`). The smallest complete examples are the key-less JSON providers such as
`provider/lhmt/observation/`; DWD observation (`provider/dwd/observation/`) is the largest.

| Hook | On | The core calls it | It must hand over |
| --- | --- | --- | --- |
| `metadata` (class attribute) | request | at construction | the `MetadataModel` of the network |
| `_values` (class attribute) | request | by `StationsResult.values()` | the values class |
| `_all()` | request | by `all()`, which every filter starts from | a `pl.LazyFrame` of the stations, one row per station and dataset, with `station_id` and, optionally, the other columns of `STATIONS_SCHEMA` |
| `_collect_station_parameter_or_dataset(station_id, parameter_or_dataset)` | values | per station and per parameter (per dataset if `grouped`) | a long frame with `parameter`, `timestamp` and `value`, and `quality_flags` if the source has them |
| `_collect_station_history(...)` | history | by `history().query()` | `History` objects; optional |
| `is_configured()`, `is_valid()` | request | by `Wetterdienst.is_configured`, `is_valid` | only for a network that needs credentials |

The columns, types and rules of the two frames are the docstrings of `_all` (`TimeseriesRequest._all`) and
`_collect_station_parameter_or_dataset` (`TimeseriesValues`), and the tables of [Services](services.md#step-2-request-class)
restate them. The point of the contract is how little is asked: a provider hands over what the source says, and the
core does the rest.

- The core writes `resolution`, `dataset` and `station_id`, casts every column to its type (a naive timestamp is read as
  UTC, a zoned one converted), fills a missing optional column with null, drops any column it does not know, removes
  duplicates, cuts the window and converts units. A frame without rows, even a bare `pl.DataFrame()`, is a station
  without data.
- What cannot be made to fit is a `ProviderContractError` raised by the core: a frame without `parameter`, `timestamp`
  or `value`, a timestamp that is a text.
- A connection that cannot be made is never an empty frame (see [The network layer](#the-network-layer)).
- The `value` is in the unit the metadata declares; the sentinel of the source for "no reading" is mapped to null in
  the provider, and what the source wrote is kept as a `raw:` token of `quality_flags` (`wetterdienst.model.quality_flags`).

`dwd/radar` and `dwd/alerts` are the exceptions: standalone networks with their own request classes
(`DwdRadarValues`, `DwdWeatherAlertRequest`) and results, resolved with `resolve_standalone`.

## The network layer

All HTTP goes through `wetterdienst.util.network`, which wraps fsspec's `HTTPFileSystem`. A provider does not use a
client of its own; it passes the four things it reads from the `Settings` of the request (`cache_dir`,
`fsspec_client_kwargs`, `cache_disable`, `use_certifi`) and a cache expiry:

| Function | Returns |
| --- | --- |
| `download_file(url, cache_dir, ttl, client_kwargs, ...)` | a `File`; a failure does not raise, it is the `File`'s `content` |
| `download_files(urls, ...)` | the `File`s of several URLs, fetched concurrently |
| `list_remote_files_fsspec(url, settings, cache_expiry)`, `list_remote_directory_fsspec(...)` | the files or entries of a directory; they raise |
| `post_file(url, ...)` | a `File` for a POST, never cached (the token endpoints) |

**Caching.** `CacheExpiry` (`wetterdienst.metadata.cache`) is the time to live a caller asks for: `NO_CACHE`,
`FIVE_SECONDS` to `TWELVE_HOURS`, `INFINITE`, and the aliases `FILEINDEX` (five minutes, for listings) and `METAINDEX`
(twelve hours, for station catalogues). `NetworkFilesystemManager` keeps one filesystem per thread and per combination of
cache directory, expiry and client arguments. With a cache it is fsspec's `WholeFileCacheFileSystem` over the HTTP
filesystem (`_LockedWholeFileCacheFileSystem`), in a directory of `cache_dir/fsspec` per expiry; `NO_CACHE` or
`cache_disable` uses the bare HTTP filesystem. `File.from_cache` says which one answered. The cache is a directory of
files, not a service: `Settings.cache_dir` says where it is, and `wetterdienst cache` prints that path.

**Retry.** `stamina` retries what may be a blip and nothing else. A download is tried twice, a listing three times; both
retry a refused or dropped connection, a body that stopped arriving, a timeout and a 5xx, and a download also retries a
404 once, because a file index can be read minutes before the files it names. A 4xx (a 429 included), a certificate that
does not verify and a size or time cap (`MAX_DOWNLOAD_BYTES`, `MAX_DOWNLOAD_SECONDS`) are not retried.

**Failures.** The errors are told apart by what they mean to a caller, and every provider must keep them apart:

| What happened | What the caller gets | REST status |
| --- | --- | --- |
| no connection could be made (offline, a name that does not resolve, a refusing host) | `NoInternetError`: the URL in the message, the connection error as `__cause__` | 503 |
| the source answered badly: a 5xx, a dropped connection, a body cut short, a timeout, a TLS failure, a refused redirect | `DownloadError(url, reason)`, the failure as `__cause__` | 502, 504 for a timeout |
| the file or the directory is not there | a `File` with `status == 404`; a listing is `[]` | |

Both errors are `UpstreamError`s. A download that fails is stored in `File.content` and raised by
`File.raise_if_exception()`; a provider that reads `file.content` itself must `raise` a `NoInternetError` rather than
answer an empty frame, because a scheduled job cannot tell an empty frame from a source with no data. A provider for
which a missing file is an ordinary answer (a station that does not report a parameter is a 404) hands the failures that are no answer to
`as_outage()`, which turns them into these errors. URLs are shown without query, fragment and user information, and credentials are removed from
the errors, so a key does not reach a log. [Troubleshooting](../usage/troubleshooting.md) is the same table from the
user's side.

## Settings and options

Two pydantic-settings classes, kept apart on purpose ([the user's view](../usage/settings.md)):

| | `Settings` (`wetterdienst/settings.py`) | `Options` (`wetterdienst/options.py`) |
| --- | --- | --- |
| Belongs to | the host: one per process | one request |
| Environment | `WD_*`, nested with `__` (`WD_AUTH__KNMI`) | `WD_TS_*` |
| Holds | `cache_dir`, `cache_disable`, `fsspec_client_kwargs`, `use_certifi`, the credentials (`auth`), and the limits, timeout and allowed hosts of the REST API (`restapi_*`) | `shape`, `humanize`, `convert_units`, `unit_targets`, `skip_empty`, `skip_threshold`, `drop_nulls`, `station_window_end_buffer`, and the interpolation distances (`geo_*`) |
| Read by | the providers (through `request.settings`), the network layer, `ui/` | the values, the interpolation and the summary; never a provider |
| Passed as | `settings=` on the request (a `Settings` or a dict) | `options=` on the request (an `Options`, a dict, or none to take the environment) |
| Mutable | by assignment, which is validated | no: frozen, `replace()` makes a changed copy |

Both read `.env` as they read the environment, and only for names they know. The request resolves them once, in
`__post_init__`, and the results read them back through `StationsResult.settings` and `.options`. A provider that
needs a credential reads it from `settings.auth` and reports it through `is_configured()`; one that needs a switch
asks for it in `Settings`, not in `Options`, because only `Settings` is a provider's. The `ts_*` settings of earlier
releases are a shim in `settings.py` that warns and forwards to `Options`.

## The three surfaces

**`ui/core.py`** holds what the surfaces share: the pydantic request models and their rules (which of the selectors
may be combined, which options a request takes), `get_stations`, `get_values`, `get_interpolate`, `get_summarize`, the
resolution of provider and network through the registry, and `failure_status()`, the one table that turns an exception
into the HTTP status a REST call answers (the command line reads it to tell a refusal, a usage error, from an outage):

```text
RequestError, OverflowError   400      NotFoundError            404      ConfigurationError, NotImplementedError  501
NoInternetError               503      other UpstreamError      502 (504 if the cause was a timeout)              anything else 500
```

**The command line** (`ui/cli.py`) is a `click` group. `stations`, `values`, `interpolate` and `summarize` are thin: they
build the request from the options, call `get_stations`, `get_values`, `get_interpolate` or `get_summarize` of
`ui/core.py` and print the result in the requested format.

**The REST API** (`ui/restapi.py`) is a FastAPI app mounted under `/api/v1` and, as an alias of the current version,
under `/api`. An endpoint validates its query with the models of `ui/core.py`, calls the same functions, and renders the
result through `ui/render.py` (or `ui/streaming.py` for NDJSON and CSV streams). The rest of `ui/` is what a server
needs and a library does not: `limits.py` (the refusals before anything is downloaded, from the `restapi_*` settings),
`middleware.py` (request id, timeout, concurrency, allowed hosts), `problems.py` (every failure as a problem
document), `response_metadata.py` (the `metadata` block of every answer, with the licence and attribution of the
provider), `providers.py` (the providers listing). See [REST API](../usage/restapi.md).

**The MCP server** (`ui/mcp.py`) has no logic of its own. `build_mcp_server(rest_app)` hands the REST app's OpenAPI
document to FastMCP's `OpenAPIProvider`, with an ASGI client that calls the REST app in-process; each data endpoint is a
tool (named by `_TOOL_NAMES`, the non-data endpoints excluded), and the endpoint docstrings and the field descriptions of
the models are the tool descriptions. So validation, limits, problems and the metadata block are the REST API's, and a
change to an endpoint is a change to a tool. `_mount_mcp` in `restapi.py` mounts it at `/mcp/v1` and, as an alias of
the current version, `/mcp`; it needs the `mcp` extra and the REST API runs without it. See [MCP server](../usage/mcp.md).

**The app** (`app/`) is a Nuxt single-page application that calls the REST API; it shares no code with the library,
only the contract of the OpenAPI document. See [App](../usage/app.md).

The surfaces are meant to be one vocabulary ([one vocabulary](../usage/restapi.md#one-vocabulary)): a rename on one is a
rename on all, and the parity tests below fail when they drift.

## Interpolation, summary and export

**Interpolation and summary** (`wetterdienst/core/`) are computed from a request, not by a provider.
`TimeseriesRequest.interpolate()` and `summarize()` import `core/interpolate.py` and `core/summarize.py` on demand
(`import_optional`, the `interpolation` extra: scipy, shapely, utm), rank the stations around the point with
`filter_by_distance`, read their values through the request's own values class (as a long, humanized copy of the request,
`_for_estimating`, whatever the caller's options are) and compute one series for the point: `get_interpolated_df`
blends the stations, `get_summarized_df` takes the nearest station that has a reading. How far a station may be, per
parameter and resolution, is `Options.geo_*` together with the `interpolation` property of the canonical parameter,
which decides whether a quantity is interpolated at all. The REST API and MCP set a check
(`TimeseriesRequest._check_reach`) that refuses a point with too many stations in reach before the first download.

**Export** (`wetterdienst/io/export.py`) is `ExportMixin`, shared by every result. It renders to a dictionary, JSON,
an OGC feature collection and GeoJSON, CSV, a plot and an image, and writes to a target named by a connection string with
`to_target`: a `file://` path (CSV, Excel, JSON, JSON lines, Feather, Parquet, Zarr or NetCDF, by its extension), `duckdb://`, `influxdb*://`,
`crate://` or any SQLAlchemy URL. `filtered_by_sql` filters a result with DuckDB. Each writer imports its dependency
when it is used (`import_optional`) and raises `MissingDependencyError`, naming the extra, if it is not installed: the optional
dependency groups are `export`, `sql`, `duckdb`, `excel`, `influxdb`, `cratedb`, `interpolation`, `restapi`, `mcp` and
`bufr`. See [Export](../usage/export.md) and [Interpolation & Summary](../usage/interpolation.md).

## Where tests and snapshots hold what

A contract is held by a committed file and a test that compares the code to it, so that a change shows as a diff in the
pull request. Regenerate with the task named, after an intended change only, and read the diff.

| Part | Held by | Regenerate with |
| --- | --- | --- |
| The REST contract | `tests/ui/openapi.snapshot.json` (`test_openapi_snapshot.py`) | `uv run poe openapi:snapshot` |
| The `--help` of every command | `tests/ui/cli/help.snapshot.txt` | `uv run poe cli:snapshot` |
| The public surface of the Python API | `tests/public_surface.snapshot.json` | `uv run poe surface:snapshot` |
| Those three together | | `uv run poe contracts:snapshot` |
| What the last release offered (OpenAPI, CLI, Python surface, MCP tools, parameters) | `tests/ui/openapi.baseline.json`, `tests/baselines/*.baseline.json` | `uv run poe contracts:baseline`, in a release commit only |
| The parameters of 0.139.0 that are gone | `tests/metadata/gone_since_0_139_0.json` | `uv run poe renames:baseline` |
| The frames the core hands out for every offline provider test | `tests/provider/frames.snapshot.json` | `uv run poe frames:snapshot` |
| A provider's station catalogue and values, offline | `tests/provider/station_catalogue_stubs.py`, `tests/provider/value_stubs.py` (a provider without one is named with the reason) | by hand |
| Physical plausibility of every value | `tests/provider/physical_ranges.py` | by hand |
| Licence and attribution in every answer | `tests/ui/test_response_metadata.py` | by hand |
| The documentation (provider pages, settings, samples) | `tests/test_docs.py`, `tests/test_docs_samples.py` | by hand, see [Writing the documentation](documentation.md) |

The surfaces are held to each other by `tests/ui/test_surface_parity.py` (one request, one answer on the library, the
command line and the REST API), `test_name_parity.py`, `test_window_parity.py` and `test_options_parity.py`, and the
MCP endpoint by `test_mcp_versioning.py`. The network layer's failure semantics are tested in `tests/test_offline.py`
(every provider raises `NoInternetError` offline) and `tests/util/test_network*.py`.

Tests that need the internet carry the `remote` marker, and an unmarked test is refused a connection by
`tests/conftest.py`; run `uv run poe "test:offline"` to check a new test. See [Development sandbox](development.md).
