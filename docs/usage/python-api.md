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

Each network says what it is: `name_short`, `country`, `url`, `kind` and `scope` (how far it reaches: `global`,
`national` or `regional`), `auth`, `configured` and `date_required`, where `observation`, `forecast` and
`derived` are the timeseries networks, which have stations and values, and `radar`, `alerts` and `storm_cells`
(`dwd/radar`, `dwd/alerts`, `dwd/storm_cells`) are standalone, with request classes and results of their own. Nothing is
downloaded, so whether a provider accepts the credentials you have is not part of it:
`Wetterdienst.is_valid(Wetterdienst.resolve("aemet", "observation"))` asks for one network. `discover()` is the
Python counterpart of the REST route [`/api/providers`](restapi.md#providers), which lists the same networks
in another shape: `name_short` and `country` once for each provider (not for each network), `scope` as
`extent.scope` beside the `continents` and the `bbox`, and the terms of the provider besides. The resolutions,
datasets and parameters of one network are `/api/coverage`, which is the `discover()` of the request class of a network.

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

`resolve` is for the networks that have stations and values. The three that have not, `dwd/radar`,
`dwd/alerts` and `dwd/storm_cells` (`Wetterdienst.standalone`), take other arguments and give other results, so they have an entry
point of their own, `Wetterdienst.resolve_standalone`, and `resolve` refuses them with an
`ApiNotFoundError` that says so. Both are typed: `resolve` gives a `type[TimeseriesRequest]`, and
`resolve_standalone("dwd", "radar")` the `DwdRadarValues` class. The classes can also be imported, which is
what the examples do.

The point lookup is in no registry: `DwdKostraRequest` of the heavy-rainfall statistics
([KOSTRA](../data/provider/dwd/kostra/index.md)), which is imported from `wetterdienst.provider.dwd.kostra`.

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

A dataset the provider serves by a window (`date_required` in the coverage, as for MET Norway Frost, FMI, DMI
or the WSV gauges) needs both: `stations.values()` raises `DateRequiredError`, a `ValueError`, naming the dataset
when the request has none, as the REST API, the command line and MCP refuse it. Listing the stations needs no
window.

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

#### filter by WMO number, WIGOS identifier or ICAO code

A station may have identifiers besides its `station_id`, in the columns `wmo_id`, `wigos_id` and `icao_id` of the
stations frame (see [the station columns](#the-ids-of-a-station)). `filter_by_wmo_id`,
`filter_by_wigos_id` and `filter_by_icao_id` select the stations that have one of the ids given, which is more than
one station where an id is on several (NOAA lists a station that was registered anew under two ids; DWD lists
five of its MOSMIX ICAO codes twice). Each station comes back with a row for every requested dataset, in the order
of the catalogue, and an id that no station has is left out with an `unknown-station` warning, so that the result may
be empty. Like `filter_by_station_id` they select among the whole list, whatever the window of the request.

```python
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

request = DwdMosmixRequest(parameters=("hourly", "large"))
request.filter_by_wmo_id(10381)  # Berlin-Dahlem; "10381" and ("10381", "10147") do too
request.filter_by_icao_id("eddh")  # the case does not matter
request.filter_by_wigos_id("0-20000-0-10381")  # an issuer written "056" finds the "56"
```

What is given is read in the notation of the column before it is compared: one to five digits of a WMO number get
their leading zeros (`1001` finds `01001`), an ICAO code is upper-cased, and the numbers of a WIGOS identifier
lose theirs. An id that cannot be one of the column (`"abc"`, six digits, `"ED"`) raises a `ValueError` that names
the notation, rather than answering as if no station had it. A provider whose station list carries no such ids has
the column null, so a search finds nothing there.

The command line (`--wmo-id`, `--wigos-id`, `--icao-id`), the REST API and MCP (`wmo_id`, `wigos_id`, `icao_id`)
take them for `stations` and `values`, comma-separated, as one of the ways to select stations: not with `stations`,
`name` or another of the selections.

(filter-by-region)=

#### filter by region

`filter_by_region` selects every station that its provider lists under a region: the `region` column of the stations
frame, which is what *the source* names (a state, province, county, canton or département), null where it names
none. It answers a question that a name cannot, such as "the lowest temperature in Hamburg", which needs all of the
stations the source lists under Hamburg, and a name matches the stations whose names hold the word, a few at a time
(the best five of a `stations` listing).

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(parameters=("daily", "kl"), periods=("historical", "recent"))
stations = request.filter_by_region("Hamburg")
stations.df.select("station_id", "name", "latitude", "longitude", "start_timestamp", "end_timestamp")
```

The region is the source's, and so is the spelling. DWD's `Hamburg` is twelve stations of `daily/kl`: nine on land
(`Hamburg-Fuhlsbüttel`, `Hamburg-Bergedorf`, `Hamburg-Neuwiedenthal`, `Hamburg (Deutsche Seewarte)`, ...) and three at
sea in the North Sea that DWD files under Hamburg as well: `UFS Deutsche Bucht` (54.18 °N, 7.46 °E), `UFS TW Ems`
(54.17 °N, 6.35 °E) and `Nordseeboje 2` (a buoy at 55.0 °N, 6.33 °E). The answer names every station with its position,
so a caller that wants the city alone leaves the stations at sea out by their position or their name.

What a region is called differs by provider, and so does how many stations have one (checked against the live lists):

| What `region` holds | Networks |
| --- | --- |
| the German state written out (`Hamburg`, `Baden-Württemberg`) | `dwd/observation`, `dwd/derived` (all its datasets but `monthly/climate_correction_factor`, whose stations have none), `dwd/phenology` (16 states; the 1 minute precipitation of `dwd/observation` has two stations without one and four in `Tirol`) |
| the two letters of the state | `dwd/road` (`HH`, `NW`) |
| the state or states as DWD writes them | `dwd/pollen` (`Niedersachsen und Bremen`) |
| the Austrian state, the Swiss canton, the Canadian province | `geosphere/observation` (`Niederösterreich`), `meteoswiss/observation` (`ZH`), `eccc/observation` (`BC`) |
| the US state or Canadian province code | `noaa/ghcn`: 88,918 of the 132,894 stations of `daily` and 6,250 of the 38,870 of `hourly` have one (75 and 67 codes: `AK`, `TX`, `BC`); the others have none |
| the département | `eaufrance/hubeau` in capitals without accents (`FINISTERE`, 2 of 1,713 stations without), `meteofrance/observation` as its number (`09`, `972`) |
| the municipality | `fmi/observation` (`Helsinki`; 4 of 437 stations without) |
| the county or province | `metno/frost` (`TRØNDELAG`), `metoffice/observation` (`cumbria`), `aemet/observation` (`ILLES BALEARS`): read from stubs of the lists, which need a key |
| none, the column is null | `dwd/derived` `monthly/climate_correction_factor`, `dwd/mosmix`, `dwd/dmo`, `dwd/poi`, `dwd/swsmos`, `dwd/uvi`, `dmi/observation`, `rmi/observation`, `smhi/observation`, `wsv/pegel`, `nws/observation`, `meteofrance/synop`, `chmi/observation`, `ipma/observation`, `lhmt/observation`, `ea/hydrology`, both `imgw` networks, `knmi/observation` (a stub; it needs a key) |

A station without a region is in none: no region selects it, and the refusal of a region that is not there says how
many stations of the network are in that case.

A region is compared the way a station name is, whole and not fuzzily: without regard to case, accents or
transliteration, and with a hyphen, an apostrophe or a space as the one break between words, so that `hamburg`,
`Baden Wuerttemberg` and `Cotes d'Armor` find `Hamburg`, `Baden-Württemberg` and `COTES-D'ARMOR`. Nothing else is
read into it: `Hesse` is no `Hessen`, since no table of the names in other languages stands behind it, and a station is
in the region its provider says, which is not always where it stands.

```python
request.filter_by_region(["Hamburg", "Bremen"])  # several regions, all their stations in catalogue order
# raises UnknownRegionError, see below
request.filter_by_region("Hesse")
```

Several regions are a list (a text is one region, a comma in it is no separator; the command line, the REST API and MCP
read a comma-separated list). Like `filter_by_station_id` the filter selects among the whole list, whatever the window
of the request. A region the list does not have is refused with an `UnknownRegionError` (a `RequestError`, so a
`ValueError`, and a 400 over REST), which names it, the closest regions of the list and the regions there are, at most
twenty of each and the number of the others, with control characters replaced and long names cut:
`DwdObservationRequest has no station in the region 'Hesse'. Closest: 'Hesse': 'Hessen'. The regions there are:
Baden-Württemberg, Bayern, ...`. Where some stations of the network have no region, it ends with how many (`2 of the
1,713 stations have no region, and no region selects them.`). The error keeps what it names as `unknown`, `known` and
`hints`. Where the stations of the requested parameters have no region, the request is refused with a `NoRegionsError`
(an `UnknownRegionError`) that says so and advises `name`, a point or a bounding box. Neither is an empty result, which a caller could not tell from a
region that has no station in the window. A list of stations that is empty is the exception: it has no region to
refuse, and the result is empty, as for every other selection.

Where the lookup of the stations went without a listing of the provider (`dwd/observation` and `dwd/derived` skip a
directory that came back empty or missing, with a `file-skipped` warning), a region that is found is answered, and a
region that is not found, or a list that came back empty or without any region, may be one the skipped directory
holds: it is a `RegionListingIncompleteError`, an `UpstreamError` (a 502 over REST, as for a station asked for by id)
that names the directories, and not a refusal of the caller's. A directory whose files name their stations (it lists no
description) holds a region only if one of those stations is not in the list; an empty or missing one may hold any.
The sentence names at most twenty of the regions asked for, as the refusal of an unknown region does, and `regions`
of the error has them all.

The command line (`--region`), the REST API and MCP (`region`) take it for `stations` and `values`, as one of the ways
to select stations: not with `stations`, `name` or another of the selections. `interpolate` and `summarize` take a
point or one station, and `history` ids: they take no `region`.

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
The rows come back best match first. A name that holds the whole query as a run of whole words
(`Tiefland Sachsen-Anhalt` in `Sachsen-Anhalt: Tiefland Sachsen-Anhalt`) matches at any threshold below 1 and comes before every
name that does not, whatever its score: `Bayern` finds all four parts of Bayern, and `Sachsen` the parts of
Sachsen and of Sachsen-Anhalt before those of Niedersachsen, which holds `niedersachsen` as one word. Among
those, and among the other names, equal scores the closer whole name first (`Saarland` finds
`Rheinland-Pfalz und Saarland: Saarland` before a longer name that holds it), a tie on both in the order of
their `station_id`.

`filter_by_name` matches the name among the stations that have a record in the `start` and `end` of the
request, as the command line, the REST API and MCP do with a `timestamp`: a station that closed before
the window, or began after it, is not the best match for a name while one of that name has the readings. A
station is left out when it started after the window, or ended before it by more than the buffer; a
station whose start or end is not published is kept. A request without a window matches among all of
them. The window is applied to a `df_all` you pass as well, so that the result does not depend on how
you got the stations. The other filters (`filter_by_station_id`, `filter_by_rank`, `filter_by_distance`,
`filter_by_region`, `filter_by_bbox`, `filter_by_sql`) select among the whole list, whatever the window.

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
nothing while `name="Cottbus"` returns just `Cottbus`, for `daily/precipitation_more` in January 2020; a name
that holds the query as a word, such as `Kiel-Holtenau`, is no match at 1.0 though it is one at any lower
threshold); or, for strict string equality, use `filter_by_sql`, e.g. `filter_by_sql("name = 'Cottbus'")`.

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

(the-ids-of-a-station)=

#### The ids of a station

The columns of `STATIONS_SCHEMA` are the same on every provider, but not always filled: `region` is the
sub-national unit the source names (a state, province, county, canton or département), whatever it is called
there, and null where the source names none; `filter_by_region` selects by it (see [filter by region](#filter-by-region)). The last three are the identifiers a station may have besides its
`station_id`, each in one notation whichever provider lists it, and null where the provider publishes none:

| Column | Notation | Filled by |
| --- | --- | --- |
| `wmo_id` | the WMO station number: five digits with leading zeros, `01001` or `10381`; a value that is not that (a source's junk, an id of another scheme) is null | `dwd/mosmix`, `dwd/dmo` and `dwd/poi` for the stations whose `station_id` is the number (the others carry an id of DWD's own, `A191`; but for block 99 and seven ids that WMO's register OSCAR lists for another station 100 km or more away, see `WMO_ID_CORRECTIONS` in `provider/dwd/catalogue.py`), `geosphere/observation`, `knmi/observation`, `meteofrance/synop`, `noaa/ghcn`; from the number the list publishes: `dwd/observation` (the Stationslexikon's number of the products `SY` and `MN`, 314 of its 13,779 stations; the station descriptions have none) and `dwd/derived` for the degree days, the degree hours and the soil (the stations of the other datasets have none), `aemet/observation` (`indsinop`), `dmi/observation` (`wmoStationId`, only in the blocks of Greenland, Denmark and the Faroe Islands), `nws/observation` (column 1 of the MADIS table; its station id is no ICAO code, so `icao_id` is null there), `eccc/observation`, `fmi/observation`, `metno/frost`; from a WIGOS id of the issuer 20000 (`0-20000-0-<number>`): `chmi/observation`, `meteoswiss/observation`, `rmi/observation` |
| `wigos_id` | the WIGOS station identifier, `<series>-<issuer>-<issue number>-<local id>`, the first three numbers without leading zeros (`0-20000-0-10381`, `0-56-101-01002`), the local id as published | `chmi/observation`, `knmi/observation`, `meteoswiss/observation`, `metno/frost`, `rmi/observation`; from WMO's register OSCAR/Surface, where the provider's `station_id` is the local part of a WIGOS id of its country's own issuer: `dwd/observation` and `dwd/derived` (`0-276-<issue number>-<Stations_ID>`), `fmi/observation` (`0-246-0-<fmisid>`) and `dmi/observation` (`0-208-0-<stationId>`, Greenland included), see [WIGOS ids of the stations](../data/provider/dwd/observation/index.md#wigos-ids-of-the-stations) |
| `icao_id` | the ICAO location indicator of the aerodrome, four upper-case letters (`EDDH`) | `dwd/mosmix`, `dwd/dmo`, `dwd/poi`, `fmi/observation`, `metno/frost`, `noaa/ghcn` (hourly) |

A provider that does not publish one of them has it null, which is no statement that the station has none:
the `station_id` of `dwd/observation` is DWD's own number, which is not the WMO number, and only 314 of its
stations have a `wmo_id` (from the Stationslexikon). Search by them with
`filter_by_wmo_id`, `filter_by_wigos_id` and `filter_by_icao_id` (see above).

#### Station columns of a provider

Behind the columns of the schema, a provider adds the columns of its own that its station list has, null for a
station the source gives none:

| Provider and network | Column | What it holds |
| --- | --- | --- |
| `chmi/observation` | `gh_id` | CHMI's own code of the station, `L3CHEB01` (the `station_id` is its WIGOS identifier) |
| `dmi/observation` | `country` | DMI's three-letter code of the country the station is in: `DNK`, `GRL` or `FRO` |
| `dwd/road` | `station_group`, `road_name`, `road_sector`, `road_type`, `road_surface_type`, `road_surroundings_type` | the road a station is on and its surroundings, as DWD's list gives them |
| `ea/hydrology` | `nrfa_id`, `rloi_id` | the station's number in the National River Flow Archive (`52017`) and its id in River Levels on the Internet (`3060`; the all-digit, then the lowest, where the listing gives two) |
| `eaufrance/hubeau` | `gauge_zero`, `gauge_zero_datum`, `site_id` | the altitude of the gauge's zero and the reference system it is given in, and the eight-character code of the hydrometric site the station is one of (`10110001` for `1011000101`) |
| `eccc/observation` | `climate_id`, `tc_id` | the seven-character Climate ID the station has in ECCC's Climate Data Online, and Transport Canada's three-letter identifier of an airport (`YVR`), which is no ICAO code |
| `imgw/hydrology` | `river`, `river_kilometer` | the river the gauge is on, with its hydrographic code as IMGW lists it (`Odra (1)`), and its position along it in kilometres, counted from the mouth |
| `imgw/hydrology` | `gauge_zero`, `gauge_zero_datum` | the altitude of the gauge's zero in metres above sea level, and the datum, which IMGW's list does not state, so it is null |
| `imgw/meteorology` | `river`, `short_code` | the river catchment the station is listed under, with its hydrographic code (`Odra (1)`), and IMGW's code of the station from `wykaz_stacji.csv` (`375`, `5409`), which is no WMO number |
| `wsv/pegel` | `river`, `river_kilometer` | the river the gauge is on, as Pegelonline publishes it (`ELBE`), and its position along it in kilometres, the waterway kilometre, which grows downstream |
| `wsv/pegel` | `gauge_zero`, `gauge_zero_datum` | the altitude of the gauge's zero and the datum it is given in |
| `wsv/pegel` | `m_i`, `m_ii`, `m_iii`, `mnw`, `mw`, `mhw`, `hhw`, `hsw` | the characteristic water levels of the gauge, in metres, converted from the unit Pegelonline lists them in, as `stage` is by default |

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

#### Plausibility checks

A number no sensor can have produced (4021 °C for a daily maximum, 1093.3 hPa at a station at sea level, a barometer
that held one value for a month) is judged by a **check**, and the option `plausibility` chooses what happens to it,
per check: `"hard"` makes the value null and keeps the number as `rejected:<check>,raw:<number>` in `quality_flags`,
`"soft"` keeps the value and flags it `suspect:<check>`. The checks are `range`, `elevation`, `stuck`, `consistency`,
`floor`, `limits`, `source`, `step` and `relations`; all are hard but `stuck` and `step`, which are soft because they judge a series and not a value (what `stuck` finds depends on what was read, and `step` is a jump between consecutive readings, which a front also makes; see the
[plausibility page](../data/plausibility.md)), `relations`, which is soft because it flags both readings of two that contradict each other and cannot tell which is wrong (it is not `consistency`, the hard check of a provider's own rules), and `source`, which is soft because its verdict is the source's own: a value the provider's quality flag marks as erroneous or doubtful (GHCN-Daily `QFLAG`, Frost `qualityCode` 7, an Environment Agency `Suspect`, DMI `validity:false`, ...) is flagged `suspect:source`, or null with `rejected:source` in `"hard"` (the suspect level of a source that has two, GHCNh `Suspect` and source 382 `R`, CHMI `Suspect`, MADIS `Questioned`, GHCNh `f`, stays flagged). A check not named keeps its mode, and `WD_TS_PLAUSIBILITY__RANGE=soft` sets one for a host. On a forecast network (`kind` `forecast`: `dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`, `dwd/pollen`, `dwd/uvi`) every check but `floor` and `limits` is soft whatever you set, so `"hard"` there flags a value `suspect:<check>` and never nulls it: a forecast is a model's output and no reading. The codes a source documents
(`-999`, a calm, a trace) are no check and have no mode.

```python
import polars as pl
from wetterdienst import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "pressure_air_site_mean")],
    start="2023-01-01",
    end="2023-01-31",
    options=Options(plausibility={"range": "soft"}),  # or options={"plausibility": {"range": "soft"}}
)
values = request.filter_by_station_id("01048").values().all()
# the values a soft check kept, flagged `suspect:range`
suspect = values.df.filter(pl.col("quality_flags").str.contains(r"(^|,)suspect:"))
```

`Options(plausibility="soft")` sets every check at once (everything a source wrote, flagged), and a check named beside
it, as in the environment (`WD_TS_PLAUSIBILITY=soft` with `WD_TS_PLAUSIBILITY__RANGE=hard`), wins.

The check `limits` judges bounds of your own, per parameter, in the unit the values come back in (`unit_targets`, or the
source's unit with `convert_units=False`), beside the physical `range`:

```python
options = Options(
    limits={
        "temperature_air_mean_2m": (-30, 45),  # every dataset that serves the parameter
        "precipitation_amount": (None, 200),  # an end may be None, not both
        "daily/climate_summary/temperature_air_max_2m": (-25, 45),  # that dataset only, which wins where both name it
    },
    plausibility={"limits": "soft"},  # hard (null, `rejected:limits,raw:<number>`) is the default
)
```

A name that is no parameter, a `low` above `high`, both ends `None` and a bound that is NaN or infinite are errors
(`WD_TS_LIMITS` is the JSON of the mapping, with pairs as lists). A forecast network follows the mode of `limits` too (hard nulls, soft flags).

Interpolation and summary leave out a suspect value in any mode, and `skip_empty` counts the unflagged
values alone. [Plausibility checks](../data/plausibility.md)
describes each check, the networks and datasets it covers, the tokens with filters for them, and the caveats.

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
  `to_csv`, `to_ndjson`, `to_format`, `to_target`, `to_plot` and `to_image`; the history one has `to_dict`, `to_json`
  and `to_format`, which has JSON and no other format. They are documented below.
- **`FormattableResult` is what all of them can do**: a `typing.Protocol` of `to_dict`, `to_json` and `to_format`,
  importable from `wetterdienst.model.result`. The five results satisfy it, and so does the alerts result of
  `dwd/alerts`, without inheriting from it, so a function that writes whatever a request answered annotates its
  argument with it (`def save(result: FormattableResult) -> str | bytes`). `isinstance(result, FormattableResult)`
  tells whether an object has the three methods. A format a result does not have, such as CSV for a history, is an
  `UnknownFormatError` from its `to_format`.
- **The formats take the arguments they have, and no others.** `to_json`, `to_geojson`,
  `to_ogc_feature_collection` and `to_plot` raise a `TypeError` for a keyword they do not know, so a typo such as
  `to_geojson(with_metdata=True)` is an error, and a type checker reports it. `to_csv` and `to_image` pass their
  keywords on (`to_csv` to polars' `write_csv`, `to_image` to the image: `fmt`, `width`, `height`, `scale` and
  `max_side`). `to_format(fmt, **kwargs)` takes one set of arguments for any format and gives each format those
  it takes (CSV none), which is what the command line, the REST API and MCP rely on. A name that no format takes
  is a `TypeError` listing the ones that are, and a format it does not know an `UnknownFormatError`.
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
each format those it takes, which is what the command line, the REST API and the MCP tools do. A keyword that no
format takes is a `TypeError` too, and the formats by surface are in the table of [Export](export.md#formats-by-surface).

| Method | `StationsResult` | `ValuesResult`, `InterpolatedValuesResult`, `SummarizedValuesResult` | `HistoryResult` |
| --- | --- | --- | --- |
| `to_dict` | `with_metadata` | `with_metadata`, `with_stations` | `with_metadata`, `with_stations`, `sections` |
| `to_json` | `with_metadata`, `indent` | `with_metadata`, `with_stations`, `indent` | `with_metadata`, `with_stations`, `sections`, `indent` |
| `to_geojson` | `with_metadata`, `indent` | `with_metadata`, `indent` | none |
| `to_ogc_feature_collection` | `with_metadata` | `with_metadata` | none |
| `to_csv` | `**kwargs` of polars' `write_csv` | the same | none |
| `to_ndjson` | none | none | none |
| `to_image` | `**kwargs`: `fmt`, `width`, `height`, `scale`, `max_side` | the same | none |
| `to_plot` | none | none | none |
| `to_format` | `fmt`, `**kwargs` | the same | `fmt`, `**kwargs`: JSON only |

`indent` defaults to 4 (`True` is 4, `False` or `None` writes the JSON on one line); `with_metadata` and `with_stations` default to `False`.
`with_stations` adds a `stations` block to the values results: `df_stations`, the stations that have a row in the result, one for each resolution, dataset and station that has rows (a row of nulls is a row). A station of the request that returned no rows is not in it, nor is one whose rows `filtered_by_date` or `filtered_by_sql` cut away, and the block is an empty list where no row is left; the stations of the request are `result.stations.df`. Where the wide shape merged several datasets of a resolution into one row, which names no dataset, it has an entry for each of the datasets. In `HistoryResult` it lists the stations of the request.
`to_dict` and `to_ogc_feature_collection` return dictionaries typed as `StationsDict`, `ValuesDict`,
`InterpolatedValuesDict`, `SummarizedValuesDict` and `HistoryDict`, and the `...OgcFeatureCollection` of each, which
are importable from `wetterdienst.model.result` to annotate a function that takes or returns one. The block that
`with_metadata` adds is a `ResultMetadata`: the `provider`, the `producer`, the `processing_note` and `data_updated_at`, the date the source
states for the data (UTC, `null` where it states none, for a list of stations and for a history; a result cut down by
`filtered_by_date` or `filtered_by_sql` keeps it, and has none where no row is left). `to_target` writes to a file or a
database, see [Export](#export).

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

### Choose the rows

`filter`, `sort`, `first`, `by` and `max_rows` choose the rows of a values answer by the same words as the REST API, the MCP tool and
the command line: see [Choose the rows](restapi.md#choose-the-rows) for the grammar, the columns, what a group is and what
an empty answer means. They are keywords of the reader, `values().all(...)` and `values().query(...)`, and of one method of
the result, `selected_rows`, which does the same to a result you hold: both call one function (`RowSelection`), so they give
the same rows. They are not options of the request (`Options`): nothing in the environment can make a host filter what it
answers.

The reader applies them to each station as its values arrive, after the stations are counted for a `rank` and for
`skip_empty`, so what is held is the rows chosen and not the series read, and finishes the whole once: a group that
spans stations (`by="year"`) and the order of `sort`. `query` yields the stations one by one and so takes the options
whose groups stay in a station (a `max_rows` cuts each station's rows there, the cap of the whole is `all`'s); `by` without `station_id` is refused there with the words to use `all`. A text that cannot
be read is a `RowSelectionError` (a `RequestError`) naming the position, and a selection that cannot be applied to the
request, `value` over parameters of two units or in the wide shape, a `RowSelectionRefusedError`; both are raised before a
station is read.

`ValuesResult.search` says what was looked at, per station and parameter (`search.series`, a frame; `search.to_dict()` is
the `metadata.search` of the REST answer). It is `None` for values read without the options.

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters="daily/climate_summary/temperature_air_min_2m", start="1900", end="2026"
)
reader = request.filter_by_station_id("01975").values()

lowest = reader.all(sort="value", first=1)  # the lowest value of the station in the window, and its days
print(lowest.df)
print(lowest.search.to_dict()["totals"])  # {'series': 1, 'searched': ..., 'expected': ..., 'gaps': ..., 'matched': ...}

coldest_days = reader.all(sort="value", first=1, by="station_id,year")  # the coldest day of every year
frost = request.filter_by_station_id("01975").values().all(filter="value<=-20", sort="-timestamp")
few = reader.all(sort="value", first=1, max_rows=20)  # ties can be many rows: keep the first 20 of the answer

# the same of a result you hold already
everything = request.filter_by_station_id("01975").values().all()
lowest_again = everything.selected_rows(sort="value", first=1)
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

The filter needs DuckDB 1.5.3 or newer and refuses an older one with `UnsupportedDependencyError`. A condition is
read by the DuckDB that is installed, 1.5 or 2.0, and DuckDB 2.0 reads some conditions differently
([its migration guide](https://duckdb.org/docs/stable/operations_manual/migration)). Those that a condition on
a result meets:

- a text operator: `name ~ 'resd'` and `!~` match a part of the text on 2.0 (on 1.5 the whole text, so false for
  `Dresden`); `regexp_full_match(name, 'Dres.*')` is the 1.5 `~` on both, and `~*` (case-insensitive, a part of the
  text) exists on 2.0 only
- `NaN`: a `NaN` is greater than every number on 2.0, so `value > 20.0`, `value >= 20.0` and `NOT value <= 20.0`
  keep the rows where `value` is `NaN`, which they dropped on 1.5; add `AND NOT isnan(value)` where that matters
- `sqrt` of a negative number and `ln`, `log`, `log10` and `log2` of zero or less are an error on 1.5 and `NaN` or
  `-inf` on 2.0
- an integer divided by zero, `10 // 0`, `10 % 0`, `divide(10, 0)` and `mod(10, 0)`, is an error on 2.0 and null on
  1.5; `TRY(10 // 0)` is null on both
- the lambda arrow: `x -> x + 1` is an error on 2.0 and is written `lambda x: x + 1`, which 1.5 reads too

It is for the
library and the command line (`--sql`, `--sql-values`): the REST API and the MCP tools take no SQL. These restrictions are defence in depth, not a sandbox: never pass text from someone you do not trust to the filter. The time a condition runs, memory outside DuckDB's limit and the process itself are not protected.

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

The library has no limits on the rows or stations of a request, which the REST API and the MCP tools have. For a long
record or many stations, `stations.values().query()` and `to_target` hold one station at a time; see
[Getting more than the limit](large-requests.md#leave-the-server).

## Errors

Every class of `wetterdienst.exceptions` derives from `WetterdienstError`
(`from wetterdienst import WetterdienstError`), so one `except` catches them all. A bad argument
the library refuses with a plain `ValueError` or `KeyError` is not one of them yet. Six classes
below it say what kind of failure it is:

| Class | Raised when | Also a |
| --- | --- | --- |
| `RequestError` | the request cannot be served as phrased and can be rephrased: an invalid parameter (`InvalidParameterError`), period, date, window or point, a region the station list does not have (`UnknownRegionError`; `NoRegionsError` for a network that has none), an output format nothing renders (`UnknownFormatError`, also a `KeyError`), or a station asked for by id that exists and has none of the requested parameters (`StationLacksParametersError`, `noaa/ghcn` daily) | `ValueError` |
| `NotFoundError` | what the request names does not exist: a provider, network, resolution or dataset (`MetadataNotFoundError`), station or forecast run | `LookupError` |
| `ConfigurationError` | this installation cannot serve it: a missing credential or optional package | |
| `UpstreamError` | the provider's side failed or sent what the parser does not expect: `DownloadError` (`ProviderRateLimitError`: the provider answered 429 or the quota of the key is used up, retry later after `retry_after` seconds), `NoInternetError`, `StationListingIncompleteError` (a station is not found, and the lookup of the stations of `dwd/observation` or `dwd/derived` went without a directory it may be in; `RegionListingIncompleteError` for a region, or a list without regions, that a skipped directory may hold) | |
| `ExportRefusedError` | a sink will not perform the export, for a reason the caller can act on | |
| `ImageTimeoutError` | the browser that draws an image did not finish in `wetterdienst.io.export.IMAGE_TIMEOUT` (120) seconds, start included, and was closed with its processes | `TimeoutError` |

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
`IssueNotFoundError` a `NotFoundError` and an `IndexError` (`ProductOutOfSeasonError` is one too: a product DWD
publishes in one season only, MOSMIX-SNOW, has no run listed), `MissingDependencyError` a
`ConfigurationError` and an `ImportError`, `CredentialRejectedError` (a provider answered 401 or 403 to the
credential you configured) a `ConfigurationError` and a `PermissionError`. The REST API, the MCP tools
and the command line decide by the class what to answer: a `RequestError` is a 400 or a usage error
(exit 2), a `NotFoundError` a 404, a `ConfigurationError` a 501, a `NoInternetError` a 503, a
`ProviderRateLimitError` (a 429 of any provider or the quota of the key used up, a `DownloadError`) a 503, any other
`UpstreamError` a 502 (a 504 where a timeout was its cause), an `ImageTimeoutError` a 504 (exit 1), and anything else, an unclassified
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
