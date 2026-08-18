# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wetterdienst is a Python library providing unified access to weather, climate and hydrology data from many national providers (DWD, NOAA, ECCC, EA, NWS, Geosphere Austria, IMGW, WSV, Eaufrance, Météo-France, MeteoSwiss, met.no, SMHI, FMI, KNMI, DMI, CHMI, RMI, AEMET, IPMA, LHMT, Met Office, Eumetnet). [polars](https://pola.rs/) is the primary dataframe library throughout.

## Commands

### Python backend (`uv run poe <task>`)

```bash
uv run poe test              # full suite (parallel + cflake)
uv run poe "test:parallel"   # parallel only (faster for dev)
uv run poe coverage          # tests with coverage
uv run poe format            # ruff format + lint --fix
uv run poe lint              # check only, no fixes
uv run poe typecheck         # ty check src/wetterdienst
uv run poe unused            # deptry unused-dependency check
uv run poe sync              # uv sync

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
```

### Docker (`compose.yml`)

```bash
docker compose --profile full up       # backend + app
docker compose --profile backend up    # backend only, port 3000
docker compose --profile app up        # app only, port 4000
```

### CLI / REST API

```bash
wetterdienst restapi --listen 0.0.0.0:3000
wetterdienst stations --provider dwd --network observation --parameters daily/kl --periods recent --all
wetterdienst values --provider dwd --network observation --parameters daily/kl --periods recent --station 00011
```

CLI commands (`ui/cli.py`): `stations`, `values`, `history`, `interpolate`, `summarize`, `stripes`, `radar`, `coverage`, `restapi`, `about`.

## Architecture

### Core data model

Layered flow: `Request → StationsResult → ValuesResult`.

- **`Wetterdienst`** (`src/wetterdienst/api.py`): registry/factory that lazily resolves provider+network combos to request classes.
- **`TimeseriesRequest`** (`model/request.py`): abstract base dataclass all provider request classes extend — parameter parsing, date validation, station filtering.
- **`TimeseriesValues`** (`model/values.py`): abstract base for fetching observation data, bound to a `StationsResult`.
- **`StationsResult` / `ValuesResult`** (`model/result.py`): wrap polars DataFrames; provide `to_dict/to_json/to_ogc_feature_collection/to_file/to_target`, DuckDB SQL filtering, and plotting.
- **`Settings`** (`settings.py`): pydantic settings; env vars prefixed `WD_` (caching, unit conversion, interpolation defaults, provider auth via `WD_AUTH__*`).

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

DWD has multiple networks: `observation`, `mosmix`, `dmo`, `road`, `radar`, `derived`, `swsmos`, `alerts`.

### Network / caching

All HTTP goes through `util/network.py`, wrapping fsspec with TTL caching and `stamina` retry logic. Cache dir is configurable via `WD_CACHE_DIR`.

### UI layer

- **CLI** (`ui/cli.py`): click/cloup-based.
- **REST API** (`ui/restapi.py`): FastAPI app mirroring the CLI; starts via `wetterdienst restapi`.
- **MCP** (`ui/mcp.py`): Model Context Protocol server exposing the same tools.
- **App** (`app/`): Nuxt 3 SPA (SSR disabled) calling the REST API; `NUXT_PUBLIC_API_BASE` sets the backend URL.

### Export / interpolation

- `ExportMixin` (`io/export.py`): export to CSV/JSON/Excel/Zarr files, SQLite/PostgreSQL/CrateDB/InfluxDB, and DuckDB SQL (`[export]` extra).
- `core/interpolate.py` and `core/summarize.py`: spatial interpolation and weighted summarization for a target point (`[interpolation]` extra: scipy, shapely, utm).

Optional dependency groups include `export`, `interpolation`, `restapi`, `sql`, `mcp`, `bufr`.

## Conventions

- **Polars throughout**: use `pl.DataFrame`/`pl.LazyFrame`; avoid pandas in new code (it appears only in some export adapters).
- **Parameters** are referenced as `"resolution/dataset"` or `"resolution/dataset/parameter"` strings, or as typed `ParameterModel`/`DatasetModel` objects.
- **New providers**: follow the strict metadata dict schema — copy an existing `provider/*/metadata.py` before adding one.
- **Test markers**: `remote` (needs internet), `slow`, `sql`, `explorer`, `cflake` (concurrency-flaky). Remote tests run by default locally; skip with `-m "not remote"`.
- **Ruff** is the linter/formatter, line length 120. **`ty`** is the type checker. Run `uv run poe format` before committing.
