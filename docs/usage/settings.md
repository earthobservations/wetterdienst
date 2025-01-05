# Settings

## Overview

Wetterdienst holds core settings in its ``Settings`` class. ``Settings`` have four layers from which to be sourced:

- Settings arguments e.g. Settings(ts_shape="long")
- environment variables e.g. `WD_TS_SHAPE="wide"`
- local .env file in the same folder (same as above)
- default arguments set by `wetterdienst`

The arguments are overruled in the above order meaning:

- Settings argument overrules environmental variable
- environment variable overrules .env file
- .env file overrules default argument

The following settings are available:

**General**

| name                 | description                                                           | default                            |
|----------------------|-----------------------------------------------------------------------|------------------------------------|
| cache_disable        | switch of caching                                                     | False                              |
| cache_dir            | set the directory where the cache is stored                           | platform specific / "wetterdienst" |
| fsspec_client_kwargs | pass arguments to fsspec, especially for querying data behind a proxy | {}                                 |

**Timeseries**

| name                                         | description                                                                                                                                                                                                                                                                                                                                              | default |
|----------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|
| ts_humanize                                  | rename parameters to more meaningful names                                                                                                                                                                                                                                                                                                               | True    |
| ts_shape                                     | reshape the returned data to a [long/tidy format](https://vita.had.co.nz/papers/tidy-data.pdf), one of "long", "wide", if two datasets are requested, parameter names are prefixed with the dataset name                                                                                                                                                 | "long"  |
| ts_convert_units                             | convert values to target units                                                                                                                                                                                                                                                                                                                           | True    |
| ts_unit_targets                              | dictionary of overwrite target units e.g. `{"temperature": "degree_fahrenheit", "fraction": "percent"}`                                                                                                                                                                                                                                                  | {}      |
| ts_skip_empty                                | skip empty stations, requires setting `ts_shape="long"`, empty stations are defined via `ts_skip_threshold` and `ts_skip_criteria`                                                                                                                                                                                                                       | True    |
| ts_skip_threshold                            | use with `skip_empty` to define when a station is empty, with 1.0 meaning no values per parameter should be missing and e.g. 0.9 meaning 10 per cent of values can be missing                                                                                                                                                                            | 0.95    |
| ts_skip_criteria                             | statistical criteria on which the percentage of actual values is calculated with options "min", "mean", "max", where "min" means the percentage of the lowest available parameter is taken, while "mean" takes the average percentage of all parameters and "max" does so for the parameter with the most percentage, requires setting `ts_shape="long"` | "min"   |
| ts_complete                                  | create a complete timeseries with filled null values, will be ignored if `ts_drop_nulls` is set to `True`, requires setting `ts_shape="long"`                                                                                                                                                                                                            | False   |
| ts_drop_nulls                                | drop all empty entries thus reducing the workload, requires setting `ts_shape="long"`                                                                                                                                                                                                                                                                    | True    |
| ts_interpolation_station_distance            | maximum distance to the farthest station which is used for interpolation, if the distance is exceeded, the station is skipped                                                                                                                                                                                                                            | 40.0    |
| ts_interpolation_use_nearby_station_until_km | distance to the nearest station which decides whether the data is used directly from this station or if data is being interpolated                                                                                                                                                                                                                       | 1       |

For more on units see the chapter [Units](units.md).

## Python

You can import and show Settings like

```python exec="on" source="above"
from wetterdienst import Settings

settings = Settings()
print(settings)
```

or modify them for your very own request like

```python exec="on" source="above"
from wetterdienst import Settings

settings = Settings(ts_shape="wide")
print(settings)
```

If your system is running behind a proxy e.g., like 
[here](https://github.com/earthobservations/wetterdienst/issues/524)
you may want to use the `trust_env` setting like

```python exec="on" source="above"
from wetterdienst import Settings

settings = Settings(fsspec_client_kwargs={"trust_env": True})
```

to allow requesting through a proxy.
