# GitHub Copilot Instructions for Wetterdienst

## Project Overview

Wetterdienst is a Python library that provides open weather data access for humans. It's a community-driven project that aims to make weather data retrieval feel like a warm summer breeze, providing unified access to multiple weather services and environmental agencies.

**Status**: Beta (Breaking changes expected until 1.0 release)

## Core Technologies & Architecture

### Data Processing Stack
- **Primary DataFrame Library**: [Polars](https://www.pola.rs/) (v1.15.0+) - Use polars for all data operations
- **Legacy Support**: pandas (v2.x) - Only used in some IO processes for backward compatibility
- **Package Management**: [uv](https://github.com/astral-sh/uv) for dependency management
- **Python Versions**: 3.10, 3.11, 3.12, 3.13, 3.14

### Key Dependencies
- **Data Validation**: pydantic (v2.7.3+), pydantic-extra-types, pydantic-settings
- **CLI Framework**: click (v8.x), cloup (v3.x)
- **HTTP/Networking**: fsspec[http], stamina (for retries)
- **Data Formats**: lxml, h5py (radar data)
- **Caching**: cachetools, shelved-cache, platformdirs
- **Timezone**: tzdata, tzfpy

### Optional Features (Extras)
- `bufr`: BUFR format support (pdbufr, pybufrkit)
- `cratedb`, `duckdb`, `mysql`, `postgresql`: Database export support
- `excel`: Excel export (xlsxwriter)
- `export`: Multiple export formats (pandas, sqlalchemy, xarray, zarr)
- `influxdb`: InfluxDB support
- `interpolation`: Station interpolation (scipy, shapely, utm)
- `matplotlib`: Plotting for radar examples
- `plotting`: Interactive plots (plotly, kaleido)
- `radar`: Radar data processing (h5py)
- `radarplus`: Advanced radar (wradlib, xradar)
- `restapi`: FastAPI-based REST API (fastapi, uvicorn)
- `sql`: SQL querying with DuckDB

## Code Style & Standards

### Linting & Formatting
- **Tool**: [Ruff](https://github.com/astral-sh/ruff) for both linting and formatting
- **Line Length**: 120 characters
- **Commands**:
  - Format code: `uv run poe format` or `uv run ruff format && uv run ruff check --fix`
  - Check formatting: `uv run poe lint` or `uv run ruff format --check && uv run ruff check`
- **Ruff Configuration**: Most rules enabled (`select = ["ALL"]`) with specific ignores for TD, FIX, PD, complexity rules
- **Auto-fix disabled for**: ERA (commented code), F401 (unused imports), F841 (unused variables), T20 (print statements), ERA001

### Code Organization
- **Module Structure**: Provider-based architecture under `wetterdienst/provider/`
- **Core Modules**: `api.py`, `boot.py`, `core/`, `exceptions.py`, `io/`, `metadata/`, `model/`, `settings.py`, `ui/`, `util/`
- **Per-File Ignores**:
  - `__init__.py`: Allow F401 (unused imports), D104 (missing docstring)
  - `tests/*`: Allow S101 (assert statements)
  - `benchmarks/*`, `examples/*`: Allow T20 (print statements), INP001 (implicit namespace package)

### Testing
- **Framework**: pytest with coverage
- **Parallel Testing**: `pytest -vvv --numprocesses=auto -m 'not (explorer or cflake)'`
- **Coverage Target**: Tests should maintain coverage (no strict minimum enforced)
- **Test Markers**:
  - `remote`: Tests accessing the internet
  - `slow`: Slow tests
  - `sql`: SQL-related tests
  - `explorer`: UI-related tests
  - `cflake`: Flaky tests under concurrency (run separately)
- **Commands**:
  - Run tests: `uv run poe test`
  - Parallel tests only: `uv run poe test:parallel`
  - Coverage: `uv run poe coverage`
- **Flaky Test Handling**: pytest-rerunfailures configured (reruns=0 by default, can be adjusted)

### Documentation
- **Tool**: Sphinx with MyST (Markdown support)
- **Theme**: sphinx-book-theme
- **Extensions**: sphinx-autodoc2, sphinx-copybutton, myst-nb for notebooks
- **Build**: `uv run poe docs` (runs `cd docs && make html`)
- **Location**: https://wetterdienst.readthedocs.io/

## Development Workflow

### Setup Environment
```bash
# Sync dependencies
uv sync

# Lock dependencies after changes
uv lock
```

### Task Runner (poethepoet)
Access tasks via `uv run poe <task>`:
- `format`: Format and fix linting issues
- `lint`: Check formatting and linting
- `test`: Run all tests (parallel + cflakes)
- `test:parallel`: Run tests in parallel
- `test:cflakes`: Run concurrency-sensitive tests
- `coverage`: Run tests with coverage reporting
- `docs`: Build documentation
- `creosote`: Check for unused dependencies
- `zizmor`: Security checks

### Git Workflow
- **Repository**: https://github.com/earthobservations/wetterdienst
- **CI/CD**: GitHub Actions (see `.github/workflows/`)
- **Branch Strategy**: Main branch with feature branches
- **Breaking Changes**: Expected until v1.0 - version pinning recommended

## Data Access Patterns

### Settings Context

```python
from src.wetterdienst import Settings

settings = Settings(
    ts_shape="long",  # tidy/long format (default)
    ts_humanize=True,  # humanize parameter names
    ts_convert_units=True  # convert to SI units
)
```

### Request Pattern

```python
from src.wetterdienst.provider.dwd import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "precipitation_height")],
    start_date="2002-08-11",  # UTC timezone if not specified
    end_date="2002-08-13",
    settings=settings
).filter_by_station_id(station_id=(5779,))

# Get stations metadata
stations = request.df  # Returns polars DataFrame

# Get values
values = request.values.all().df  # Returns polars DataFrame

# Convert to pandas if needed
values.to_pandas()
```

### Supported Providers
Check `wetterdienst/provider/` for available weather services:
- DWD (Deutscher Wetterdienst) - Germany
- ECCC (Environment and Climate Change Canada)
- EA (Environment Agency) - UK
- NOAA/NWS - USA
- Geosphere Austria
- IMGW - Poland
- Eaufrance Hubeau
- WSV - German waterways

## CLI Interface

**Command**: `wetterdienst` (entry point in `wetterdienst.ui.cli:cli`)

Example commands:
```bash
# List stations
wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all

# Get values
wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --station=1048,4411
```

## Important Notes for Contributors

### Data Philosophy
- Use **polars** for all new data operations (not pandas unless for IO compatibility)
- Default to UTC timezone when not specified
- Return data in "long" (tidy) format by default
- Humanize parameter names and convert to SI units by default

### Performance
- Cache data appropriately using `shelved-cache` for persistent caching and `cachetools` for in-memory caching
- Use parallel processing where beneficial
- Consider retry logic with `stamina` for network requests

### API Design
- Follow existing provider patterns when adding new data sources
- Maintain backwards compatibility where possible (until v1.0)
- Document breaking changes in CHANGELOG.md

### Code Review Expectations
- All code must pass `ruff` checks
- Tests should be added for new features
- Avoid commented-out code (ERA rule)
- Minimize complexity (respect Pylint complexity limits when reasonable)

### Community
- **Maintainers**: Benjamin Gutzmann (gutzemann@gmail.com), Andreas Motl (andreas.motl@panodata.org)
- **Response Time**: Expect response within a few days
- **Contribution Types**: Issues, PRs, dataset requests, bug reports all welcome
- **Code of Conduct**: See CODE_OF_CONDUCT.md

### Docker Support
- Public Docker images available at `ghcr.io/earthobservations/wetterdienst`
- Includes all optional dependencies
- Can be used for library or CLI access

### Special Considerations
- **Raspberry Pi/ARM**: May require additional system packages (gfortran, libopenblas, lxml)
- **Windows CI**: Uses `test-slow` task instead of parallel tests
- **Deprecation**: Explorer and Streamlit apps are deprecated; new web interface in development

## Key Links
- REST API: https://wetterdienst.eobs.org/
- Documentation: https://wetterdienst.readthedocs.io/
- Examples: https://github.com/earthobservations/wetterdienst/tree/main/examples
- Benchmarks: https://github.com/earthobservations/wetterdienst/tree/main/benchmarks
- Issues: https://github.com/earthobservations/wetterdienst/issues

## Citation
When using wetterdienst in research, please cite using Zenodo DOI: https://zenodo.org/badge/latestdoi/160953150
