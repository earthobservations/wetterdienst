# Compatibility

What you can rely on when you upgrade wetterdienst, surface by surface: what is stable, what may change in a minor
release, what only adds, what counts as breaking, and how a break is announced. If you are moving from an older
release, [Migrating from 0.139.0](migrating.md) lists what to change.

Wetterdienst is 0.x until the 1.0.0 tag, and until then any release may break any surface below; each break is an
entry marked **Breaking** in the [changelog](../changelog.md) that says what to use instead. This page is the promise
that 1.0.0 makes. Where a rule is held by a test the page names it; **not yet held by a test** marks a rule that
is a decision and is not checked by anything, so a reviewer has to catch a violation.

## The version numbers

A release of the package, the version of the REST API, the version of the MCP endpoint and the app each have a number
of their own:

| What | Where you read it | Moves when |
| --- | --- | --- |
| the package (`wetterdienst`) | `wetterdienst --version`, `wetterdienst.__version__`, `version` of `GET /api/version` | every release; from 1.0.0 as [semantic versioning](https://semver.org/) says: a break of a frozen surface is a major version, an addition a minor, a fix a patch; two breaks are made in a minor, see [Which release a break takes](#which-release-a-break-takes) |
| the REST API | `api_version` of `GET /api/version` and of every `metadata` block, the `X-Wetterdienst-API-Version` header, the `v1` of `/api/v1` | a change a client has to follow; `/api/v2` would be a new set of routes next to `/api/v1` |
| the MCP endpoint | `mcp_path` of `GET /api/version`, the `v1` of `/mcp/v1` | a change of a tool a client has to follow |
| the `metadata` block | `schema_version` of the block | its shape changes, so that a stored answer can be told from one in a later shape |
| the web app | `app/package.json`, its own [changelog](https://github.com/earthobservations/wetterdienst/blob/main/CHANGELOG_APP.md) | its own releases, see [The web app and the image](#the-web-app-and-the-image) |

## What each surface promises

| Surface | Frozen from 1.0 | What holds it |
| --- | --- | --- |
| [Python API](#python-api) | the top-level exports, `Wetterdienst`, the requests, the results, `Settings` and `Options`, the exceptions, the metadata enums, the output schemas | snapshot and tests: a change is a diff in the pull request; the Python-surface baseline refuses a name or a signature of the last release that is gone |
| [Command line](#command-line) | commands, options, choices, defaults, the shape of the output, the exit codes 0, 1 and 2 | the `--help` snapshot, the command-line baseline, the parity tests, the exit-code test |
| [REST API](#rest-api) | the `/api/v1` routes, their parameters, the response and problem shapes, the statuses | the OpenAPI snapshot, and a check against the last release that refuses a break, a changed default or a tighter bound |
| [MCP](#mcp) | the names of the tools, their arguments and answers | generated from the REST routes; the names are listed in the docs and tested; the MCP baseline refuses a tool or an argument of the last release that is gone |
| [Parameter names](#parameter-names-units-and-timestamps) | the canonical names and what they mean | the parameter table; a rename is refused with a hint; the parameter baseline refuses a name of the last release that is neither there nor renamed |
| [Provider metadata](#provider-metadata-licence-and-credit-line) | the members of the licence, the attribution and the provider description | the response models |
| [The host](#the-host-settings-environment-extras) | the `WD_*` variables | the names of the settings and options are in the Python snapshot |

Besides the OpenAPI document, four surfaces are held against what the last release offered: the command line, the
Python surface, the MCP tools and the parameters of every dataset. `tests/baselines/` has each as that release
offered it (`cli.baseline.json`, `surface.baseline.json`, `mcp.baseline.json`, `parameters.baseline.json`; the
comparison of each is the module of the same name), and `tests/baselines/test_baselines.py` fails when the code no
longer offers something the baseline does or asks more of a call: what a release offered must still be offered, and
an addition passes, as for the OpenAPI document. A break that is meant is named in the `ACCEPTED_BREAKS` of its
module with a reason, together with a **Breaking** changelog entry; an entry that no break is behind any more
fails as stale. A baseline is written only in a release commit, with `uv run poe contracts:baseline` (which writes the
OpenAPI one too), and each says which release it is of (`x-release`), which a test holds to `pyproject.toml`; see
[Release strategy](https://github.com/earthobservations/wetterdienst/blob/main/.github/RELEASE_STRATEGY.md).
The baselines are those of 0.162.0 until the next release.

## What counts as breaking

One list for every surface. A change of any of these to something a frozen surface offers is breaking:

- removing or renaming a name a caller writes or reads: a function, a method, an argument or keyword, an attribute or
  a field of a result, a column, a command, an option, a path, a query parameter, a member of an answer, a tool, an
  environment variable, a canonical parameter, an enum member (a resolution, a period, a choice of an option);
- changing a type, a dtype, a unit, a default, the place or order of a column, a status code, an exit code, the
  kind of problem an error is, or how a timestamp is to be read (the start or the end of an interval, the zone);
- making an optional argument or parameter required, or adding a required one;
- an exception raised where a value was returned, or a value (an empty frame, a null) where an exception was raised.

Not breaking, and so possible in a minor release:

- adding an optional argument, parameter, option, command, tool, endpoint, member of an answer, column, environment
  variable, enum member, exception class below an existing one, provider, network, dataset or parameter;
- a new `warnings` code in the `metadata` block and a new problem `type`: a client reads the ones it knows, and the
  `status` of a problem is there for the rest;
- improving a message, a description, a hint, the text of `--help`, the descriptions and instructions of the MCP
  tools, a log line;
- fixing a defect so that the library does what its documentation says.

A correction of what a provider's values mean or how they are stamped (a unit, a timestamp that was an hour off, a
parameter that was mapped to the wrong quantity) is marked **Breaking** in the changelog, though no name changes,
because a stored series no longer joins the new one. It has been announced so every time so far, and from 1.0 it is
the rule, with the entry saying what to do with stored values. It is the exception to the list above: it is made in a
minor release, not a major (see below). Nothing detects a changed value, so a reviewer has to catch a correction that
is not marked; it is not held by a test.

### Which release a break takes

From 1.0.0 a break of a frozen surface takes a **major** release, announced as **Breaking**, with two exceptions that
are made in a minor release, each with a **Breaking** entry:

- **A correction of data** (above).
- **An upstream source that has ended**: a provider, a network or a parameter whose source no longer exists, so that
  nothing is left to serve, is removed in a minor release. It is the one exception to "a removal is only in a major
  release" (see [Deprecation](#deprecation)).

A rename is no break in a minor: the old name keeps working as an alias, with a warning, for at least two minor
releases, and is removed only in a major (see [Parameter names](#parameter-names-units-and-timestamps)). The floor
of Python is a promise and the floor of a library is not, see [Dependencies and platforms](#dependencies-and-platforms).

## What is not promised

These may change in a minor or a patch release, with a changelog entry where a caller can notice:

- `wetterdienst.provider.*` internals (the `parser`, `fileindex`, `download` and `values` modules of a provider; not
  the request class a package exports, which is frozen, see [Python API](#python-api)), `wetterdienst.util`, the
  model internals, and every name that starts with an underscore;
- the texts of error messages, hints (`Did you mean`), `detail` of a problem, the `message` of a warning and the log;
- the HTML pages of the server (the index page), and the pixels of an image: its format, its size and its data are
  asked for, how it is drawn is not;
- which parameters a provider offers in a dataset: a provider can gain one, and one whose upstream source has ended is
  removed in a minor release, announced as **Breaking** (see [Which release a break takes](#which-release-a-break-takes));
  any other removal is a break;
- the values: a reading is what the provider published; a provider that revises its data revises the answer.

## Python API

The frozen surface is the one a script is written against:

- **the top-level exports**, `wetterdienst.__all__`: `Wetterdienst`, `Settings`, `Options`, `Period`, `Resolution`,
  `Info`, `Author`, `WetterdienstError` and its kinds `RequestError`, `NotFoundError`, `ConfigurationError`,
  `UpstreamError` and `ExportRefusedError`, `__appname__` and `__version__`;
- **`Wetterdienst`** and its methods (`resolve`, `resolve_standalone`, `discover`, `get_provider_names`,
  `get_network_names`, `is_standalone`, `is_configured`, `is_valid`), the request class each network resolves to, and
  its constructor arguments, and `TimeseriesRequest` and its public methods;
- **the import path of a request class**: the package of its network exports it under its name
  (`from wetterdienst.provider.dwd.observation import DwdObservationRequest`), which `Wetterdienst.resolve` is the
  other way to. The `api.py`, `values.py` and the other modules behind it are not frozen;
- **the results**, `StationsResult`, `ValuesResult`, `InterpolatedValuesResult`, `SummarizedValuesResult` and
  `HistoryResult`: their fields, their public methods and the signatures the [guide](python-api.md#results) shows.
  A result is frozen, built by keyword only, compares by what it holds and is unhashable; what the library keeps for
  itself (`_df_all`, `_stations_filter`, `_rank`) is private;
- **the output schemas**: the columns, their dtypes and their order in the frame of the stations (`STATIONS_SCHEMA`),
  of the long and the wide values (`LONG_SCHEMA`, `WIDE_SCHEMA`), and of an interpolated and a summarized result.
  A column of its own that a provider adds to its stations frame is an addition;
- **`Settings` and `Options`**: the names of their fields, which are the `WD_*` and `WD_TS_*` variables;
- **the exceptions**: `wetterdienst.exceptions`, each class with the kind it belongs to and the built-in classes it
  keeps (`ValueError`, `OSError`, ...), so that an `except` written against one keeps catching it;
- **the metadata enums**, `Period` and `Resolution`: their members and values.

What holds it: `tests/public_surface.snapshot.json` (the exports, the members of the enums, the field names of
`Settings` and `Options`, the signatures of `Wetterdienst`, `TimeseriesRequest` and the constructor of each request,
and the import path of each request class), `tests/model/test_results.py` (the results), `tests/test_exceptions.py`
(the exceptions), `tests/model/test_output_schema.py` (the schemas) and `tests/typed_caller.py` (the types a checker
makes of a script, built against the wheel). A change to any of them is a change to a committed file in the same pull
request, where it shows as a diff. `uv run poe surface:snapshot` writes the first one anew.

The snapshot shows a change and does not refuse one, so `tests/baselines/surface.baseline.json` is the same surface as
the last release offered it, and `tests/baselines/test_baselines.py` refuses what the code no longer offers: an export, a
member of `Period` or `Resolution` (or one with another value), a field of `Settings` or `Options`, a method of
`Wetterdienst` or `TimeseriesRequest`, a network, a request class that its package no longer exports, and a signature
that a call written against the old one no longer fits (a parameter that is gone, became required or keyword-only,
changed its default, was reordered, or was inserted before one that a call passes by position; a new optional
parameter after the others passes). The constructor of a network whose extra is not installed is compared by the
name of its network only.

Not yet held by a test: against the last release, the results, the exceptions and the output schemas (each is held as
it is now, by the tests above, and not compared with what the release had); the methods of the reader that
`stations.values()` returns; and the defaults and the allowed values of the settings and the options, of which the
baseline has the names.

## Command line

The command line is a client of the same functions as the REST API: it renders a result through the same code, so the
same request gives the same output, and the options are the parameters of the REST API.

- **Commands and options**: `about` (`auth`, `coverage`, `fields`, `glossary`, `providers`), `alerts`, `cache`,
  `history`, `info`, `interpolate`, `issues`, `radar`, `restapi`, `stations`, `stripes` (`image`, `stations`),
  `summarize` and `values`, with their options, the choices of an option and its default. `tests/ui/cli/help.snapshot.txt`
  is the `--help` of every command; `uv run poe cli:snapshot` writes it anew after an intended change.
  `tests/baselines/cli.baseline.json` is every command and every spelling of every option as the last release offered
  it (see below).
- **The spelling**: an option is the REST query parameter and the MCP argument of the same request with hyphens for
  underscores (`--name-threshold` is `name_threshold`), a list is plural and comma-separated. A test holds every
  parameter of every request to that (`tests/ui/test_surface_parity.py`).
- **The output**: the JSON, GeoJSON, NDJSON and CSV a command writes are what the REST API answers, `metadata` block
  included, and the data goes to stdout and the sentences to stderr. An empty result is an answer.
- **Exit codes**: `0` an answer (empty or not), `1` a failure that is not the request's to rephrase, `2` a request
  that cannot be served as phrased. No command has another code, and the three are frozen; a code of its own for an
  upstream failure would be a break. The table is on the [command line page](cli.md#exit-codes), and
  `tests/ui/test_exit_codes.py` holds every explicit exit to the status the REST API answers the same failure with.
- **The environment**: the `WD_*` variables of the [settings](settings.md).

Not frozen: the prose of `--help` and its examples, the sentences on stderr, and how click lays out its help.

The help snapshot shows a removed option and does not refuse it, so `tests/baselines/test_baselines.py` holds the
command line to `tests/baselines/cli.baseline.json`: a command, an option or a spelling of one that is gone, a changed
type, `nargs`, `multiple`, flag, environment variable or default, a choice that is gone, a narrower range, an option
that was free text and takes choices now, an option that became required or a new one that is, and any change of the
exit codes (0, 1, 2) fail it; a new command, option, spelling or choice, a wider range and an option that stopped being
required pass.

Not yet held by a test: the shape of each command's output is held where a parity test compares it with the REST
answer and nowhere else, and a command that prints a table for a person (`about`, `info`, `cache`) is not held to a
shape.

## REST API

The routes are served under `/api/v1`, and `/api` is a hidden alias of the current version: the same routes and
handlers, not deprecated, not in the OpenAPI document, and moving with the next version. A client that must not move
with it uses `/api/v1`. See [Versioning](restapi.md#versioning).

Frozen:

- the **routes and methods**, with their `operationId` (a change of one is a break, and so is the name of the MCP tool
  that is found by it);
- the **query parameters**: their names, their type, the members of an enum, whether a list is `form` and not
  exploded, which are required, and their defaults and bounds (below);
- the **statuses** a route answers and the **kind of problem** each is (the table of
  [Errors](restapi.md#errors)): the `type` of a problem is what a client branches on and a kind keeps its status;
- the **shape of the answers**: the members of the JSON, GeoJSON and NDJSON, their types and which of them are always
  there, in particular the [`metadata` block](restapi.md#response-metadata) of every answer and the members of its
  `provider.license`, `request`, `counts`, `crs` and `warnings`, and the headers the OpenAPI document declares;
- the **timestamp**: ISO 8601 in UTC, to the microsecond, with its offset.

`tests/ui/openapi.snapshot.json` is the OpenAPI document as last reviewed (`uv run poe openapi:snapshot` writes it
anew), so that every change shows in a diff. `tests/ui/openapi.baseline.json` is the document of the last release, and
`tests/ui/test_openapi_baseline.py` fails when the served document no longer offers something the baseline did: a
path, a method, an `operationId`, a parameter and its type, an enum member, a status, a media type, a header, a member
of an answer and its type, or a request that asks for more. Additions pass. A break that is meant is named in
`ACCEPTED_BREAKS` of `tests/ui/openapi_diff.py` with its reason, together with a **Breaking** changelog entry; the
baseline is refreshed in each release commit and `ACCEPTED_BREAKS` emptied. From 1.0.0 a break of `/api/v1` is not
made: it is `/api/v2`, and `/api/v1` is served for at least two minor releases after `/api/v2` appears, announced by
the `Deprecation` and `Sunset` headers (see [Deprecation](restapi.md#deprecation)). The routes, the problem kinds and
the statuses they are answered with are also held by `tests/ui/test_api_contract.py` and `tests/ui/test_operations.py`.

A request is asked more of when a parameter, or a member of a request body, takes less than it did, and by convention
that is a break: a changed `default` (what an omitted parameter means), a tighter bound (a larger `minimum`,
`minLength` or `minItems`, a smaller `maximum`, `maxLength` or `maxItems`, a bound where there was none), a `pattern`
that was added or changed, and an enum that lost members. `tests/ui/openapi_diff.py` holds it. A looser bound or no
pattern is an addition and passes.

What may change in a minor release: a new route, an optional query parameter, a member of an answer, an enum member,
a problem kind, a warning `code`, a header, a looser bound; the `title`, `detail`, descriptions and examples of the
document; and the defaults of the server's limits, which `GET /api/version` reports.

Not yet held by a test: the check against the last release does not compare the formats, descriptions and examples
of the document, nor the defaults and bounds of an answer; a change of what an answer means (a unit, a statistic)
is for the changelog; that a break raises `api_version` is not checked; and that `/api/v1` keeps serving for two minor
releases after a `/api/v2` exists is written down and not held by a test.

## MCP

The endpoint is `/mcp/v1`, and `/mcp` is its alias for the current version, as `/api` is for `/api/v1`. The tools
are the REST routes, generated from them: a tool has the name given in the table of the [MCP page](mcp.md#the-tools),
the arguments are the query parameters of its route with the same names, and the answer is the REST answer.

- A breaking change of a tool (its name, an argument, the answer) comes with `/mcp/v2`, and `/mcp/v1` keeps serving the
  tools as they were for at least two minor releases, announced in the changelog.
- A new tool, an optional argument and a new member of an answer are not breaking.
- An argument a tool does not take is refused with the names of those it takes.
- The descriptions of the tools and the instructions the server gives are written for agents and are improved without
  a new version.
- The endpoint is stateless: it creates no session.

The generation from the routes means the baseline check of the OpenAPI document covers the arguments and answers of the
tools. The 14 names of the tools (`_TOOL_NAMES` in `ui/mcp.py`) are held to the list on the MCP page by
`tests/test_docs.py`, and `tests/ui/test_restapi.py` calls every tool of that list.

`tests/baselines/mcp.baseline.json` is the input schema of every tool as the last release offered it (types, enum
members, defaults, bounds and which arguments are required; not titles and descriptions), and
`tests/baselines/test_baselines.py` fails when a tool or an argument is gone, a type changed, an argument became
required, a default changed, a bound tightened or a pattern was added, by the rules of the OpenAPI check above. The
schemas depend on the versions of FastAPI, pydantic and FastMCP, so they are compared where those are the locked ones.

## Parameter names, units and timestamps

A canonical parameter name (`temperature_air_2m`, `wind_speed_mean`, `precipitation_amount`) is one row of the
parameter table (`wetterdienst.metadata.parameter_table`), which every provider's metadata is tested against. It means
one quantity, in one unit type, with the statistic its name says (see [The statistic in a name](../data/parameters.md#the-statistic-in-a-name)),
whoever reports it. Frozen: a name that was released keeps meaning what it meant.

- **Until 1.0 a rename is a hard break, with a hint.** The old name is not an alias. A request, a filter, a wide column name and
  a `geo_station_distance` key that spells it is refused with an error that names the new one (`'wind_speed' was
  renamed to 'wind_speed_mean' in this dataset`), from the tables of `wetterdienst.metadata.renamed`:
  `RENAMED_PARAMETERS` and `RENAMED_PARAMETERS_IN_DATASET` for the parameters, `RENAMED_COLUMNS` for frame columns,
  `RENAMED_RESOLUTIONS`, `RENAMED_ARGUMENTS` and `RENAMED_RESULT_MEMBERS`, and the request parameters of the REST
  API, the command line and the MCP tools. `tests/metadata/test_renamed.py` holds each entry to pointing from a name
  that is gone to one that exists, and `tests/metadata/test_gone_since_0_139_0.py` holds each parameter of 0.139.0 that
  is gone to the answer the [migration note](migrating.md) gives.
- **From 1.0 a rename keeps the old name as an alias.** The old name still works, with a warning that names the new
  one, for at least two minor releases, and is removed only in a major release. The hints above stay for the names
  that are already gone: they are not aliases and are not brought back. Nothing implements the alias yet and no test
  holds it.
- **A name that is removed** because the provider no longer publishes it, or never did, is refused as any name the
  provider does not have; the request is refused whole, naming each unknown parameter, and `on_unknown="warn"` asks
  for the older behaviour of dropping it with a warning.
- **Units** are those of the quantity (see [Units](units.md)); a change of one is breaking, and the correction of a
  wrong one is announced as such in a minor release (see [Which release a break takes](#which-release-a-break-takes)).
- **Timestamps** mean what [Time reference](../data/time_reference.md) says for each provider and resolution; a change
  of the stamp is breaking, and so is a correction of a wrong one, in a minor release.
- **Quality flags** are one string, `quality_flags`, of comma-separated tokens: the source's flag plain, further kinds
  as `kind:code`, the text of a missing value as the last token `raw:<text>`. What a code means is the provider's.

`tests/baselines/parameters.baseline.json` is every provider, network, resolution, dataset and parameter name as the
last release offered it, with the tables of renames of that release, and `tests/baselines/test_baselines.py` fails
when a name is gone: a provider, network, resolution or dataset (a resolution in `RENAMED_RESOLUTIONS` excepted), a
parameter that is neither in its dataset any more nor renamed, through the tables and as many times as it was renamed
since, to one that is, and an entry of the rename tables that was there. A new name or rename passes. A parameter
removed because its upstream source has ended is named in `ACCEPTED_BREAKS` of `tests/baselines/parameters.py`.

Not yet held by a test: the alias after 1.0, that it lasts two minor releases, and that a removal is in a major release
(the baseline counts a renamed name as kept, and does not know how long ago it was renamed).

## Provider metadata, licence and credit line

Every answer says where the data comes from and under what terms (`metadata.provider`, and `GET /api/providers`):
`license` with `spdx_id`, `name` and `url`, `attribution`, `copyright`, the names and the country of the provider
(`country_code` is null for a provider of several countries). The members are frozen with the answer's model. The
values are what the provider states, taken from its own terms: they change when a provider changes its terms or the
library reads them more closely, which is a fix and not a break; `spdx_id` is null where the terms have none (ECCC,
AEMET, IMGW, IPMA), and `license` is null only where a provider states no terms that could be read, which is then
named with its reason in `LICENSE_NOT_STATED` of `tests/ui/test_response_metadata.py` (empty today). The licence of the
data is the provider's, not wetterdienst's.

## The host: settings, environment, extras

The names of the `Settings` and `Options` fields are frozen, and so are the `WD_*` and `WD_TS_*` variables they read.
Adding a setting is an addition. The optional extras (`[export]`, `[mcp]`, ...) keep their names; what each installs is not promised
beyond what its feature needs. The environment variables, defaults and bounds are in [Settings](settings.md).

## The web app and the image

The web app is released on its own, as `app-v0.x` with a changelog of its own (`CHANGELOG_APP.md`). It is not part of
the 1.0 promise and is not given one: its number stays 0.x. It is a client of the REST API and is paired with a
backend, as the [app page](app.md) says: run versions of the two that were released together, because an app that is
older than its backend can fail on a request the backend has since changed, and a newer one on a route the older
backend lacks. A release of the app that needs a backend change is cut after the backend release that has it.

The Docker image is versioned with the backend. Its default port (7890), the user it runs as and the place of its
cache are in the [Docker page](docker.md); changes to them have been announced as **Breaking**, and are not yet held
by a test.

## Deprecation

One rule for every surface: what is deprecated keeps working for **at least two minor releases** before it is removed,
and it is announced in the changelog under **Deprecated** when it is deprecated, with what to use instead. A removal
is a **Breaking** entry, and from 1.0 it is made only in a major release. How the deprecation shows depends on the
surface:

| Surface | How a deprecated thing tells you |
| --- | --- |
| Python | a `DeprecationWarning` that names the replacement |
| command line | click's `(DEPRECATED: ...)` in the help, and a warning on stderr when it is used; stdout stays what it was |
| REST | `deprecated` in the OpenAPI document, a `Deprecation` header ([RFC 9745](https://www.rfc-editor.org/rfc/rfc9745)) on every response that uses it, a `Sunset` header ([RFC 8594](https://www.rfc-editor.org/rfc/rfc8594)) where a date is set, a `Link` with `rel="deprecation"`, and a `deprecated-parameter` warning in `metadata` for a parameter; see [Deprecation](restapi.md#deprecation) |
| MCP | the endpoint of the old version keeps serving for at least two minor releases after the next one appears |

Deprecated today:

| What | Since | Use instead | Removed |
| --- | --- | --- | --- |
| `Wetterdienst(provider, network)`, the constructor form that returns a class | 0.156.0 | `Wetterdienst.resolve(provider, network)`, `resolve_standalone` for `dwd/radar` and `dwd/alerts` | 1.0.0 |
| `wetterdienst stripes values`, which writes the image | 0.159.0 | `wetterdienst stripes image` | 1.0.0 |

Nothing is deprecated on the REST API and the MCP endpoint. The deprecations before these were removed after more
than two minor releases: the `ts_*` settings (deprecated in 0.148.0, removed in 0.160.0) and `use_nearby_station_distance`
of `summarize` (deprecated in 0.140.0, removed in 0.158.0).

Both are removed at 1.0.0, with the tag. `wetterdienst
stripes values` is then "No such command", and the name is **never reused** for other output: a command for the
yearly values that `/api/stripes/values` answers would get another name, as an addition.

Removal is a **Breaking** change, and so a major version from 1.0, with one exception: a provider, a network or a
parameter whose upstream source has ended is removed in a minor release, announced as **Breaking** (see
[Which release a break takes](#which-release-a-break-takes)). Not yet held by a test: the two minor releases (the code
has the mechanism for REST, `ui/deprecation.py`, and a test of it, but nothing checks the length of a period or that a
removal had a deprecation), that every `DeprecationWarning` names a removal version, and that a removal after 1.0 is
in a major release. The mechanism states the rule and does not enforce it.

## How a break is announced

1. The entry in `CHANGELOG.md` under `[Unreleased]` and then the release, marked **Breaking**, says what changed, what it
   means for a caller, what to use instead, and ends with the issue as `(GH-####)`. The
   [migration note](migrating.md) is collected from them.
2. A break of the OpenAPI document is named in `ACCEPTED_BREAKS` with its reason until the next release.
3. The release notes of the GitHub release say which breaking changes need action.
4. A rename is refused by the old name with an error that names the new one, where the old name cannot be kept
   (until 1.0; after it the old name is an alias with a warning, see
   [Parameter names](#parameter-names-units-and-timestamps)).
5. A deprecation is announced when it starts, see above.

Not yet held by a test: that a break has a **Breaking** entry, and that the entry says what to use instead.

## Dependencies and platforms

The supported Python is `>=3.11` (`requires-python`), and the dependency ranges are those of `pyproject.toml`.

- **The floor of Python is a promise.** Raising it is a break, announced as **Breaking** in the changelog (Python 3.10
  was dropped in 0.145.0, **Breaking**), and pip on an older Python keeps resolving the last release that supports it.
  Which version number it takes after 1.0 is not written down.
- **The floor of a library is not.** Raising it is a **Changed** entry and not **Breaking** (polars was raised from 1.15
  to 1.43 in 0.132.0, not marked), because what a caller writes does not change, only what the resolver may install.

Marking them the same way every time is a convention, and neither is held by a test.
