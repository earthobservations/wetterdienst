---
file_format: mystnb
kernelspec:
  name: python3
---

# Python API

## Introduction

The API offers access to different data products. They are outlined in more detail within the
[data](../data/overview.md) chapter, and the words (provider, network, dataset, resolution, period) are in
[Concepts](concepts.md).
Please also check out complete examples about how to use the API in the
[examples](https://github.com/earthobservations/wetterdienst/tree/main/examples) folder. In order to explore all
features interactively, you might want to try the [cli](cli.md). For managing general settings and the options of a
request, please refer to the [settings](settings.md) chapter.

## Available APIs

The available APIs can be accessed by the top-level API Wetterdienst. This API also
allows the user to discover the available APIs of each service included:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Wetterdienst

coverage = Wetterdienst.discover()
coverage
```

Each network says what it is: `name_short`, `country`, `url` and `kind`, where `observation`, `forecast` and
`derived` are the timeseries networks, which have stations and values, and `radar` and `alerts`
(`dwd/radar`, `dwd/alerts`) are standalone, with request classes and results of their own. Nothing is
downloaded, so whether a provider accepts the credentials you have is not part of it:
`Wetterdienst.is_valid(Wetterdienst.resolve("aemet", "observation"))` asks for one network. The fields are
described with the [REST API](restapi.md#coverage), which lists the same.

To load the request class of a timeseries network pass the provider and the network of data to
`Wetterdienst.resolve`:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Wetterdienst

Wetterdienst.resolve(provider="dwd", network="observation")
```

`resolve` is for the networks that have stations and values. The two that have not, `dwd/radar` and
`dwd/alerts` (`Wetterdienst.standalone`), take other arguments and give other results, so they have an entry
point of their own, `Wetterdienst.resolve_standalone`, and `resolve` refuses them with an
`ApiNotFoundError` that says so. Both are typed: `resolve` gives a `type[TimeseriesRequest]`, and
`resolve_standalone("dwd", "radar")` the `DwdRadarValues` class. The classes can also be imported, which is
what the examples do.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Wetterdienst

Wetterdienst.resolve_standalone(provider="dwd", network="radar")
```

`Wetterdienst(provider, network)`, which returned the class, was removed in 0.173.0, earlier than announced for
1.0.0: `Wetterdienst` constructs nothing, and the call raises a `TypeError` that names `resolve` and
`resolve_standalone`.

## Request arguments

A request is typically defined by three arguments:

- ``parameters``
- ``start``
- ``end``

Parameters can be requested in different ways e.g.

- using a tuple of resolution and dataset

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(
    parameters=("daily", "climate_summary")  # will resolve to all parameters of kl
)
```

- using a tuple of resolution, dataset, parameter

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(
    parameters=("daily", "climate_summary", "precipitation_amount")
)
```

- the same with the original names

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(
    parameters=("daily", "kl", "rsk")
)
```

- using the metadata model

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationMetadata
  
DwdObservationRequest(
    parameters=DwdObservationMetadata.daily.kl  # will resolve to all parameters of kl
)
```

- using a list of tuples

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(
    parameters=[("daily", "climate_summary"), ("daily", "precipitation_more")]
)
```

- using a list of metadata

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationMetadata

DwdObservationRequest(
    parameters=[DwdObservationMetadata.daily.kl, DwdObservationMetadata.daily.more_precip]
)
```

- using the resolution as its ``Resolution`` member in a tuple: the member is read as its value, so
  ``(Resolution.DAILY, "kl")`` is ``("daily", "kl")`` and ``Resolution.MINUTE_10`` is ``"10_minutes"``

```python
from wetterdienst import Resolution
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(parameters=(Resolution.DAILY, "kl"))
```

A parameter the provider does not have, or one that is not shaped like a parameter, is an error:
``InvalidParameterError`` names every such entry, with the close match where there is one and the
names that would have matched, and no request is made. A call used to log a warning and go on with
the parameters that did resolve, which left no trace in the result of what was dropped. To get that
back, pass ``on_unknown="warn"``: the unknown ones are logged, and the request is made with the
rest. If nothing resolves, that is ``NoParametersFoundError``; without ``on_unknown`` the same request
is the ``InvalidParameterError``. Catch ``RequestError`` to cover both.

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

# raises InvalidParameterError: daily/klx not found in DwdObservationMetadata: 'klx'. Did you mean 'kl'? ...
DwdObservationRequest(parameters=["daily/kl/temperature_air_mean_2m", "daily/klx"])

# warns about daily/klx and requests temperature_air_mean_2m
DwdObservationRequest(
    parameters=["daily/kl/temperature_air_mean_2m", "daily/klx"],
    on_unknown="warn",
)
```

``start`` and ``end`` are an ISO 8601 string, a ``date`` or a ``datetime``; anything else, a year as
an integer such as ``start=2020`` among it, is a ``TypeError``. A bound that names a span and nothing
finer is the whole span, as the ``timestamp`` of the REST API, the command line and MCP reads it: a
``datetime.date`` or a string such as ``"2026-01-31"`` is the day, ``"2026-01"`` the month and ``"2026"``
the year. ``start`` is the first instant of the span and ``end`` its last (23:59:59.999999 UTC), so
``end="2026-01-31"`` includes all 24 readings of the 31st of hourly data and not midnight alone, and
``end="2026-01"`` runs to the end of January. A ``datetime`` and a string with a time
(``"2026-01-31T00:00"``) are that instant and no more, so ``end=datetime(2026, 1, 31)`` ends at
midnight. A bound given alone is the whole window: ``end`` without ``start`` is the same window as
``start`` without ``end``, the span of a date, a month or a year and the single instant of an instant, so
``end="2020-01-05"`` asks for that day, not for everything up to it. Pass both for a range. The
command line reads ``--end`` alone the same way. A string that is none of these, an interval
``"2020-05/2020-07"`` among it (pass the two bounds), is an ``InvalidTimeIntervalError`` (a
``ValueError``) that lists what is accepted.

Every request takes ``periods``, the release the data is read from. Valid periods are
``historical``, ``recent``, ``now`` and ``future``, and which of them a dataset is published under
is part of its metadata. A dataset published under a single period has nothing to choose between,
so asking for another one is an error naming the periods it does have, rather than a request that
quietly reads all of them. ``periods`` can be given as a list or a single value.
The value can be a string, the enumeration value or the enumeration name e.g.

- by using the exact enumeration e.g.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.metadata.period import Period

Period.HISTORICAL
```

- by using the enumeration name or value as string e.g.

```python
"historical" or "HISTORICAL"
```

An unknown one is an ``InvalidEnumerationError`` that lists the valid values: ``foo could not be
parsed from Period. Valid values: historical, recent, now, future``.

The periods argument typically can be used as replacement for the start and end
arguments. In case both arguments are given they are used as a filter for the data. Left out, the
periods are derived from ``start``/``end`` where the provider publishes on a release
schedule that says which period holds which years -- DWD observation and DWD phenology do -- and
are otherwise every period the requested datasets publish.

Regarding the definition of requested parameters:

## Data

In case of the DWD, requests can be defined by either of period or
``start`` and ``end``. Use ``DwdObservationRequest.discover()``
to discover available parameters based on the given filter arguments. Names match in any case. A resolution or dataset the
network does not have is a ``MetadataNotFoundError`` listing the ones it has, not an empty answer;
a dataset is looked for in the resolutions asked for, so ``resolutions="daily", datasets="dew_point"``
refuses a dataset that exists only at ``hourly``. ``Wetterdienst.get_network_names("foo")`` raises the
``ApiNotFoundError`` that ``Wetterdienst.resolve("foo", "bar")`` raises for a provider that does not exist.

### Stations

#### all stations

Get station information for a given *dataset/parameter* and
*period*.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
stations = request.all()
df = stations.df
df
```

The function returns a Polars DataFrame with information about the available stations.

#### filter by station id

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
stations = request.filter_by_station_id(station_id=("01048", ))
df = stations.df
df
```

A station id the request has no station for -- one that does not exist, or has no data for the
requested parameters and periods -- is left out of the result with a warning naming it (log level
`WARNING`): the stations that do exist are returned, and when none does the result is empty. The command
line and the REST API do the same for a list of `--stations` ids.

The stations come back in the order of the catalogue, not in the order the ids are given
(`("00003", "00001")` is `00001`, then `00003`): sort the frame for another order.

#### filter by name

Station name filtering uses fuzzy matching (case-insensitive, via rapidfuzz's `WRatio`
scorer) so partial names, minor typos, and word-order variations are handled
automatically. In particular a bare place name resolves to its stations, e.g.
`name="Kiel"` matches `Kiel-Holtenau` and `Kiel-Kronshagen`.

Diacritics do not matter: the name and the station names are folded before they are scored, so
`"Köln"`, `"Koln"` and `"koeln"` all find `Köln`, and `"Dusseldorf"`, `"Düsseldorf"` and
`"duesseldorf"` find the same stations. A name is folded two ways and the better score counts: without
its accent (`ä ö ü é ñ ç š č` become the plain letter, `ß` is `ss`, `ø` is `o`, `ł` is `l`) and with
the umlaut and the Nordic letters spelled out (`ä ö ü` become `ae oe ue`, `å` is `aa`, `ø` is `oe`).

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
stations = request.filter_by_name(name="Dresden-Klotzsche")
df = stations.df
df
```

The `threshold` parameter (0–1, default **0.8**) controls how strictly the name must
match.  Lower values accept more typos; higher values require a closer match.  The
`rank` parameter limits how many stations are returned (default 1, the best match). The `stations` listing
of the command line and the REST API offers the best five instead: pass `rank=5` for the same list.
A station is one match however many datasets (rows) it has, and two stations that share a name are two.
The rows come back best match first, equal scores in the order of their `station_id`.

`filter_by_name` matches the name among the stations that have a record in the `start` and `end` of the
request, as the command line, the REST API and MCP do with a `timestamp`: a station that closed before
the window, or began after it, is not the best match for a name while one of that name has the readings. A
station is left out when it started after the window, or ended before it by more than the buffer; a
station whose start or end is not published is kept. A request without a window matches among all of
them. The window is applied to a `df_all` you pass as well, so that the result does not depend on how
you got the stations. The other filters (`filter_by_station_id`, `filter_by_rank`, `filter_by_distance`,
`filter_by_bbox`, `filter_by_sql`) select among the whole list, whatever the window.

The buffer is there because the end a source publishes lags a station that is still reporting (DWD's
daily index ends yesterday, its annual one the year before last). By default a station is kept until its
end is two days before the window, 62 days for monthly and 732 days for annual. The start is compared
exactly: an index states the first day with a reading (the DWD stations that began last had their first
reading on the start the index gives, at daily, hourly and monthly resolution), so a station that begins
after the window has nothing in it and no buffer is taken on that side. The option `station_window_end_buffer`
of the [options](settings.md#options) sets the buffer, in days and the same for every resolution: `0`
compares the end exactly, `7` keeps a station that ended up to a week before the window, and left out
(`None`, the default) it is the buffer by resolution. The command line (`--station-window-end-buffer`), the
REST API and MCP (`station_window_end_buffer`) take it for `stations` and for `values` with a `name`, and
`WD_TS_STATION_WINDOW_END_BUFFER` sets it for a host. One rule serves Python and the three of them
(`limit_to_window`), so the same name and window give the same stations.

```python
request = DwdObservationRequest(
    parameters=[("monthly", "climate_summary")],
    start="2026-10-16",
    end="2026-10-16",
    options={"station_window_end_buffer": 0},  # a station is kept only if it has not ended before the window
)
stations = request.filter_by_name(name="Dresden-Klotzsche")
```

Because `WRatio` is a partial matcher, a query that is a common sub-token matches many
stations (e.g. `name="Bad"` matches every "…, Bad" station). For an exact match you have two
options: set `threshold=1.0`, which keeps only matches scoring 100 (so `name="Kiel"` returns
nothing while `name="Aach"` returns just `Aach`); or, for strict string equality, use
`filter_by_sql`, e.g. `filter_by_sql("name = 'Aach'")`.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
# case-insensitive, typo-tolerant, returns up to 3 matches
stations = request.filter_by_name(name="dresden", rank=3, threshold=0.8)
df = stations.df
df
```

#### filter by distance

Distance in kilometers (default)

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

hamburg = (53.551086, 9.993682)
request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
stations = request.filter_by_distance(latlon=hamburg, distance=30, unit="km")
df = stations.df
df
```

Distance in miles

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

hamburg = (53.551086, 9.993682)
request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
stations = request.filter_by_distance(latlon=hamburg, distance=30, unit="mi")
df = stations.df
df
```

#### filter by rank

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

hamburg = (53.551086, 9.993682)
request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
stations = request.filter_by_rank(latlon=hamburg, rank=5)
df = stations.df
df
```

```{note}
Unlike `filter_by_distance`, `filter_by_rank` returns **all** stations sorted by
distance in `stations.df`, not just `rank` rows. The `rank` limit is applied lazily
during value collection: Wetterdienst walks the distance-sorted stations and stops
once `rank` stations *with data* have been consumed. To see the `rank` closest
stations that actually returned data, use `stations.values().all().df_stations` rather
than `stations.df`. Enable the `skip_empty` option to walk past a station that returned data
but too little of it, as `skip_threshold` and `skip_criteria` define.
```

#### filter by bbox

```{code-cell}
---
mystnb:
  number_source_lines: true
---
import datetime as dt
from wetterdienst.provider.dwd.observation import DwdObservationRequest

bbox = (8.9, 50.0, 8.91, 50.01)
request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start=dt.datetime(2020, 1, 1),
    end=dt.datetime(2020, 1, 20)
)
stations = request.filter_by_bbox(*bbox)
df = stations.df
df
```

#### Station columns of a provider

The columns of `STATIONS_SCHEMA` are the same on every provider, but not always filled: `region` is the
sub-national unit the source names (a state, province, county, canton or département), whatever it is called
there, and null where the source names none. Behind them, a provider adds the
columns of its own that its station list has, null for a station the source gives none:

| Provider and network | Column | What it holds |
| --- | --- | --- |
| `dmi/observation` | `country` | DMI's three-letter code of the country the station is in: `DNK`, `GRL` or `FRO` |
| `dwd/mosmix`, `dwd/dmo`, `dwd/poi` | `icao_id` | the ICAO location indicator of the station, where it has one |
| `dwd/road` | `station_group`, `road_name`, `road_sector`, `road_type`, `road_surface_type`, `road_surroundings_type` | the road a station is on and its surroundings, as DWD's list gives them |
| `eaufrance/hubeau` | `gauge_zero`, `gauge_zero_datum` | the altitude of the gauge's zero and the reference system it is given in |
| `geosphere/observation` | `wmo_id` | the WMO station number, five digits |
| `imgw/meteorology` | `river` | the river catchment the station is listed under, with its hydrographic code (`Odra (1)`) |
| `knmi/observation` | `wigos_id` | the WIGOS station identifier (`0-20000-0-06260`), of which `station_id` is the WMO number at the end |
| `noaa/ghcn` | `wmo_id` | the WMO station number, five digits, null for a station without one |
| `wsv/pegel` | `river`, `river_kilometer` | the river the gauge is on, as Pegelonline publishes it (`ELBE`), and its position along it in kilometres |
| `wsv/pegel` | `gauge_zero`, `gauge_zero_datum` | the altitude of the gauge's zero and the datum it is given in |
| `wsv/pegel` | `m_i`, `m_ii`, `m_iii`, `mnw`, `mw`, `mhw`, `hhw`, `hsw` | the characteristic water levels of the gauge |

A test holds this table to the columns the providers declare, so a column added to a provider is added here.

### Values

Values are just an extension of requests. `stations.values()` builds the reader of the values of the
stations, and you can query data station by station with its `.query()` method:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst import Options

# if no options are provided, default options are used which are
# Options(shape="long", humanize=True, convert_units=True)
request = DwdObservationRequest(
    parameters=[("daily", "kl"), ("daily", "solar")],
    start="1990-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=("00003", "01048"))

# From here you can query data by station
for result in stations.values().query():
    # analyse the station here
    break

df = result.df.drop_nulls("value")
df
```

Or you can query all data at once:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst import Options

# if no options are provided, default options are used which are
# Options(shape="long", humanize=True, convert_units=True)
request = DwdObservationRequest(
    parameters=[("daily", "kl"), ("daily", "solar")],
    start="1990-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=("00003", "01048"))
df = stations.values().all().df.drop_nulls("value")
df
```

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names. Instead of
``start`` and ``end`` you may as well want to use ``periods`` to update your
database once in a while with a fixed set of records.

A result can be cut down after the fact with ``values.filtered_by_date("2020-08")``, which takes the
same date strings as the CLI and the REST API and gives a new result back, leaving ``values`` as it
was. Each covers everything it names: ``"2020-08-01"``
is that whole day -- all 24 readings of it for hourly data -- ``"2020-08"`` the month and
``"2020"`` the year, while an interval such as ``"2017-01/2019-12"`` runs from the start of the
first span to the end of the second. A date carrying a time, ``"2020-08-01T12"``, names one
instant and is matched exactly.

The frame of every result has one schema, whatever the provider and whether it holds rows or not (a wide frame has the columns of the parameters that were delivered):
``station_id``, ``resolution``, ``dataset`` and ``parameter`` are ``String``, ``timestamp`` is
``Datetime("us", "UTC")``, so two results concatenate, and a values frame joins against a stations
frame, without a cast. The schemas are exported as objects to assert against:

```python
import polars as pl
from wetterdienst.model.schema import LONG_SCHEMA

df = stations.values().all().df
assert df.schema == LONG_SCHEMA

# filter by names that may or may not be present, and join on the station
subset = df.filter(pl.col("parameter").is_in(["temperature_air_mean_2m", "sunshine_duration"]))
merged = df.join(stations.df, on="station_id")
```

| Schema | Frame |
| --- | --- |
| `STATIONS_SCHEMA` | `request.df` and `StationsResult.df`: the columns every station has, in this order; a provider may add its own, among or after them |
| `LONG_SCHEMA` | `ValuesResult.df` with `Options(shape="long")` |
| `WIDE_SCHEMA`, `wide_schema(names)` | `ValuesResult.df` with `Options(shape="wide")`: the columns that do not depend on the request, and with the parameters' columns named |
| `INTERPOLATED_SCHEMA` | `InterpolatedValuesResult.df` |
| `SUMMARIZED_SCHEMA` | `SummarizedValuesResult.df` |

A test in the library holds each of them against what a result returns, so a change of a column, its
dtype or its place is a visible diff in a pull request and a breaking change.

```{note}
**Migrating from 0.154.0 or earlier.** `.values().all().df` used to store the four identity columns as polars `Enum`,
with the categories taken from the data of each result, while an empty result and an interpolated or
summarized one had `String`. They are `String` now. Code that cast them back, such as
`df.with_columns(pl.col(pl.Enum).cast(pl.String))`, or cast a join key or the column of an `is_in`,
can drop the cast, which does no harm where it stays. Code that read the `Enum`'s categories
(`df.schema["parameter"].categories`) takes them from the data, `df["parameter"].unique()`. A frame
you keep in memory can have the saving of the `Enum` back by casting it yourself, for instance to
`pl.Categorical`.
```

In case you use `filter_by_rank` you may want to skip empty stations. We can use the Options from
[settings](settings.md#options) to achieve that:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest

options = Options(skip_empty=True, skip_criteria="min", skip_threshold=0.2)
karlsruhe = (49.19780976647141, 8.135207205143768)
request = DwdObservationRequest(
  parameters=[("daily", "kl")],
  start="2021-01-01",
  end="2021-12-31",
  options=options,
)
stations = request.filter_by_rank(latlon=karlsruhe, rank=2)
values = stations.values().all()
print(values.df.head())
# df_stations has only stations that appear in the values
values.df_stations
```

#### Quality flags

Every reading has one string column, `quality_flags` (in the wide shape `<parameter>_quality_flags`), with the
flags its source publishes for it, null where the source gives none. What a code means differs from provider to
provider, so a code from one says nothing about one from another. The tokens, the codes of each provider and the
sentinels that are kept as `raw:<text>` are on the [quality flags](../data/quality-flags.md) page.

### Results

What a request answers is a result, and the results are what a caller reads:

| Result | Made by | Holds |
| --- | --- | --- |
| `StationsResult` | `request.all()` and the `request.filter_by_*` methods | `df`, the stations selected, and the `request` they come from |
| `ValuesResult` | `stations.values().all()`, and each step of `stations.values().query()` | `df`, the values, and the `stations` they were read for |
| `InterpolatedValuesResult` and `SummarizedValuesResult` | `request.interpolate()` and `request.summarize()` | `df`, the values of the point, and the `stations` they were made from |
| `HistoryResult` | each step of `stations.history().query()` | `history`, one station's history, and its `stations` |

- **A result is not changed once it is built.** Assigning to one raises `FrozenInstanceError`, and
  `filtered_by_date` and `filtered_by_sql` give a new result of the same kind back, so a result you hand
  on is the one you made. The frame-returning forms are `result.filtered_by_sql(sql).df`.
- **`request` is the request** that made a `StationsResult`, with the settings, options, parameters and
  window it was given (`stations.settings`, `.options`, `.parameters`, `.start` and `.end` read them).
  The stations are in `df`. How `df` was selected from them is the library's: `_df_all` (every station of
  the request), `_stations_filter` and `_rank` are private, as the underscore says, and a caller reads `df`.
- **`values()` and `history()` are methods.** Each builds a new reader on every call, so two walks over
  the stations never share state; keep the reader in a variable where you use it more than once.
- **A values result does not hold the reader** that produced it, so one you keep for a long job keeps
  the stations, their request and the frame alive, but not the reader. `df_stations` names the stations that have values.
- Every result but the history one has `to_dict`, `to_json`, `to_ogc_feature_collection`, `to_geojson`,
  `to_csv`, `to_format`, `to_target`, `to_plot` and `to_image`; the history one has `to_dict` and `to_json`
  only. They are documented below.
- **The formats take the arguments they have, and no others.** `to_json`, `to_geojson`,
  `to_ogc_feature_collection` and `to_plot` raise a `TypeError` for a keyword they do not know, so a typo such as
  `to_geojson(with_metdata=True)` is an error, and a type checker reports it. `to_csv` and `to_image` pass their
  keywords on (`to_csv` to polars' `write_csv`, `to_image` to the image: `fmt`, `width`, `height`, `scale` and
  `max_side`). `to_format(fmt, **kwargs)` takes one set of arguments for any format and gives each format those
  it takes (CSV none), which is what the command line, the REST API and MCP rely on.
- **A result is built by the library, and by keyword.** The constructors take keyword arguments only
  (`ValuesResult(stations=..., df=...)`); a positional call raises a `TypeError`.

```{note}
**Migrating from 0.155.0 or earlier.** The names a result had are refused with an error that says what
to write instead. `StationsResult.stations` (and the `stations=` argument) is `request`;
`stations.values.all()`, `.values.query()` and `.history.query()` are `stations.values().all()`,
`stations.values().query()` and `stations.history().query()`; `ValuesResult.values` is gone, use
`stations.values()` for a reader; `values.filter_by_date(date)` and `values.filter_by_sql(sql)`, which changed
the result and returned its frame, are `values.filtered_by_date(date)` and `values.filtered_by_sql(sql)`, which
return a new result (`.df` is its frame). Code that wrote `values.filter_by_sql(sql)` and went on with `values`
now continues with `values = values.filtered_by_sql(sql)`. Everything else that changed since 0.139.0 is in
[Migrating from 0.139.0](migrating.md).
```

### Interpolation & Summary

Wetterdienst can derive a time series for an arbitrary location from the surrounding
station network, either by spatial interpolation or by combining the nearest available
stations. See the dedicated [Interpolation & Summary](interpolation.md) chapter for the
full explanation, supported parameters, settings, CLI and REST usage.

### Format

A result renders itself in the formats below. The arguments are keyword-only and the ones in the table: a keyword a
method does not take is a `TypeError`. `to_format(fmt, **kwargs)` takes one set of arguments for any format and gives
each format those it takes, which is what the command line, the REST API and the MCP tools do.

| Method | `StationsResult` | `ValuesResult`, `InterpolatedValuesResult`, `SummarizedValuesResult` | `HistoryResult` |
| --- | --- | --- | --- |
| `to_dict` | `with_metadata` | `with_metadata`, `with_stations` | `with_metadata`, `with_stations`, `sections` |
| `to_json` | `with_metadata`, `indent` | `with_metadata`, `with_stations`, `indent` | `with_metadata`, `with_stations`, `sections`, `indent` |
| `to_geojson` | `with_metadata`, `indent` | `with_metadata`, `indent` | none |
| `to_ogc_feature_collection` | `with_metadata` | `with_metadata` | none |
| `to_csv` | `**kwargs` of polars' `write_csv` | the same | none |
| `to_image` | `**kwargs`: `fmt`, `width`, `height`, `scale`, `max_side` | the same | none |
| `to_plot` | none | none | none |

`indent` defaults to 4 (`True` is 4, `False` or `None` writes the JSON on one line); `with_metadata` and `with_stations` default to `False`.
`to_dict` and `to_ogc_feature_collection` return dictionaries typed as `StationsDict`, `ValuesDict`,
`InterpolatedValuesDict`, `SummarizedValuesDict` and `HistoryDict`, and the `...OgcFeatureCollection` of each, which
are importable from `wetterdienst.model.result` to annotate a function that takes or returns one. The block that
`with_metadata` adds is a `ResultMetadata`: the `provider`, the `producer` and `data_updated_at`, the date the source states for the data (UTC, `null` where it states none and for a list of stations). `to_target` writes to a file or a database, see [Export](#export).

#### To Dict

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "kl", "temperature_air_mean_2m"),
    start="2020-01-01",
    end="2020-01-02"
)
stations = request.filter_by_station_id(station_id="01048")
values = stations.values().all()
values.to_dict(with_metadata=True, with_stations=True)
```

#### To Json

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "kl", "temperature_air_mean_2m"),
    start="2020-01-01",
    end="2020-01-02"
)
stations = request.filter_by_station_id(station_id="01048")
values = stations.values().all()
print(values.to_json(with_metadata=True, with_stations=True))
```

#### To Ogc Feature Collection

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "kl", "temperature_air_mean_2m"),
    start="2020-01-01",
    end="2020-01-02"
)
stations = request.filter_by_station_id(station_id="01048")
values = stations.values().all()
values.to_ogc_feature_collection(with_metadata=True)
```

#### To GeoJson

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "kl", "temperature_air_mean_2m"),
    start="2020-01-01",
    end="2020-01-02"
)
stations = request.filter_by_station_id(station_id="01048")
values = stations.values().all()
print(values.to_geojson(with_metadata=True))
```

#### To CSV

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "kl", "temperature_air_mean_2m"),
    start="2020-01-01",
    end="2020-01-02"
)
stations = request.filter_by_station_id(station_id="01048")
values = stations.values().all()
print(values.to_csv())
```

### SQL

Querying data using SQL is provided by an in-memory [DuckDB](https://duckdb.org/) database.
In order to explore what is possible, please have a look at the
[DuckDB SQL introduction](https://duckdb.org/docs/sql/introduction).

The result data is provided as a table called ``df``, and the filter takes a single condition on
it, the part of a query after ``WHERE``: a second statement, ``ORDER BY`` or ``LIMIT`` is refused,
so sort or slice the returned frame instead. The condition runs on a DuckDB connection of its
own, which cannot read files, reach the network or load extensions, and holds nothing but the
frame.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest

options = Options(shape="long", humanize=True, convert_units=True)  # defaults
request = DwdObservationRequest(
  parameters=("hourly", "temperature_air", "temperature_air_2m"),
  start="2019-01-01",
  end="2020-01-01",
  options=options
)
stations = request.filter_by_station_id(station_id=[1048])
values = stations.values().all()
df = values.filtered_by_sql("parameter='temperature_air_2m' AND value < -7.0;").df
df
```

### Interpolation and summary at an elevation

`request.interpolate(latlon=..., elevation=1500)` and `summarize` take an `elevation` in metres, which brings each
station's readings to the height of the point first (air temperature falls about 0.65 K per 100 m). What is
corrected, which stations are left out and when a request is refused are in
[Interpolation & Summary](interpolation.md#elevation).

### Export

A result writes itself to a file (CSV, JSON, Excel, Parquet, Feather, Zarr, NetCDF) or a database (SQLite, DuckDB,
PostgreSQL, MySQL, CrateDB, InfluxDB) with `to_target(target)`, and `TimeseriesValues.to_target` does it station by
station. The targets, the `if_exists` modes and the errors are on the [Export](export.md) page.

## Errors

Every class of `wetterdienst.exceptions` derives from `WetterdienstError`
(`from wetterdienst import WetterdienstError`), so one `except` catches them all. A bad argument
the library refuses with a plain `ValueError` or `KeyError` is not one of them yet. Five classes
below it say what kind of failure it is:

| Class | Raised when | Also a |
| --- | --- | --- |
| `RequestError` | the request cannot be served as phrased and can be rephrased: an invalid parameter (`InvalidParameterError`), period, date, window or point | `ValueError` |
| `NotFoundError` | what the request names does not exist: a provider, network, resolution or dataset (`MetadataNotFoundError`), station or forecast run | `LookupError` |
| `ConfigurationError` | this installation cannot serve it: a missing credential or optional package | |
| `UpstreamError` | the provider's side failed or sent what the parser does not expect: `DownloadError`, `NoInternetError` | |
| `ExportRefusedError` | a sink will not perform the export, for a reason the caller can act on | |

```python
from wetterdienst import RequestError, UpstreamError, WetterdienstError

try:
    values = request.filter_by_station_id("01048").values().all()
except RequestError as e:
    print(f"rephrase the request: {e}")
except UpstreamError as e:
    print(f"the provider failed: {e}")
except WetterdienstError as e:
    print(f"wetterdienst refused: {e}")
```

Each class keeps the built-in classes it was before, so an `except ValueError`, `except OSError`,
`except FileNotFoundError` or `except IndexError` that caught it still does: `InvalidEnumerationError` is
a `RequestError` and a `ValueError`, `NoInternetError` an `UpstreamError` and an `OSError`,
`IssueNotFoundError` a `NotFoundError` and an `IndexError`, `MissingDependencyError` a
`ConfigurationError` and an `ImportError`, `CredentialRejectedError` (a provider answered 401 or 403 to the
credential you configured) a `ConfigurationError` and a `PermissionError`. The REST API, the MCP tools
and the command line decide by the class what to answer: a `RequestError` is a 400 or a usage error
(exit 2), a `NotFoundError` a 404, a `ConfigurationError` a 501, a `NoInternetError` a 503, any other
`UpstreamError` a 502 (a 504 where a timeout was its cause), and anything else, an unclassified
`WetterdienstError` included, the server's error, a 500. See [REST API](restapi.md#errors) for the body.

### Offline

A request made without a network connection raises `NoInternetError`: every provider, for its station
catalogue as for its values, and for a file listing as for a download. The message names the URL (without
its query or credentials) and the connection error is on `__cause__`. It is not an empty frame, which a
scheduled job could not tell from a source that has no data. It is told apart from a source that answered
badly, a 4xx or 5xx, a timeout or a body cut short, which is a `DownloadError`, and from a directory that
is not there, which lists as empty.

Catch it where an empty result is what the caller wants when offline:

```python
import polars as pl

from wetterdienst.exceptions import NoInternetError

try:
    df = request.all().df
except NoInternetError:
    df = pl.DataFrame()
```

## Type checking

The package ships `py.typed` (PEP 561), so mypy, pyright and ty read its annotations. The public
surface is typed end to end: a request gives a `StationsResult`, `stations.values().all()` a
`ValuesResult` whose `df` is a `pl.DataFrame`, `to_dict()` a typed dict whose `["values"]` you can
index, and `Wetterdienst.discover()` a `dict[str, dict[str, CoverageNetwork]]`. CI checks
`tests/typed_caller.py`, a script that uses the documented API, against the built wheel with `ty`,
and the same script was run through `mypy --strict` and `pyright` in strict mode by hand.

Two things to know when you type your own code against it. The values of a request come back long
or wide as its `shape` option says, which is decided when the request runs and not when it is
written, so `to_dict()["values"]` is declared as the union of the two kinds of rows. And the
attributes `settings`, `options`, `parameters`, `start` and `end` of a request are
declared as what its constructor accepts; read them from the result, where `stations.settings` is a
`Settings` and `stations.parameters` a `list[ParameterModel]`.

## Caching

The backbone of wetterdienst uses fsspec caching. It requires to create a directory under ``/home`` for the
most cases. For another place, set an environment variable ``WD_CACHE_DIR`` to define where the caching directory
should be created. A cache directory that cannot be created or written to, such as a Docker volume that root filled,
does not fail the requests: wetterdienst warns once and keeps the cache of that process in a temporary directory,
removed when it exits. Make the directory writable, or set ``WD_CACHE_DIR``, to keep the cache across runs.

To find out where your cache is located you can use the following code:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Settings

settings = Settings()
settings.cache_dir
```

Or similarly with the cli:

```{code-cell} bash

!wetterdienst cache
```

## FSSPEC

The downloads go through fsspec, which relies on aiohttp for asynchronous requests, and aiohttp may swallow errors
about a proxy or SSL. How to pass your own client arguments (a proxy from the environment, a timeout, headers) and a
certificate bundle is in [Settings](settings.md#python): `fsspec_client_kwargs` (`WD_FSSPEC_CLIENT_KWARGS`) and
`use_certifi`.
