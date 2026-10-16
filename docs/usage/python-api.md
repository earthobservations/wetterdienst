---
file_format: mystnb
kernelspec:
  name: python3
---

# Python API

## Introduction

The API offers access to different data products. They are outlined in more detail within the
[data](../data/overview.md) chapter.
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
`Wetterdienst.is_valid(Wetterdienst("aemet", "observation"))` asks for one network. The fields are
described with the [REST API](restapi.md#coverage), which lists the same.

To load any of the available APIs pass the provider and the network of data to the
wetterdienst api factory:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Wetterdienst

Wetterdienst(provider="dwd", network="observation")
```

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

``start`` and ``end`` are an ISO 8601 string or a ``datetime``; anything else, a year as an integer
such as ``start=2020`` among it, is a ``TypeError``. A bound given alone is the whole window: ``end``
without ``start`` is the same single instant as ``start`` without ``end``, so ``end="2020-01-05"`` asks
for that day, not for everything up to it. Pass both for a range. The command line reads ``--end``
alone the same way.

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
``ApiNotFoundError`` that ``Wetterdienst("foo", "bar")`` raises for a provider that does not exist.

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

#### filter by name

Station name filtering uses fuzzy matching (case-insensitive, via rapidfuzz's `WRatio`
scorer) so partial names, minor typos, and word-order variations are handled
automatically. In particular a bare place name resolves to its stations, e.g.
`name="Kiel"` matches `Kiel-Holtenau` and `Kiel-Kronshagen`.

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
`rank` parameter limits how many stations are returned (default 1).

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
stations that actually returned data, use `stations.values.all().df_stations` rather
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

Values are just an extension of requests. You can query data by using the
`.query()` method on the values object:

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
for result in stations.values.query():
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
df = stations.values.all().df.drop_nulls("value")
df
```

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names. Instead of
``start`` and ``end`` you may as well want to use ``periods`` to update your
database once in a while with a fixed set of records.

A result can be cut down after the fact with ``values.filter_by_date("2020-08")``, which takes the
same date strings as the CLI and the REST API. Each covers everything it names: ``"2020-08-01"``
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

df = stations.values.all().df
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
**Migrating from 0.154.0 or earlier.** `.values.all().df` used to store the four identity columns as polars `Enum`,
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
values = stations.values.all()
print(values.df.head())
# df_stations has only stations that appear in the values
values.df_stations
```

#### Quality flags

Every reading has one string column, `quality_flags` (in the wide shape `<parameter>_quality_flags`),
holding the flags its source publishes for it. It is null where the source gives none, which is the
case for every provider not listed below. Interpolated and summarized results have no such column, as
they are made of several stations' readings. The sources call the field by many names (DWD `QN`,
MIDAS `MESQL`, ECCC `Flag`, SMHI `Kvalitet`, GHCN `QFLAG`, NWS `qualityControl`, Frost `qualityCode`, Hubeau
`code_qualification_obs`, Météo-France `Q<parameter>`) and the meaning of a code differs from provider to
provider, so a code from one says nothing about one from another; none is a scale of better and worse
unless the table says so.

- A source with one flag: its plain code as the source writes it, only trimmed (`T`, `Good`, `3`).
- A source with several kinds of flag: the ordinary quality flag first as a plain code, then every other
  kind as `kind:code`, comma-separated, in a fixed order per provider (`G,measurement:T,source:7`,
  `3,element:E`). A blank flag is left out, so a plain token is always the quality flag, and
  `measurement:T` alone is a reading whose quality flag is blank.
- A value the provider maps from a missing-value sentinel carries the text the source wrote for it as the
  last token, `raw:<text>`, after the quality flag and the other kinds (`3,raw:-999`, `raw:-99.0`,
  `raw:NaN`). The value is null, or what the source documents the code to stand for (`0.0` for a
  precipitation of `-1.0`), and the text stays beside it. It is the cell as the source writes it, `-999.0`
  where the source writes that; where the value comes as a JSON number the text is the one the provider
  declares. The long shape drops the rows without a value by default, so the token shows with
  `drop_nulls=False` or in the wide shape; a filter on a null `quality_flags` as "no flag" meets
  these rows then.
- A value outside the physical range of its parameter that is no code (4021 degrees for a daily
  maximum, 17,802 mm for a month of rain) is treated the same way where the table below names the
  provider: null, with `raw:<number>` as the last token, the number as short as it can be written
  (`raw:4021`, `raw:110.26`). The ranges are generous and the same for every resolution, so a value that
  is only odd stays.
- `str.split(",")` takes the tokens apart; where a numeric code was used before, cast it:
  `pl.col("quality_flags").cast(pl.Int64, strict=False)`; a code that is no number (IMGW's `Z`) and a
  value with several tokens become null, so take the first token of a code that can be followed by
  `raw:` or a further kind: `pl.col("quality_flags").str.split(",").list.first().cast(pl.Int64, strict=False)`. The sentinel of a reading is
  `pl.col("quality_flags").str.extract(r"raw:([^,]*)$")`.

The table lists the plain codes and the further kinds; the `raw:` tokens are in the second table below it.

| Provider | codes in `quality_flags` |
| --- | --- |
| DWD observation | `QN`, the quality control level of the file's row: `1` only formal control, `2` controlled with individually defined criteria, `3` automatic control and correction, `5` historic, subjective procedures, `7` second control done, before correction, `8` quality control outside routine, `9` not all parameters corrected, `10` quality control finished (data up to 1980 reach `5` at best; 10 minutes data `1` to `3`). A larger number is a more thorough check. Hourly `sun` adds `zone:woz` for a stamp of a period in the station's local true solar time, not UTC (`10,zone:woz`). `DwdObservationRequest.describe_fields` prints the table of a dataset |
| DWD derived | hourly `radiation_global` and `sunshine_duration` (DUETT, `QN_952`): `500` DUETT data without station and satellite data, `501` on station data only, `502` on satellite data only, `503` on station and satellite data; the other derived datasets: null |
| DWD phenology | `Qualitaetsniveau`: `1` formal check only, `7` checked in routine but uncorrected, `10` checked and corrected |
| DWD road | the station's own verdict, from `qualityInformationAwsData`, or this library's: `1` suspect, `0` checked and not found suspect, null unknown ([details](../data/provider/dwd/road/15_minutes.md)) |
| DWD mosmix, dmo, poi, swsmos, radar and the other DWD networks | null (apart from `raw:`) |
| Met Office observation | the MIDAS `*_q` flag `MESQL`, a five digit compound code, written by the file as an integer so that its leading zeros are missing (`2576` is `02576`; `str.zfill(5)` restores them) (marker, estimate, status, query, level: [QC flags](https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html)); not a scale |
| RMI | the validation of the value in `qc_flags`: `1` validated, `0` not validated |
| IMGW meteorology | the status column beside the value: `8` no measurement (value null), `9` the phenomenon did not occur (value 0), `Z` a collective total (`o_d` only); `11` is this library's own, for a day absent from a month that is present (`daily/precipitation`, value 0). Blank status is null |
| IMGW hydrology, WSV, FMI, KNMI, IPMA, LHMT, MeteoSwiss, AEMET, Geosphere, Météo-France synop | null (apart from `raw:`) |
| DMI | `qcStatus`: `manual` quality controlled by DMI's climatologists, `none` not controlled; then `validity:true` or `validity:false`, whether the climatologists consider the value valid ("Invalid data is generally not correct"; mostly Greenland) |
| Hubeau (Eaufrance) | `code_qualification_obs`: `0` neutre, `4` faible, `8` forte, `12` douteuse, `16` non qualifiée, `20` bonne, `30` estimée |
| MET Norway Frost | `qualityCode`: `0` controlled and found O.K., `1` controlled and corrected or interpolated, `2` slightly uncertain, not controlled, `4` slightly uncertain, not corrected, `5` very uncertain, not corrected, `6` very uncertain, model data, `7` erroneous, not corrected |
| ECCC | the `*_FLAG` letter of the value: `M` missing, `E` estimated, `T` trace, ... (null for monthly) |
| EA hydrology | the reading's `quality`: `Good`, `Estimated`, `Suspect`, `Unchecked`, `Missing`; then `completeness:Complete` or `completeness:Incomplete`, whether the value is based on complete data (`Good,completeness:Complete`). Only daily readings carry it, and not all of them; a reading without one has the quality alone |
| Météo-France observation | the `Q<parameter>` code: `9` filtered, `0` protected, `1` validated, `2` doubtful |
| NOAA GHCN daily | `QFLAG,measurement:MFLAG,source:SFLAG` of the value's attributes: the check it failed (`X` bounds, `G` gap, ...), how the value was made (`T` trace, ...) and where it came from (`0` U.S. Cooperative Summary of the Day, ...), as in the GHCN-Daily `readme.txt` |
| NOAA GHCN hourly (GHCNh) | `QUALITY,measurement:MEASUREMENT,source:SOURCE`: the `<element>_Quality_Code` of the value as the file writes it, case included (`q` and `Q` differ), kept for a suspect or erroneous value too, then its `<element>_Measurement_Code` (how the value was made, by element and by source as Table 2 of the documentation lists it: `N` a normal and `C` a calm wind, `D` a derived relative humidity or wet bulb, `0` to `8` the tendency of the 3-hour pressure change, `T` or `2` a trace of precipitation, `1` and `2` of a snow depth, ...) and its `<element>_Source_Code` (the data source, `335`, `223`, ... as `ghcnh-source-list.pdf` lists it); a code the file leaves blank, or writes `Null` (sources 245 and 367), is left out, so `4,source:335` has no measurement code. The meaning of the quality code (and of the measurement code) depends on the element's source, as Table 3 of the [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf) lists it. Sources 313, 314, 315, 322, 335, 343, 344, 346: `0` passed gross limits, `1` passed all checks, `2` suspect, `3` erroneous, `4` to `7` the same four from an NCEI data source, `9` passed gross limits if the element is present; sources 220, 221, 222, 223, 347, 348: `0` not checked, `1` good, `2` suspect, `3` erroneous, `4` calculated, `5` removed. Sources 345 and 382 have codes of their own, and some sources have codes Table 3 does not list (`0` and `1` of source 401). A letter is mostly a check of the integration run on temperature, dew point, station and sea level pressure, wind direction and wind speed (`c` climatological outlier, `s` spike, `f` frequent value, `o` odd cluster, ...); on a derived humidity or wet bulb `f` is a suspect input and `o` a relative humidity out of range; `A`, `P`, `U` and the `q` of source 382 are legacy letters |
| CHMI | daily, 10 minutes, hourly: `QUALITY`, then `element:FLAG`: `0` good, `1` suspect, `2` poor, `3` estimated, `4` missing, `5` unknown (`meta4.csv`), and the letter of the element's own table (`meta3.csv`: SRA `T` an amount too small to measure, ...). Monthly and annual (no `QUALITY`, no `FLAG`): `interrupted:I`, the value is computed although daily values of the period are missing (`FLAG_INTERRUPTED`); `repeat:*` (`FLAG_REPEAT`, a `MAX` or `MIN` reached on more than one day) is read too but sits on `MAX`/`MIN` rows only, which no monthly or annual parameter is, so it does not show today. CHMI documents neither flag; the meaning is read from the files against their daily files |
| NWS | the MADIS `qualityControl` flag: `Z`, `C`, `S`, `V`, `X`, `Q`, `G`, `B`, `T` |
| SMHI | the `Kvalitet` code: `G` approved, `Y` suspect or aggregated |

##### Sentinels in `quality_flags`

| Provider | `raw:` text (value) |
| --- | --- |
| DWD observation | `-999` in every dataset (null); `-1` in the hourly cloud cover, `cloud_type` layers included, where the sky was not visible (null); `-99.9` in the five hourly `moisture` columns (null); `-1` in the hourly `weather_phenomena` `weather`, "not reported" (null); `990` in the wind direction of hourly and 10 minute `wind`, a variable direction (null) |
| DWD derived | `-999` and `-9999` (null) |
| DWD mosmix, dmo | `-` for a value the run does not have (null) |
| DWD poi | `---`, and any text that is no number (null) |
| DWD swsmos | any text that is no number (null); none is in the run file read on 2026-10-12 |
| AEMET | `99` in the wind direction of the daily maximum gust, calm or variable (null); any text that is no number in the daily, monthly and annual values (null) |
| DMI | `0` in the mean wind direction beside a mean wind speed of 0, calm (null); a value outside the range of its parameter, such as the 17,802 mm of a month of rain (null) |
| FMI | `NaN` (null); `-1.0` in `precipitation_amount` and `snow_depth`, none (0.0); any text that is no number (null) |
| Geosphere | `-1.0` in the daily `precipitation_amount` and `snow_depth`, and `-1` in the daily `snow_depth_manual` and `snow_depth_new`, none (0.0) |
| IMGW hydrology | `9999` in the stage, `99999.999` in the discharge, `99.9` and `9999` in the water temperature (null) |
| IPMA | `-99.0` (null); `0` in the wind direction, calm, or a code the eight points do not have (null) |
| KNMI | `NaN`, the fill value (null); `-1` in `precipitation_amount`, a trace (0.0) |
| Met Office observation | `NA`, and any text that is no number (null); a day with an `NA` beside readings has the value of the readings |
| MET Norway Frost | `-1` in `snow_depth`, no snow (0.0); `-3` and `9` in `cloud_cover_total`, not estimated (null); the code as Frost documents it |
| Météo-France observation | `9` in the hourly cloud cover, the sky is invisible (null); `0` and `999` in the wind directions `DD` (hourly) and `DXI` (daily), no direction (null); any text that is no number (null) |
| Météo-France synop | `-0.1` in the precipitation, a trace (0.0); `101` in the cloud cover, the sky is obscured (null); any text that is no number (null) |
| RMI | a value outside the range of its parameter, such as the 4021 degrees of a daily maximum (null) |
| NOAA GHCN hourly | `999` in `wind_direction`; `-9999` in `precipitation`; `-None` in any column (null) |

The other providers write their missing values as an empty field, a JSON null or a status that the plain code
already carries (IMGW meteorology: `8`), and have no `raw:` token. DWD road decodes BUFR, which has no text of a
missing value. CHMI, MeteoSwiss, SMHI, DWD phenology and the real-time values of AEMET read a text that is no
number as null without a token; none was found in their files, and DWD observation does the same for a letter
outside `P` and `I` in a measurement method.

### Interpolation & Summary

Wetterdienst can derive a time series for an arbitrary location from the surrounding
station network, either by spatial interpolation or by combining the nearest available
stations. See the dedicated [Interpolation & Summary](interpolation.md) chapter for the
full explanation, supported parameters, settings, CLI and REST usage.

### Format

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
values = stations.values.all()
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
values = stations.values.all()
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
values = stations.values.all()
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
values = stations.values.all()
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
values = stations.values.all()
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
values = stations.values.all()
df = values.filter_by_sql("parameter='temperature_air_2m' AND value < -7.0;")
df
```

### Interpolation and summary at an elevation

Air temperature falls with height -- about 0.65 K per 100 m, a dew point about 0.2 -- so stations
at different altitudes say different things about the same weather. Interpolating them as they come
fits that vertical difference as though it were horizontal: around Garmisch the stations within
40 km span 630 m to 2956 m, which is 15 K of it.

Give the point an ``elevation`` in metres and each station's readings are brought to it first:

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "kl", "temperature_air_mean_2m")],
    start="2022-01-01",
    end="2022-01-05",
)
request.interpolate(latlon=(47.48, 11.06), elevation=1500)   # on the mountain
request.interpolate(latlon=(47.48, 11.06), elevation=200)    # in the valley
```

``summarize`` takes the same argument, where it matters more still: a summary answers with one
station's reading rather than a blend, so nothing softens the difference in altitude.

``interpolate_by_station_id`` and ``summarize_by_station_id`` answer at the named station's own
altitude unless told another one, that being the one case where the elevation is known without
being given. For the reading uncorrected, pass the station's coordinates to ``interpolate``.

A station whose own elevation the provider does not report cannot be placed against the elevation
asked for, so it is left out rather than contributing at its own altitude while its neighbours are
moved. Some providers report no station elevations at all, in which case an elevation leaves nothing
to interpolate from for the quantities that depend on it.

Left out, nothing is corrected. The elevation cannot be derived from the stations themselves: an
elevation taken from the same linear interpolation cancels out of the correction exactly, leaving
the result unchanged, so it has to come from the caller.

### Export

Data can be exported to [SQLite](https://www.sqlite.org/), [DuckDB](https://duckdb.org/docs/sql/introduction),
[InfluxDB](https://github.com/influxdata/influxdb), [CrateDB](https://github.com/crate/crate) and more targets.
A target is identified by a connection string.

Examples:

- sqlite:///dwd.sqlite?table=weather
- duckdb:///dwd.duckdb?table=weather
- influxdb://localhost/?database=dwd&table=weather
- crate://localhost/?database=dwd&table=weather

File targets are identified by their extension:

- file:///path/to/dwd.csv
- file:///path/to/dwd.json
- file:///path/to/dwd.jsonl
- file:///path/to/dwd.xlsx
- file:///path/to/dwd.parquet
- file:///path/to/dwd.feather
- file:///path/to/dwd.zarr
- file:///path/to/dwd.nc

CSV and spreadsheets are written the way ``to_csv`` returns them, with timestamps as ISO strings
and a list of station ids as one comma-separated field. JSON and JSON Lines hold the same records
with the list kept as a list, JSON having arrays of its own, rather than the response envelope
``to_json`` wraps them in. Zarr and NetCDF go through xarray, grouped by the datasets the frame holds;
NetCDF writes its timestamps as CF units, Zarr as the nanoseconds since the epoch it reads back.

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start="2019-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=[1048, 1050])
stations.values.to_target("influxdb://localhost/?database=dwd&table=weather", if_exists="append")
```

The previous example uses a batch approach meaning each station is written one by one. The first station is written
with the `if_exists` given and every station after it with `append`, so the sink has to accept `append` — which is why
this form passes it explicitly rather than taking the `fail` that `TimeseriesValues.to_target` defaults to.

You could also first collect all data and then write it at once:

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start="2019-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=[1048, 1050])
stations.values.all().to_target("influxdb://localhost/?database=dwd&table=weather")
```

You could also iterate over the stations and write them one by one:

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start="2019-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=[1048, 1050])
for station in stations.values.query():
    station.to_target("influxdb://localhost/?database=dwd&table=weather", if_exists="append")
```

The argument `if_exists` supports the following modes:

- `fail`: Raise an error if the table/file already exists.
- `replace`: Drop the table/file before inserting new values.
- `append`: Insert new values to the existing table (not supported by files).
- `skip`: Do nothing if the table/file already exists.

`replace` is the default on a result — `StationsResult`, `ValuesResult`, anything carrying a frame.
`TimeseriesValues.to_target`, the batch form above, defaults to `fail` instead and then writes
every station after the first with `append`, because there it is one table being filled station by
station rather than one frame being written.

InfluxDB takes `replace` and `append`, which do the same thing there: every write is points, and a
point carrying the timestamp and tags another already has replaces that one, so `replace` does not
clear what is already in the measurement. `fail` and `skip` are refused, because both turn on
whether the measurement exists and this sink never asks.

An append into a database matches columns by name rather than by position, so a frame carrying a
column the table does not have is refused instead of being filed under whatever heading sat in that
position. A frame that is a *subset* of the table's columns is accepted, with nulls for the rest.

Every refusal — a mode the sink does not do, a target that already holds data under `fail`, or a
format or protocol nothing here writes — raises `ExportRefusedError` (from `wetterdienst.exceptions`),
whose message is the whole of what there is to know. A package a sink needs that is not installed
(DuckDB, SQLAlchemy, xarray) raises `MissingDependencyError`, an `ImportError` naming the extra
that installs it. Anything else out of `to_target` is a defect or an environment problem and keeps
its own class and traceback.

The CLI takes the same argument as `--if_exists`, which is what a scheduled acquisition needs —
see [Scheduling](scheduling.md):

```bash
wetterdienst values --provider=dwd --network=observation \
    --parameters=daily/kl/temperature_air_mean_2m --periods=recent --station=01048 \
    --target="duckdb:////var/lib/wetterdienst/obs.duckdb?table=weather" --if_exists=append
```

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
    values = request.filter_by_station_id("01048").values.all()
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
(exit 2), a `NotFoundError` a 404, a `ConfigurationError` a 501, a `NoInternetError` a 503, and anything else, an unclassified
`WetterdienstError` included, the server's error. See [REST API](restapi.md#errors) for the body.

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

FSSPEC is used for flexible file caching. It relies on the two libraries requests and aiohttp. Aiohttp is used for
asynchronous requests and may swallow some errors related to proxies, ssl or similar. Use the
setting `fsspec_client_kwargs` (environment variable `WD_FSSPEC_CLIENT_KWARGS`) to pass your very own client kwargs
to fsspec, which are merged into the default ones (see [Settings](settings.md)) e.g.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

settings = Settings(fsspec_client_kwargs={"trust_env": True})  # use proxy from environment variables

request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    settings=settings
)
stations = request.filter_by_station_id(station_id=[1048])
stations
```