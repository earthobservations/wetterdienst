# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wetterdienst is a Python library providing unified access to weather, climate and hydrology data from many national providers (DWD, NOAA, ECCC, EA, NWS, Geosphere Austria, IMGW, WSV, Eaufrance, Météo-France, MeteoSwiss, met.no, SMHI, FMI, KNMI, DMI, CHMI, RMI, AEMET, IPMA, LHMT, Met Office, Eumetnet). [polars](https://pola.rs/) is the primary dataframe library throughout.

## Commands

### Python backend (`uv run poe <task>`)

```bash
uv run poe test              # full suite (parallel + cflake)
uv run poe "test:parallel"   # parallel only (faster for dev)
uv run poe "test:offline"    # the offline selection, on its own -- see the marker note below
uv run poe coverage          # tests with coverage
uv run poe format            # ruff format + lint --fix
uv run poe lint              # check only, no fixes
uv run poe typecheck         # ty check src/wetterdienst
uv run poe "typecheck:installed"  # the caller script against the built wheel (needs the network)
uv run poe unused            # deptry unused-dependency check
uv run poe sync              # uv sync
uv run poe "contracts:snapshot"  # regenerate the OpenAPI, CLI --help and Python-surface snapshots after an intended change
uv run poe "contracts:baseline"  # the baselines of the last release (OpenAPI, CLI, Python surface, MCP, parameters): in a release commit only
uv run poe "frames:snapshot"  # regenerate tests/provider/frames.snapshot.json, the frames the core hands out for every offline provider test, after an intended change to one
uv run poe "renames:baseline"  # the parameters of 0.139.0 that are gone (tests/metadata/gone_since_0_139_0.json): when a 0.139.0 name is renamed, removed (add it to `REMOVED`) or back
uv run poe docs              # sphinx build into docs/_build/html, as Read the Docs runs it
uv run poe "docs:clean"      # remove docs/_build
uv run poe "docs:linkcheck"  # check the external links of the docs (needs the internet)

# Single file / single test
uv run pytest tests/provider/dwd/observation/test_api.py -vvv
uv run pytest tests/ -k "test_my_function" -vvv
```

### App (`cd app`, Nuxt 3 / Vue 3, pnpm)

```bash
pnpm install
pnpm dev            # dev server, port 4000
pnpm build
pnpm lint           # oxlint + eslint
pnpm test:ci        # vitest run
pnpm test:e2e       # playwright
pnpm test:a11y      # the axe accessibility spec, on request only (not in test:e2e); see app/ACCESSIBILITY.md
```

### Docker (`compose.yml`)

```bash
docker compose --profile full up       # backend + app
docker compose --profile backend up    # backend only, port 7890
docker compose --profile app up        # app only, port 4000
```

### CLI / REST API

```bash
wetterdienst restapi --listen 0.0.0.0:7890
wetterdienst stations --provider dwd --network observation --parameters daily/kl --periods recent --all
wetterdienst values --provider dwd --network observation --parameters daily/kl --periods recent --stations 00011
```

CLI commands (`ui/cli.py`, as `wetterdienst --help` prints them): `about` (subcommands `auth`, `coverage`, `fields`, `glossary`, `providers`), `alerts`, `cache`, `history`, `info`, `interpolate`, `issues`, `radar`, `restapi`, `stations`, `stripes`, `summarize`, `values`.

## Architecture

### Core data model

Layered flow: `Request → StationsResult → ValuesResult`.

- **`Wetterdienst`** (`src/wetterdienst/api.py`): registry/factory that lazily resolves provider+network combos to request classes.
- **`TimeseriesRequest`** (`model/request.py`): abstract base dataclass all provider request classes extend — parameter parsing, date validation, station filtering.
- **`TimeseriesValues`** (`model/values.py`): abstract base for fetching observation data, bound to a `StationsResult`.
- **`StationsResult` / `ValuesResult`** (`model/result.py`): wrap polars DataFrames; provide `to_dict/to_json/to_ogc_feature_collection/to_file/to_target`, DuckDB SQL filtering, and plotting.
- **`Settings`** (`settings.py`): the host's pydantic settings, process-wide and read by providers; env vars prefixed `WD_` (cache, network client, certifi, BUFR, REST SQL, provider auth via `WD_AUTH__*`). Per-request behaviour is not here.
- **`Options`** (`options.py`): frozen pydantic settings per request, passed as `options=` (an `Options` or a dict); how values come back (shape, units, skipping) and the interpolation distances. Env vars prefixed `WD_TS_`. The old `Settings` `ts_*` paths are gone: `Settings` refuses them with an error that names the option to pass instead (`refuse_removed_ts_settings` in `settings.py`).

### Metadata system

Provider metadata (resolutions, datasets, parameters, periods) is declared as nested dicts in each provider's `metadata.py` and converted to pydantic models via `build_metadata_model()` (`model/metadata.py`): `MetadataModel → ResolutionModel → DatasetModel → ParameterModel`. Shared enums live in `metadata/`: `Parameter` (canonical snake_case names), `Resolution`, `Period`, `CacheExpiry`.

### Provider structure

Each provider lives under `src/wetterdienst/provider/<provider>/`, often per-network. Standard layout:

```
provider/<provider>/[<network>/]
  __init__.py     # exports the main Request class
  api.py          # concrete TimeseriesRequest subclass
  metadata.py     # metadata dict + build_metadata_model()
  values.py       # concrete TimeseriesValues subclass
  parser.py       # raw data parsing
  fileindex.py    # file listing/indexing from source
  download.py     # data fetching helpers
```

DWD has multiple networks: `observation`, `mosmix`, `dmo`, `road`, `radar`, `derived`, `swsmos`, `poi`, `phenology`, `alerts`.

### Network / caching

All HTTP goes through `util/network.py`, wrapping fsspec with TTL caching and `stamina` retry logic. Cache dir is configurable via `WD_CACHE_DIR`. A connection that cannot be made is a `NoInternetError` (URL in the message, the OS error as `__cause__`), raised by `File.raise_if_exception` and by the file listings for every provider, catalogues included; a provider that reads `file.content` itself must `raise` it, never answer an empty frame. `list_remote_files_fsspec` answers `[]` for a directory that is not there, or is empty; `list_remote_directory_fsspec` raises `FileNotFoundError` for one that is not there. Downloads, posts and listings retry a transient failure through one predicate (`_worth_retrying`): a reset, a timeout, a 5xx and a handshake the peer answers wrongly (`_is_transient_tls_failure`: `WRONG_VERSION_NUMBER`, `INVALID_SESSION_ID`), never a certificate that does not verify (`ssl.SSLCertVerificationError`), a handshake the two cannot agree on, or a 4xx.

The processes that share a cache directory take turns on its metadata file and its sweep through a lock file beside the directory (`<dir>.lock`, `filelock`; `_locked_across_processes`, always taken after `_cache_dir_lock`, never around a download). A holder that does not let go within 30 s (the timeout; a load waits 1 s) costs that wait once, and then every save and sweep of that directory for a minute, which are only tried and skipped, while its reads go ahead without the lock (on Windows a read that meets a replace can then fail). The wait holds the process-wide `_cache_dir_lock`, so every cache miss of the process stalls behind it. No request fails. The OS drops the lock (`flock`, `msvcrt`; never the soft lock, `fallback_to_soft=False`) of a process that is killed, so there is no stale one.

`TimeseriesValues.query` has the files of the next `Settings.fetch_ahead` stations (4) downloaded into the cache while one is parsed, for a provider that names them in `_files_ahead` (`model/fetch_ahead.py`; dwd/observation, dwd/derived, chmi, imgw/meteorology, smhi/observation). It raises nothing itself: the provider's own download at the station's turn finds the files in the cache and raises what it always raised. It limits its own connections only (not the station in hand's); interpolate and summarize switch it off. A new provider whose files are one set per station implements the hook with the URLs and the expiry its collection uses, and a test in `tests/model/test_files_ahead_hooks.py` holds the hook to the collection. `tests/conftest.py` switches it off for every test but those of `tests/model/test_fetch_ahead.py`.

### UI layer

- **CLI** (`ui/cli.py`): click-based.
- **REST API** (`ui/restapi.py`): FastAPI app mirroring the CLI; starts via `wetterdienst restapi`.
- **MCP** (`ui/mcp.py`): Model Context Protocol server exposing the same tools.
- **App** (`app/`): Nuxt 3 SPA (SSR disabled) calling the REST API; `NUXT_API_BASE` (private runtime config `apiBase`; the old `NUXT_PUBLIC_API_BASE` still works, deprecated) sets the backend URL.

### Export / interpolation

- `ExportMixin` (`io/export.py`): export to CSV/JSON/Excel/Zarr files, SQLite/PostgreSQL/CrateDB/InfluxDB, and DuckDB SQL (`[export]` extra).
- `core/interpolate.py` and `core/summarize.py`: spatial interpolation and weighted summarization for a target point (`interpolate()` needs the `[interpolation]` extra: scipy, shapely, utm; `summarize()` needs no extra).

Optional dependency groups include `export`, `interpolation`, `restapi`, `sql`, `mcp`, `bufr`.

## Conventions

- **Polars throughout**: use `pl.DataFrame`/`pl.LazyFrame`; avoid pandas in new code (it appears only in some export adapters).
- **Parameters** are referenced as `"resolution/dataset"` or `"resolution/dataset/parameter"` strings, or as typed `ParameterModel`/`DatasetModel` objects.
- **New providers**: follow the strict metadata dict schema — copy an existing `provider/*/metadata.py` before adding one, and declare its `extent` (where its stations are: `scope`, `continents` declared by hand as the areas it is meant to serve, `country_codes` for a regional one, `bbox`, which `test_station_catalogues_live.py` and the stubs hold to the list; a national network that has a `COUNTRY_BBOX` has that box). Add a stub of its station catalogue to `tests/provider/station_catalogue_stubs.py` (rows of the real list, served through its own reader), and its country's bounding box to `COUNTRY_BBOX` in `station_catalogue.py` if it is one country's, so the catalogue rules apply to it; `test_station_catalogues_live.py` applies them to the live list. Map the source's missing-value sentinel (`-999`, `-99`, `99.9`, a text such as `---`) to null in the provider's reader, before the unit conversion, and per column where the source does, through `null_sentinels` (`model/quality_flags.py`), which returns the cleaned value and the text the source wrote with it: that text is the last token of `quality_flags`, `raw:-999`, written as the source writes it (`join_quality_flags(plain, raw=raw)`); add a stub of its values, with the sentinel written as the source writes it and each `raw:` token it must carry named in `tokens`, to `tests/provider/value_stubs.py` (or the network and the reason it has none yet to `NO_STUB`). A test under `tests/provider` that goes through `TimeseriesValues` is held to `tests/provider/physical_ranges.py` (generous ranges, in the returned unit; remote tests only with `WD_CHECK_RANGES_REMOTE=1`, and `@pytest.mark.synthetic_values` for a test that serves numbers that are no readings), which catches a sentinel that is outside the range of its parameter; one that looks like data (99.9 % humidity, 0 for "not measured") is only caught by reading the source's documentation, which the stub's comment should quote.
- **Frame snapshot**: every offline test under `tests/provider` that collects values or stations is held to the frame the core produced for it, in `tests/provider/frames.snapshot.json` (schema, row count, a hash of the rows; see `tests/provider/frames.py`). A new test, or a change to what a fixture's frame holds, is a regenerated snapshot in the same PR (`uv run poe "frames:snapshot"`, one process), and a refactor that is meant to change nothing leaves its diff empty. A network with no offline fixture is named with the reason in `test_frames_snapshot.py`. What a provider must hand to the core is the docstring of `_collect_station_parameter_or_dataset` (values) and of `_all` (stations).
- **Licence of a provider**: its metadata declares `license` (a `LicenseModel`: SPDX identifier or null, name, URL of the terms the provider states, not one you assume) and `attribution` (the credit line, in the provider's words where it states one), both of which every answer reports in its `metadata` block. A provider that states no terms declares `"license": None` and is named with the reason in `LICENSE_NOT_STATED` of `tests/ui/test_response_metadata.py`. The OpenAPI document is held to `tests/ui/openapi.snapshot.json`: a change to the REST contract regenerates it with `uv run poe openapi:snapshot`, and the diff is read in the pull request.
- **Test markers**: `remote` (needs internet), `slow`, `sql`, `explorer`, `cflake` (concurrency-flaky), `synthetic_values` (tests under `tests/provider` that serve numbers that are no readings, so the physical-range check stands aside). Remote tests run by default locally; skip with `-m "not remote"`. That selection is offline and enforced: `tests/conftest.py` refuses non-local names and addresses for every unmarked test, so a test reaching upstream needs the marker or a rewrite that does without the network. It catches a connection being made, not one already open or made before the per-test fixture is in place; `tests/conftest.py` lists what that leaves out. Check a new test with `uv run poe "test:offline"` rather than `poe test`, which runs the remote tests too and so warms the cache and the connection an unmarked test would then be served from.
- **Ruff** is the linter/formatter, line length 120. **`ty`** is the type checker. Run `uv run poe format` before committing.
- **Changelog**: entries record changes to wetterdienst that a caller can observe — behaviour, API, dependencies, security, and docs that stated a wrong fact. Not new tests, test helpers or docs consistency (notation, row order, padding). Say what changed and what it means for a caller, then `(GH-####)`; a breaking change also says what to do instead. Wrap at 100 columns and keep it to a few lines — the `[Unreleased]` entries run a median of 5 and none past 10. The reasoning for the change belongs in the commit body, not here.
