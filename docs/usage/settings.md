---
file_format: mystnb
kernelspec:
  name: python3
---

# Settings and options

## Overview

Wetterdienst keeps two kinds of configuration apart:

- **Settings** (the `Settings` class) belong to the host: the cache, the network client, the
  credentials. They are the same for every request a process makes and are read by the providers.
- **Options** (the `Options` class) belong to a request: how its values come back (shape, units,
  names, skipping of empty stations) and how far a station may be to be interpolated from. A
  request takes them as `options=`, so two requests of one process can differ in them.

```python
from wetterdienst import Options, Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "kl")],
    settings=Settings(cache_disable=True),  # the host
    options=Options(shape="wide"),  # this request
)
```

Both read the environment, and `.env`, the same way. The variables of the options keep their
`WD_TS_` prefix, so `WD_TS_SHAPE="wide"` sets the `shape` option as before.

```{note}
`Settings(ts_shape="long")` and the other `ts_*` settings, reading or assigning `settings.ts_shape`,
and a `settings={"ts_shape": "long"}` dict are the old way to set what are options now. `Settings`
no longer has them as fields. They are still taken, with a `DeprecationWarning`, when a request is
given no `options=`, but will be removed: pass `options=Options(shape="long")` instead. Giving
`options=` beside such `ts_*` settings that differ from the options of the environment raises a
`ValueError`. A mapping given as a `ts_*` setting is merged with the environment's, key by key, as
`Options(...)` does and `options={...}` does not. `Settings.model_construct(ts_...)` is not covered.
The `WD_TS_*` variables stay and are read by `Options` alone.
```

## Settings

`Settings` have four layers from which to be sourced:

- Settings arguments e.g. Settings(cache_disable=True)
- environment variables e.g. `WD_CACHE_DISABLE="true"`
- local .env file in the same folder (same as above)
- default arguments set by `wetterdienst`

The arguments are overruled in the above order meaning:

- Settings argument overrules environmental variable
- environment variable overrules .env file
- .env file overrules default argument

As from the environment, only the `WD_` variables that name a setting are read from `.env`. Its
other keys, such as another program's, or a `WD_` key that names no setting, such as the misspelt
`WD_CACHE_DIABLE`, are ignored. A key within a setting, such as `WD_AUTH__KNMI`, is read as part of
that setting. A keyword to `Settings(...)` that names no setting is refused, the removed `ts_*` settings apart.

The following settings are available:

| name                 | description                                                           | default                            |
|----------------------|-----------------------------------------------------------------------|------------------------------------|
| cache_disable        | switch off caching                                                    | False                              |
| cache_dir            | set the directory where the cache is stored; where no home directory resolves, the default is a temporary directory per process, removed at exit | platform specific / "wetterdienst" |
| fsspec_client_kwargs | pass arguments to fsspec, especially for querying data behind a proxy | User-Agent header, timeout 30      |
| use_certifi          | use certifi certificate bundle instead of system certificates         | False                              |
| read_bufr            | parse DWD radar BUFR products into `RadarResult.df` (needs the `bufr` extra) | False               |
| restapi_sql          | let REST API and MCP clients filter with `sql` / `sql_values` (refused with a 403 otherwise); the clause runs in DuckDB on the server, see [REST API](restapi.md#sql-filters) | False |

### Python

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

settings = Settings(cache_disable=True)
settings
```

and hand them to a request with `settings=`, next to the `options=` described [below](#options).

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

A dict given as `fsspec_client_kwargs`, as an argument or as `WD_FSSPEC_CLIENT_KWARGS`, is merged
into the defaults rather than replacing them: the example above keeps the User-Agent header and the
timeout of 30. A key you give wins over the default of the same name, and `headers`, given as a
dict, is merged the same way, so a header of your own is sent alongside the User-Agent, and a
`User-Agent` of your own (in any capitalisation) replaces it. Give `"timeout": None` (`null` in
the environment variable) to use aiohttp's own default instead: five minutes for the whole request,
30 seconds to connect. A dict assigned to `fsspec_client_kwargs` on a `Settings` object that
already exists is merged the same way.

A number given as `timeout` in `fsspec_client_kwargs` (30 by default) is how many seconds a request
may wait before it fails: for a connection (including a free one from the pool), for the first byte
of the answer, or between two bytes of it. It does not limit the request as a whole, so a download
that keeps arriving is not cut off, however long it takes. Eaufrance Hub'Eau ignores whatever
`timeout` is given and uses 120 seconds, as its service can take longer than 30 seconds to answer.

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

## Options

`Options` have the same four layers, and the arguments overrule the rest in the same order:

- Options arguments e.g. `Options(shape="long")`, or a dict of them, `options={"shape": "long"}`
- environment variables e.g. `WD_TS_SHAPE="wide"`
- local .env file in the same folder (same as above)
- default arguments set by `wetterdienst`

A dict names only the options it changes and leaves the rest to the environment and the defaults.
What it names replaces the environment's value for that option as a whole: a `unit_targets` dict
is not merged with a `WD_TS_UNIT_TARGETS` the host sets. `Options(...)` itself, as `Settings(...)`
does, merges a mapping it is given with the environment's key by key; give a dict, or use
`options.replace(...)`, to replace it. A key within an option, such as
`WD_TS_UNIT_TARGETS__TEMPERATURE`, is read as part of that option, and a keyword to `Options(...)`
that names no option is refused. As for the settings, only the `WD_TS_` variables that name an
option are read from `.env`.

An `Options` is frozen. `options.replace(shape="wide")` gives a changed copy, validated as a new
instance is. A request takes its options when it is built, so build it with the ones you want.

The environment variable of an option is its name in capitals behind `WD_TS_`, e.g.
`WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS`. The following options are available:

| name | description | default |
|------|-------------|---------|
| humanize | rename parameters to more meaningful names | True |
| shape | reshape the returned data to a [long/tidy format](https://vita.had.co.nz/papers/tidy-data.pdf), one of "long", "wide"; a wide row is one timestamp of one resolution, so resolutions get their own rows while datasets recorded at the same resolution share one, with their parameter names prefixed by the dataset name and the `dataset` column of that shared row left null | "long" |
| convert_units | convert values to target units | True |
| unit_targets | dictionary of overwrite target units e.g. `{"temperature": "degree_fahrenheit", "fraction": "percent"}` | {} |
| skip_empty | skip a station whose requested parameters are covered too sparsely to be worth returning, where too sparsely is defined via `skip_threshold` and `skip_criteria`. The coverage of a parameter is the share of the readings the requested window can hold at its resolution that the station actually delivered; a request naming no window is measured against the span of the station's own series instead | False |
| skip_threshold | use with `skip_empty` to define when a station is empty, with 1.0 meaning no values per parameter should be missing and e.g. 0.9 meaning 10 per cent of values can be missing; above 0 and at most 1 | 0.95 |
| skip_criteria | statistical criteria on which the percentage of actual values is calculated with options "min", "mean", "max", where "min" means the percentage of the lowest available parameter is taken, while "mean" takes the average percentage of all parameters and "max" does so for the parameter with the most percentage | "min" |
| drop_nulls | drop all empty entries thus reducing the workload, requires `shape="long"`: the wide shape keeps them but leaves this option as given, and `options.drop_nulls_effective` tells whether they are dropped | True |
| geo_station_distance_homogeneous | maximum distance (in km) to a station used for interpolation of a homogeneous parameter, one that varies slowly across a region such as air temperature or air pressure | 40.0 |
| geo_station_distance_heterogeneous | the same for a heterogeneous parameter, one that decorrelates within a few tens of kilometres such as precipitation, fresh snow or visibility | 20.0 |
| geo_station_distance | dictionary of per-parameter overrides of the two distances above, e.g. `{"precipitation_amount": 25.0}`, keyed by canonical parameter name. Used exactly as given, at every resolution, while the two distances above are the radius at hourly resolution | {} |
| geo_station_distance_resolution_factors | dictionary of factors the heterogeneous distance is multiplied by, keyed by resolution, e.g. `{"10_minutes": 1.0}` to search the full hourly radius at ten minutes. Resolutions left out keep their default factor: 0.75 for the minute resolutions, 1.0 hourly, 1.5 for `6_hour` and `subdaily`, 2.0 from daily upwards, where terrain rather than correlation is what bounds the search | {} |
| geo_use_nearby_station_distance | distance to the nearest station which decides whether the data is used directly from this station or if data is being interpolated | 1 |
| geo_min_gain_of_value_pairs | minimum gain of value pairs which decides whether to stop looking for further stations | 0.1 |
| geo_num_additional_stations | number of additional stations to take into account besides gain of value pairs | 3 |

For more on units see the chapter [Units](units.md), and for the two search radii and their
per-parameter overrides the chapter [Interpolation & Summary](interpolation.md#the-search-radius).

### Options in Python

You can import and show the options like

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Options

options = Options()
options
```

or change them for your very own request like

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Options

options = Options(shape="wide")
options.replace(humanize=False)
```

`options.tidy` tells whether the shape is long, and `options.drop_nulls_effective` whether the empty
entries are dropped, which they are in the long shape alone.
