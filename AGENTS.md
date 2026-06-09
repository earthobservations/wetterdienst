# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wetterdienst is a Python library providing unified access to weather/hydrology data from multiple providers (DWD, NOAA, ECCC, EA, NWS, Geosphere Austria, IMGW, WSV, Eaufrance). It uses [polars](https://pola.rs/) as the primary dataframe library throughout.

## Commands

### Python Backend

```bash
# Run all tests (parallel + cflake tests)
uv run poe test

# Run tests in parallel only (faster for development)
uv run poe "test:parallel"

# Run a single test file
uv run pytest tests/provider/dwd/observation/test_api.py -vvv

# Run a single test by name
uv run pytest tests/ -k "test_my_function" -vvv

# Run with coverage
uv run poe coverage

# Format and lint
uv run poe format

# Lint only (no fix)
uv run poe lint

# Type checking
uv run poe typecheck

# Check for unused dependencies
uv run poe unused

# Sync dependencies
uv run poe sync
```

### Frontend (Nuxt 3 / Vue 3)

```bash
cd frontend

# Install dependencies
pnpm install

# Dev server (runs on port 4000)
pnpm dev

# Build
pnpm build

# Lint
pnpm lint

# Unit tests
pnpm test:ci

# E2E tests
pnpm test:e2e
```

### Docker (full stack)

```bash
# Run backend + frontend
docker compose --profile app up

# Backend only (port 3000)
docker compose --profile backend up

# Frontend only (port 4000)
docker compose --profile frontend up
```

### REST API

```bash
# Start the REST API server
wetterdienst restapi --listen 0.0.0.0:3000

# CLI usage
wetterdienst stations --provider dwd --network observation --parameters daily/kl --periods recent --all
wetterdienst values --provider dwd --network observation --parameters daily/kl --periods recent --station 00011
```

## Architecture

### Core Data Model

The library follows a layered pattern: `Request → StationsResult → ValuesResult`

- **`Wetterdienst`** (`src/wetterdienst/api.py`): Registry/factory that lazily resolves provider+network combos to their request classes.
- **`TimeseriesRequest`** (`src/wetterdienst/model/request.py`): Abstract base dataclass all provider request classes extend. Handles parameter parsing, date validation, and station filtering.
- **`TimeseriesValues`** (`src/wetterdienst/model/values.py`): Abstract base for fetching actual observation data, bound to a `StationsResult`.
- **`StationsResult`** / **`ValuesResult`** (`src/wetterdienst/model/result.py`): Wrap polars DataFrames and provide `to_dict()`, `to_json()`, `to_ogc_feature_collection()`, `to_file()`, `to_target()`, SQL filtering via DuckDB, and plotting methods.
- **`Settings`** (`src/wetterdienst/settings.py`): Pydantic settings model; all env vars are prefixed `WD_`. Controls caching (`WD_CACHE_DISABLE`, `WD_CACHE_DIR`), unit conversion, interpolation defaults, etc.

### Metadata System

Provider metadata (parameters, resolutions, datasets, periods) is declared as nested dicts in each provider's `metadata.py` and converted to pydantic models via `build_metadata_model()` in `src/wetterdienst/model/metadata.py`. The key classes are `MetadataModel → ResolutionModel → DatasetModel → ParameterModel`.

### Provider Structure

Each provider lives under `src/wetterdienst/provider/<provider>/`. Standard layout:
```
provider/
  __init__.py          # exports the main Request class
  api.py               # concrete TimeseriesRequest subclass
  metadata.py          # MetadataModel dict + build_metadata_model() call
  values.py            # concrete TimeseriesValues subclass
  parser.py            # raw data parsing
  fileindex.py         # file listing/indexing from source
  download.py          # data fetching helpers
```

DWD has multiple networks: `observation`, `mosmix`, `dmo`, `road`, `radar`, `derived`.

### Metadata Enums

Shared enums live in `src/wetterdienst/metadata/`:
- `Parameter` — canonical cross-provider parameter names (snake_case)
- `Resolution` — time granularity (`MINUTE_1`, `HOURLY`, `DAILY`, etc.)
- `Period` — data periods (`HISTORICAL`, `RECENT`, `NOW`)
- `CacheExpiry` — preset cache durations used via fsspec

### Network / Caching

All HTTP requests go through `src/wetterdienst/util/network.py` which wraps fsspec with TTL caching and `stamina`-based retry logic. Cache is stored in the user cache directory (configurable via `WD_CACHE_DIR`).

### UI Layer

- **CLI** (`src/wetterdienst/ui/cli.py`): click/cloup-based CLI exposing `stations`, `values`, `history`, `interpolate`, `summarize`, `stripes`, `restapi`, and `about` commands.
- **REST API** (`src/wetterdienst/ui/restapi.py`): FastAPI app; endpoints mirror CLI commands. Starts via `wetterdienst restapi`.
- **Frontend** (`frontend/`): Nuxt 3 SPA (SSR disabled) that calls the REST API backend. Runtime config `NUXT_PUBLIC_API_BASE` sets the backend URL (default: `http://localhost:3000/api`).

### Export / IO

`ExportMixin` (`src/wetterdienst/io/export.py`) is mixed into result classes and supports exporting to files (CSV, JSON, Excel, Zarr), databases (SQLite, PostgreSQL, CrateDB, InfluxDB), and DuckDB SQL queries. The `[export]` optional dependency group enables most of these.

### Interpolation & Summary

`src/wetterdienst/core/interpolate.py` and `src/wetterdienst/core/summarize.py` implement spatial interpolation (requires `[interpolation]` extras: scipy, shapely, utm) and weighted summarization of station values for a target location.

## Key Conventions

- **Polars throughout**: data is always `pl.DataFrame`/`pl.LazyFrame`; avoid pandas in new code (it appears only in some export adapters).
- **Parameters are referenced** as `"resolution/dataset"` or `"resolution/dataset/parameter"` strings, or as typed `ParameterModel`/`DatasetModel` objects from the provider's metadata.
- **Provider metadata dicts** follow a strict schema — see any existing `provider/*/metadata.py` for the canonical structure before adding a new provider.
- **Test markers**: `remote` (needs internet), `slow`, `sql`, `explorer`, `cflake` (concurrency-flaky). Remote tests are not skipped by default locally; use `-m "not remote"` to skip them.
- **Ruff** is the linter/formatter; line length is 120. Run `uv run poe format` before committing.
