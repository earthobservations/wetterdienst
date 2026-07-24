---
file_format: mystnb
kernelspec:
  name: python3
---

# Quickstart

This page takes you from a fresh install to your first weather time series in a few minutes.
For the full feature set, continue with the [Python API](python-api.md) chapter.

## Installation

Wetterdienst is available on PyPI and requires Python 3.10 or newer:

```bash
pip install wetterdienst
```

The base install keeps dependencies light. Optional features live behind
[extras](docker.md) — for example the interpolation feature or exporting to databases:

```bash
pip install "wetterdienst[interpolation,export]"
```

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
values = stations.values.all()
values.df
```

That's it — `values.df` is a [polars](https://pola.rs/) DataFrame you can filter, plot or
export.

## The same request on the command line

Everything the Python API can do is also available via the CLI:

```bash
# List the station's metadata.
wetterdienst stations --provider dwd --network observation \
  --parameters daily/climate_summary --periods recent --station 1048

# Fetch the values.
wetterdienst values --provider dwd --network observation \
  --parameters daily/climate_summary/temperature_air_mean_2m --periods recent --station 1048
```

## Where to go next

- [Python API](python-api.md) — the full request/stations/values workflow, filtering,
  formatting, SQL and export.
- [Python Examples](python-examples.md) — ready-to-run snippets per provider and network.
- [Data / Overview](../data/overview.md) — every supported provider and what it offers.
- [Interpolation & Summary](interpolation.md) — derive a series for an arbitrary location.
- [Climate Stripes](stripes.md) — generate warming-stripes visualizations.
- [Settings](settings.md) — units, caching, proxies and interpolation knobs.
