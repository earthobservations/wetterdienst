---
file_format: mystnb
kernelspec:
  name: python3
---

# Quickstart

This page takes you from a fresh install to your first weather time series in a few minutes, from Python, from the
command line, from the REST API, from an assistant and from the app. New to the words? Read [Concepts](concepts.md)
first, it is one page. For the full feature set, continue with the [Python API](python-api.md) chapter.

## Installation

Wetterdienst is available on PyPI and requires Python 3.11 or newer:

```bash
pip install wetterdienst
```

The base install keeps dependencies light. What goes beyond the library and the command line is behind an extra,
installed in brackets, in quotes so that the shell leaves them alone:

```bash
pip install "wetterdienst[interpolation,export]"
```

| Extra | What it adds |
| --- | --- |
| `restapi` | the REST API, `wetterdienst restapi` |
| `mcp` | the [MCP server](mcp.md), served by the REST API (brings `restapi`) |
| `interpolation` | `interpolate` and `summarize` for a point, see [Interpolation & Summary](interpolation.md) |
| `sql` | SQL filters on a result (`filtered_by_sql`, `--sql`), by DuckDB |
| `export` | files (Zarr, NetCDF, Excel) and SQL databases as export targets, see [Export](export.md) |
| `duckdb`, `postgresql`, `mysql`, `cratedb`, `influxdb` | the one database of that name as an export target, without the rest of `export` |
| `excel` | Excel (`.xlsx`) as an export target |
| `plotting` | charts and images of a result (`to_plot`, `to_image`) and the climate stripes images |
| `knmi` | the KNMI observations, which come as NetCDF |
| `radar` | the DWD radar products that are HDF5 or NetCDF |
| `radarplus` | the packages that radar data is worked with (wradlib, xradar), as in the radar examples |
| `bufr`, `eccodes` | decoding BUFR, which DWD road weather is (and the radar products of DWD's earlier layout, through `read_radar_bufr`; `bufr` brings the reader, `eccodes` only the library); on Linux see the [crash at exit](../known_issues.md#crash-at-exit-with-eccodes-and-pyproj-on-linux) for code that imports ecCodes itself |
| `pdf` | reading the field descriptions of DWD's PDF documents (`describe_fields`) |

Check the installation with `wetterdienst --help`. The [Docker image](docker.md) ships with most of them. A request that
needs an extra that is not installed fails with a `MissingDependencyError` that names it.

## Your first request

A request is defined by the data you want (`parameters`) and, optionally, a time range.
Here we ask the German Weather Service (DWD) for the daily climate summary and then pick a
single station by its id — `1048`, Dresden-Klotzsche:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
    periods="recent",
)
stations = request.filter_by_station_id(station_id="1048")
stations.df
```

`stations.df` holds the station metadata. To fetch the actual measurements, ask the
associated values result:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
values = stations.values().all()
values.df
```

That's it — `values.df` is a [polars](https://pola.rs/) DataFrame you can filter, plot or
export.

## The same request on the command line

Everything the Python API can do is also available via the CLI:

```bash
# List the station's metadata.
wetterdienst stations --provider dwd --network observation \
  --parameters daily/climate_summary --periods recent --stations 1048

# Fetch the values.
wetterdienst values --provider dwd --network observation \
  --parameters daily/climate_summary/temperature_air_mean_2m --periods recent --stations 1048
```

## The same request from the REST API

Start the API (it needs the `restapi` extra) and ask it, here with [httpie](https://github.com/httpie/cli) (`curl`
works as well, with the query in the URL):

```bash
wetterdienst restapi
```

```bash
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_mean_2m periods==recent stations==1048
```

The answer is JSON with the values and a `metadata` block that says where the data comes from, under which licence and
with which credit line. The interactive reference of every endpoint is at <http://localhost:7890/docs>. A hosted
instance is at [wetterdienst.eobs.org](https://wetterdienst.eobs.org). See [REST API](restapi.md).

## From an assistant or the app

An assistant that speaks the [Model Context Protocol](mcp.md) reads the same data as tools: add
`https://wetterdienst.eobs.org/mcp/v1` as a server and ask in words how warm it was somewhere. No account is needed. And
the [web app](app.md) at [wetterdienst.eobs.org](https://wetterdienst.eobs.org) is the same data on a map, with
forecasts and climate stripes, for anyone who would rather click.

## If something fails

Most failures say what to change; [Troubleshooting](troubleshooting.md) lists what each means: a missing extra, a
provider that needs a key, a provider that is down, an answer that is empty.

## Where to go next

- **Python**: [Concepts](concepts.md), then the [Python API](python-api.md) (requests, stations, values, formats),
  [Python Examples](python-examples.md) per provider, [Units](units.md), [Settings and options](settings.md),
  [Interpolation & Summary](interpolation.md) for a point between stations, [Export](export.md) to files and databases.
- **Command line**: the [command line interface](cli.md), [Scheduling](scheduling.md) a recurring acquisition.
- **REST and MCP**: the [REST API](restapi.md), the [MCP server](mcp.md), [Docker](docker.md).
- **App**: the [web app](app.md), including how to run your own.
- **The data**: [Data](../data/index.md) for every provider and parameter, the [parameter glossary](../data/parameters.md)
  and what the [quality flags](../data/quality-flags.md) mean. DWD [weather alerts](../data/provider/dwd/alerts/index.md),
  [Climate Stripes](stripes.md), [Station history](station_history.md).
