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

The periods argument typically can be used as replacement for the start and end
arguments. In case both arguments are given they are used as a filter for the data. Left out, the
periods are derived from ``start``/``end`` where the provider publishes on a release
schedule that says which period holds which years -- DWD observation and DWD phenology do -- and
are otherwise every period the requested datasets publish.

Regarding the definition of requested parameters:

## Data

In case of the DWD, requests can be defined by either of period or
``start`` and ``end``. Use ``DwdObservationRequest.discover()``
to discover available parameters based on the given filter arguments.

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

The metadata columns ``station_id``, ``resolution``, ``dataset`` and ``parameter`` of the
DataFrame returned by ``.values.all()`` are stored as polars
[``Enum``](https://docs.pola.rs/api/python/stable/reference/api/polars.datatypes.Enum.html)
instead of ``String`` to reduce the memory footprint (these columns repeat on every row and
``Enum`` stores them as small integer codes). ``Enum`` behaves like ``String`` for most grouping,
sorting and ``==`` comparisons, but it has a few sharp edges: it does not support the ``.str``
namespace, it compares unequal to a ``String`` column (so joins need matching dtypes), and
``is_in([...])`` **raises** on polars 1.x if any of the given values is not one of the column's categories
(e.g. filtering for a parameter that is absent from the result) instead of returning an empty
selection; polars 2 answers with the rows of the categories it has. If you need plain ``String`` columns again — e.g. for ``.str`` operations,
``is_in`` with possibly-absent values, strict dtype checks or when concatenating with a
``String`` DataFrame — cast them back:

```python
import polars as pl

# cast every Enum column back to String
df = df.with_columns(pl.col(pl.Enum).cast(pl.String))
```

This matters in particular for ``station_id``: polars raises a ``SchemaError`` when a join
key is ``Enum`` on one side and ``String`` on the other. The stations DataFrame
(``request.df``) keeps ``station_id`` as ``String``, so joining it — or any other ``String``
station table — with the values DataFrame requires casting the join key first:

```python
import polars as pl

# join values (Enum station_id) with a String station table
merged = df.with_columns(pl.col("station_id").cast(pl.String)).join(stations, on="station_id")
```

It also affects filtering by name with ``is_in``. On polars 1.x there is no "soft"/non-raising flag on
``is_in`` — if any queried value is not a category of the ``Enum`` column it raises instead of
returning an empty selection. Cast the column to ``String`` for the comparison, which behaves the same on
every polars version (an ``==`` check against a single value, on the other hand, does handle absent values
gracefully):

```python
import polars as pl

# filter by parameters that may or may not be present in the result
subset = df.filter(pl.col("parameter").cast(pl.String).is_in(["temperature_air_mean_2m", "sunshine_duration"]))
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
- `str.split(",")` takes the tokens apart; where a numeric code was used before, cast it:
  `pl.col("quality_flags").cast(pl.Int64, strict=False)`; a code that is no number (IMGW's `Z`) and a
  value with several tokens become null, so take the first token of a code that can be followed by
  `raw:` or a further kind: `pl.col("quality_flags").str.split(",").list.first().cast(pl.Int64, strict=False)`. The sentinel of a reading is
  `pl.col("quality_flags").str.extract(r"raw:([^,]*)$")`.

The table lists the plain codes and the further kinds; the `raw:` tokens are in the second table below it.

| Provider | codes in `quality_flags` |
| --- | --- |
| DWD observation | `QN`, the quality control level of the file's row: `1` only formal control, `2` controlled with individually defined criteria, `3` automatic control and correction, `5` historic, subjective procedures, `7` second control done, before correction, `8` quality control outside routine, `9` not all parameters corrected, `10` quality control finished (data up to 1980 reach `5` at best; 10 minutes data `1` to `3`). A larger number is a more thorough check. `DwdObservationRequest.describe_fields` prints the table of a dataset |
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
| FMI | `NaN` (null); `-1.0` in `precipitation_amount` and `snow_depth`, none (0.0); any text that is no number (null) |
| Geosphere | `-1.0` in the daily `precipitation_amount` and `snow_depth`, and `-1` in the daily `snow_depth_manual` and `snow_depth_new`, none (0.0) |
| IMGW hydrology | `9999` in the stage, `99999.999` in the discharge, `99.9` and `9999` in the water temperature (null) |
| IPMA | `-99.0` (null); `0` in the wind direction, calm, or a code the eight points do not have (null) |
| KNMI | `NaN`, the fill value (null); `-1` in `precipitation_amount`, a trace (0.0) |
| Met Office observation | `NA`, and any text that is no number (null); a day with an `NA` beside readings has the value of the readings |
| MET Norway Frost | `-1` in `snow_depth`, no snow (0.0); `-3` and `9` in `cloud_cover_total`, not estimated (null); the code as Frost documents it |
| Météo-France observation | `9` in the hourly cloud cover, the sky is invisible (null); `0` and `999` in the wind directions `DD` and `DXY` (hourly) and `DXI` (daily), no direction (null); any text that is no number (null) |
| Météo-France synop | `-0.1` in the precipitation, a trace (0.0); `101` in the cloud cover, the sky is obscured (null); any text that is no number (null) |
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