---
file_format: mystnb
kernelspec:
  name: python3
---

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
| cache_disable        | switch off caching                                                    | False                              |
| cache_dir            | set the directory where the cache is stored                           | platform specific / "wetterdienst" |
| fsspec_client_kwargs | pass arguments to fsspec, especially for querying data behind a proxy | {}                                 |
| use_certifi          | use certifi certificate bundle instead of system certificates         | False                              |
| read_bufr            | parse DWD radar BUFR products into `RadarResult.df` (needs `eccodes` + `bufr` extras) | False               |

**Timeseries**

| name                               | description                                                                                                                                                                                                                                                                                                                                              | default |
|------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|
| ts_humanize                        | rename parameters to more meaningful names                                                                                                                                                                                                                                                                                                               | True    |
| ts_shape                           | reshape the returned data to a [long/tidy format](https://vita.had.co.nz/papers/tidy-data.pdf), one of "long", "wide"; a wide row is one timestamp of one resolution, so resolutions get their own rows while datasets recorded at the same resolution share one, with their parameter names prefixed by the dataset name and the `dataset` column of that shared row left null                                                                                                                                                 | "long"  |
| ts_convert_units                   | convert values to target units                                                                                                                                                                                                                                                                                                                           | True    |
| ts_unit_targets                    | dictionary of overwrite target units e.g. `{"temperature": "degree_fahrenheit", "fraction": "percent"}`                                                                                                                                                                                                                                                  | {}      |
| ts_skip_empty                      | skip a station whose requested parameters are covered too sparsely to be worth returning, where too sparsely is defined via `ts_skip_threshold` and `ts_skip_criteria`. The coverage of a parameter is the share of the readings the requested window can hold at its resolution that the station actually delivered; a request naming no window is measured against the span of the station's own series instead | False   |
| ts_skip_threshold                  | use with `skip_empty` to define when a station is empty, with 1.0 meaning no values per parameter should be missing and e.g. 0.9 meaning 10 per cent of values can be missing                                                                                                                                                                            | 0.95    |
| ts_skip_criteria                   | statistical criteria on which the percentage of actual values is calculated with options "min", "mean", "max", where "min" means the percentage of the lowest available parameter is taken, while "mean" takes the average percentage of all parameters and "max" does so for the parameter with the most percentage                                     | "min"   |
| ts_drop_nulls                      | drop all empty entries thus reducing the workload, requires setting `ts_shape="long"`                                                                                                                                                                                                                                                                    | True    |
| ts_geo_station_distance_homogeneous   | maximum distance (in km) to a station used for interpolation of a homogeneous parameter, one that varies slowly across a region such as air temperature or air pressure                                                                                                                                                                              | 40.0    |
| ts_geo_station_distance_heterogeneous | the same for a heterogeneous parameter, one that decorrelates within a few tens of kilometres such as precipitation, fresh snow or visibility                                                                                                                                                                                                        | 20.0    |
| ts_geo_station_distance            | dictionary of per-parameter overrides of the two distances above, e.g. `{"precipitation_height": 25.0}`, keyed by canonical parameter name. Used exactly as given, at every resolution, while the two distances above are the radius at hourly resolution                                                                                                                                                              | {}      |
| ts_geo_station_distance_resolution_factors | dictionary of factors the heterogeneous distance is multiplied by, keyed by resolution, e.g. `{"10_minutes": 1.0}` to search the full hourly radius at ten minutes. Resolutions left out keep their default factor: 0.75 for the minute resolutions, 1.0 hourly, 1.5 for `6_hour` and `subdaily`, 2.0 from daily upwards, where terrain rather than correlation is what bounds the search                                                          | {}      |
| ts_geo_use_nearby_station_distance | distance to the nearest station which decides whether the data is used directly from this station or if data is being interpolated                                                                                                                                                                                                                       | 1       |
| ts_geo_min_gain_of_value_pairs     | minimum gain of value pairs which decides whether to stop looking for further stations                                                                                                                                                                                                                                                                   | 0.1     |
| ts_geo_num_additional_stations     | number of additional stations to take into account besides gain of value pairs                                                                                                                                                                                                                                                                           | 3       |

For more on units see the chapter [Units](units.md), and for the two search radii and their
per-parameter overrides the chapter [Interpolation & Summary](interpolation.md#the-search-radius).

## Python

You can import and show Settings like

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Settings

settings = Settings()
settings
```

or modify them for your very own request like

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Settings

settings = Settings(ts_shape="wide")
settings
```

If your system is running behind a proxy e.g., like
[here](https://github.com/earthobservations/wetterdienst/issues/524)
you may want to use the `trust_env` setting like

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Settings

settings = Settings(fsspec_client_kwargs={"trust_env": True})
settings
```

to allow requesting through a proxy.

If you're experiencing SSL certificate verification issues, especially in corporate environments or
when system certificates are outdated, you can enable the certifi certificate bundle:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Settings

settings = Settings(use_certifi=True)
settings
```

This uses the [certifi](https://pypi.org/project/certifi/) package which provides Mozilla's
carefully curated collection of Root Certificates for validating the trustworthiness of SSL
certificates while verifying the identity of TLS hosts.