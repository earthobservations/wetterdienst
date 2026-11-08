# Frost

## Overview

The Frost API provides access to historical and recent observations from the Norwegian
Meteorological Institute's station network. An API client ID is required; register for
free at [frost.met.no](https://frost.met.no/auth/requestCredentials.html).

Set the client ID via the `WD_AUTH__METNO_FROST=<client_id>` environment variable or the
`Settings(auth={"metno_frost": "<client_id>"})` argument.

## Stations

The station list is Frost's catalogue of `SensorSystem` sources, the closed ones included: 4,179 entries on
2026-11-07, of which 2,043 have an end (Frost's own list, asked without a `validtime`, holds the 2,234 that are valid now).
Frost serves observations of a closed station, but `ids=` of one is a 404, so the catalogue is the only way to it.

52 of them have no position: Frost gives them no `geometry`, and no latitude or longitude in any other
field. They are mobile platforms, such as ships (`SN76999` SCARABEO 8, `SN77049` MS ASTERIX,
`SN20930` POLARSTERN), rigs (`SN76946` ROSS RIG) and gliders (`SN20957` SG644 GLIDER), so there is no
fixed place to state. They stay in the list with a null `latitude` and `longitude`, and a search by distance or bounding
box, an interpolation or a summary never picks them.

The list also holds about 465 stations of foreign SYNOP networks (closed ones included), with ids made of `SN` and the WMO
number times 100 (`SN743400` is Limoges-Bellegarde in France, `SN623500` De Kooy in the Netherlands, `SN848200` Malaga in
Spain). Frost serves observations for them, but mostly with short, recent series: those of Limoges and De Kooy start on
2026-10-26. They show up in `stations`, so check the dates a station has values for before relying on a long record.

Three closed stations lie outside Norway's box: Torgilsbu and Myggbukta on the coast of Greenland and Nordkappbassenget in
the Barents Sea (east of 32 E). They stay in the list with the position Frost gives.

### Start and end

The `start_timestamp` and `end_timestamp` of a station are those of its data, not Frost's `validFrom` and `validTo` of the
source, which are not: data begins before the source's `validFrom` at one station in ten (SN99700's daily precipitation
begins on 1895-07-07, the source on 1956-09-01), and the source's `validTo` is earlier than the end of the data at 1,156 of
1,868 stations. They are read from one request of Frost's list of time series, for the elements and resolutions the dataset
declares (about 71,000 series, 13 MB, which Frost takes about 30 s to answer), and kept for a week, where the list of sources
is kept for twelve hours:

- the start is the earlier of the source's `validFrom` and the earliest `validFrom` of a declared series;
- the end is the latest `validTo` of a declared series, and none if any declared series is still open (the end of the
  source is not used, so the 115 stations in service whose declared series have all ended have an end, and the 17 closed
  ones with a series that is open have none);
- a station without a declared series (344 of the 4,179) keeps the dates of its source.

The two are out of step by design: a start is history and an end changes only when a series closes, so a list of series that
is old costs a station that closed since a place in the searches of a window (it answers no data), and a station that opened
since keeps the dates of its source. The first request with an empty cache takes about 35 s (36.7 s on 2026-11-07, 30 of
them for the series), the later ones are served from the cache, which the series fill once a week: a REST API or MCP server
with the default `WD_RESTAPI_TIMEOUT` of 60 s answers the first with a 504 `request-timeout` only when Frost is slower than
that, and the work goes on, so the next request finds the cache full. An answer of Frost that is no list (a page of a proxy,
no `data`, no series) is raised as a `DownloadError` and is not kept.

If Frost does not answer that request, `stations` raises the `DownloadError` or `NoInternetError` of the failure and does
not give a list with the dates of the sources. With a window, `filter_by_name`, the `stations` command, REST endpoint and MCP tool, and a search by rank, distance or
bounding box (`filter_by_rank`, `filter_by_distance`, `filter_by_bbox`, and `values` by point or box) leave out the stations
that began after it or ended before it: the end is that of the last declared series, which Frost closes only when every one
has ended, so it does not lag a station that is still reporting. A closed station is then not counted against
`WD_RESTAPI_MAX_STATIONS` or the rows limit, and a rank does not ask Frost for it. Without a window the whole list is
searched, closed stations included, with their dates (the values of Frost need a window, so this is the listing alone); a
search by station id, name and SQL looks among the whole list (the name applies the window itself). To list the stations in
service only, keep the rows whose `end_timestamp` is null, or give the listing a `timestamp`.

### Stations that cannot be reached

58 stations that have a declared series (on 2026-11-07) are in no list of Frost's `/sources`, whatever `validtime` is
asked: no catalogue request can name them, so they are not in the station list and `values` for one of them answers
`unknown-station`.

## Time window

Every resolution needs a window, because Frost is asked for one reference time range. The REST
API, the CLI and MCP refuse a request for values without a start and end date (REST API: 400,
`timestamp` is required), and so does the Python API: `stations.values()` raises `DateRequiredError`
(a `ValueError`) naming the dataset. Pass `start` and `end` to the request. Stations can be listed
without a window.

Frost computes at most 100,000 observations per request. A window that would hold more (6-hourly precipitation of
`SN99710` from 1920 to 2026, say) is refused with a 403, the status it also gives a client ID it rejects. The reader asks
the refusal once more to read why, and raises an `InvalidTimeIntervalError` (a `ValueError`, a 400 in the REST API) that
names the estimate and says to narrow the window, where it used to say that the client ID was invalid. A 403 that does not
say so stays a `CredentialRejectedError`.

## The two series of the daily and monthly precipitation sum

Frost keeps several series of an element at a station that differ in `timeOffset` only: "Sometimes multiple timeseries are
available at the same station, with the only difference being the timeOffset value"
([data clarifications](https://frost.met.no/dataclarifications.html), "Standard time offsets"). The sums of the daily and
the monthly precipitation have two, and Frost answers both for a date when no `timeoffsets` is asked for:

| element | offset | window | Frost's table of preferred offsets |
|---|---|---|---|
| `sum(precipitation_amount P1D)` | `PT6H` | the previous date 06 UTC to the date 06 UTC | preferred: "Standard sampling period for precipitation is 07-06 UTC" |
| `sum(precipitation_amount P1D)` | `PT18H` | the previous date 18 UTC to the date 18 UTC | |
| `sum(precipitation_amount P1M)` | `PT6H` | the last day of the previous month 06 UTC to the last day of the month 06 UTC | preferred: the same words |
| `sum(precipitation_amount P1M)` | `PT18H` | the same, at 18 UTC | |

What `timeOffset` means is on [the concepts page](https://frost.met.no/concepts2.html) ("Case 2.2: Diurnal (daily)
data"): "If timeOffset != PT0H, the observation represents the last 24 hr, at the time after midnight equal to timeOffset.
E.g. elementId = sum(precipitation_amount P1D) has timeOffset PT6H. This means that the observation period lasts
continuously from the previous date at 06 UTC to current date 06 UTC." The "06-06" of the element's description and the
"07-06" of the table name the same window: the sum of the hourly stamps of `D-1` 07 to `D` 06 (a `-1` counted as 0) equals the `PT6H` value on 16 of 16 days at SN18700 (2023-08-02 to 09) and
SN50540 (2026-10-26 to 11-02), and the stamps of `D-1` 19 to `D` 18 equal the `PT18H` value on the same 16.

The reader sent no `timeoffsets`, so both rows came for each date, `PT18H` before `PT6H` (the offsets sort as text), and
the core keeps the first row of a reading. The 18-18 UTC sum was returned under a description of 06-06 (GH-3832):

| station, date | returned before | the 06-06 sum, returned now |
|---|---|---|
| SN50540, 2026-10-29 | 4.0 | 22.3 |
| SN18700, 2023-08-07 | 61.7 | 9.5 |
| SN39040, 1951-08-05 | 79.3 | 12.1 |

All three readers (the batch, the single parameter and the time series discovery) now return the rows of the `PT6H`
series alone, for the daily and the monthly sum. The choice is made on the `timeOffset` of the rows of the answer. It is
not made by asking Frost for `timeoffsets`, because the request holds every element of the dataset:

- `timeoffsets=PT6H` leaves out each element that has no `PT6H` series. At SN50540 for ten days of January 2024 the
  batch of the 12 daily elements (the request of the reader) gave 140 rows without it, and with it 30: the
  precipitation, the snow depth and the mean temperature of the `PT6H` series (not the calendar day the description
  says), and none of the other 9 elements: no maximum or minimum temperature, no wind speed, humidity or pressure;
- `timeoffsets=default` takes Frost's table for each element (100 rows there) and so also moves `max` and
  `min(air_temperature P1D)` from `PT0H` to `PT18H`, which the reader now does for those two on the rows of the
  answer, with the dates it leaves out told ([below](#the-two-series-of-the-daily-maximum-and-minimum-temperature)).

A date that only the 18-18 series has is not returned: it would be a sum of another window under this one's name. The
answer says so, with an `other-window-left-out` warning that names the parameter, the stations and the number of dates
left out at each (the first ten stations), in the batch, the single and the discovery reading alike, and counts only the
dates within the window asked for. It is no "the source has no values": `parameter-without-rows` does not name a
parameter, nor a dataset asked for whole, that this warning names, because the source has those values. So an answer
with fewer rows than the source holds at a station never reads as no data; see
[the response metadata](../../../../usage/restapi.md#response-metadata). `timeoffsets=default` would return the 18-18 sum
at those dates, under the name of the 06-06 one.

### What changes

Counted from the readings Frost had on 2026-11-07, for the stations that wetterdienst served then. Its list was Frost's
catalogue of `SensorSystem` sources valid now (`/sources`, 2,234 stations), which left out the closed ones that Frost's
time-series listing has: a station of the listing that was not in the catalogue answered `unknown-station`, with
or without this change, so nothing there reached a caller. The closed stations are listed since GH-3847; the counts below
are those of the 2,234, and the closed ones are in Frost's figures. Of the 2,334 stations that have a daily precipitation series
in Frost's listing 1,045 are in the catalogue, and of the 987 that have both series 618; of the 2,388 stations with a
monthly series 785, and of the 964 with both 612. The other stations have the `PT6H` series only (and two daily ones
`PT18H` only), and nothing changes for them. A figure that is Frost's and not the catalogue's is called so.

The values first, at the dates where both series exist: the daily sum of every catalogue station that was active in nine
years (1960, 1970, 1980, 1985, 1990, 2000, 2010, 2020 and 2024, the whole year each), and the monthly sum of every
catalogue station, all years.

| sum | station-dates | with both series | the value differs | by 1 mm or more |
|---|---|---|---|---|
| daily | 1,058,330 at 979 stations | 514,324 (48.6 %) at 569 stations | 306,101 (59.5 % of those) at 569 stations | 189,792 |
| monthly | 317,875 at 785 stations | 110,203 (34.7 %) at 612 stations | 76,703 (69.6 % of those) at 612 stations | 44,977 |

Where the two differ, the median difference is 1.6 mm for the daily sum (90th percentile 9.9, largest 321.5 mm) and 1.4 mm
for the monthly sum (90th percentile 8.6, largest 317.3 mm). A series stored from the old reader holds the 18-18 sums at
those stations and does not join the new one.

#### The dates that are left out

The dates that only the 18-18 series has are not returned any more, and are told (above). They are of two kinds, which
are counted apart because the first is complete for all years and the second is complete only for the monthly sum. The
figures are of catalogue stations.

- **Outside the validity of the `PT6H` series, all years**, from the time-series listing (the stretches in which a
  station's `PT18H` series is valid and its `PT6H` series is not) and the readings of those stretches. Daily: 1,178 dates
  at 165 stations. 158 of them lose one date, the first of their 18-18 series; 7 lose more: SN85380 692 (2015-10 to
  2020-03: 315 in 2018 and 301 in 2019; its last `PT6H` date is 2015-09-01), SN12648 302 (2017-07 to 2018-05: its 06-06
  series starts on 2018-05-03 and is still open, so the gap comes before it), SN27470 16, SN10380 3, SN57770 3, SN73550 2
  and SN94280 2. Monthly: 59 months at 43 stations, 38 of them the first month of the series, then SN85380 9, SN94280 6,
  and SN46510, SN57770 and SN90800 2 each.
- **Inside the validity of the `PT6H` series, a gap of the 06-06 series.** Monthly, all years: 591 months at 161 stations
  (SN76450 57, SN63705 50, SN99917 24, SN60500 21, SN46510 18, SN44610 14). Daily, in the nine sampled years only: 414
  dates at 131 stations (SN93140 82, SN99990 44, SN44554 20, SN29350 17, SN44610 13, SN44730 12). The other years were not
  read (both series of every catalogue station would be several million rows), so the daily figure is a lower bound.

| sum | outside the `PT6H` validity | a gap inside it | together |
|---|---|---|---|
| daily | 1,178 dates at 165 stations | at least 414 at 131 stations (nine years) | at least 1,592 dates at 271 stations |
| monthly | 59 months at 43 stations | 591 at 161 stations (all years) | 650 months at 176 stations |

The answer's warning counts both kinds, so its figure is the sum of the two for the window asked for: SN85380 is 698 for
2012 to 2020 (692 from 2015-10 and 6 gaps in 2013 and 2014), 9 for 2013 to 2015, and SN12648 is 303 for 2015 to 2022 (the
302 and 1 date on 2021-02-23).

Frost's listing has more: 2,139 days at 352 stations outside the `PT6H` validity, 961 of them at stations that are not in
the catalogue (SN55840 549 days, SN59580 128, SN69570 75, SN28360 23 and SN10000 1, 776 in all, and for the monthly sum
SN55840 18 months). A caller never had those dates, and none of them is counted above.

The two largest blocks that a caller meets: SN85380 returns 06-06 sums up to 2015-09-01 and then nothing from 2015-10 to
2020-03, with the warning, where it returned the 18-18 sums; SN12648 has nothing from 2017-07 to 2018-05-02 and its 06-06
sums from 2018-05-03 on.

## The two series of the daily maximum and minimum temperature

`max(air_temperature P1D)` and `min(air_temperature P1D)` have the same two series by `timeOffset` as the precipitation
sums, and Frost's table of preferred offsets names the one to take
([data clarifications](https://frost.met.no/dataclarifications.html), "Standard time offsets"). A series is named here
by the 24 hours it ends: the 24 hours ending 18 UTC of the date are "18-18 UTC" (`PT18H`, as for the precipitation sum
above), and the series Frost files as the calendar day is `PT0H`:

| element | offset | window | Frost's table of preferred offsets |
|---|---|---|---|
| `max(air_temperature P1D)` | `PT18H` | the 24 hours ending 18 UTC of the date: the hourly readings stamped `D-1` 19:00 to `D` 18:00 | preferred: "Standard sampling period for temperature extremes is 19-18 UTC" |
| `max(air_temperature P1D)` | `PT0H` | the series Frost files as the calendar day: the hourly readings stamped `D` 00:00 to 23:00 | |
| `min(air_temperature P1D)` | `PT18H`, `PT0H` | the same | preferred: the same words |

Frost's "19-18 UTC" names the hourly stamps 19:00 to 18:00 and so the 24 hours ending 18 UTC (19:00 to 18:00 of stamps is
not 23 hours; `PT0H` is named by its stamps only, 00:00 to 23:00, as the hours it ends are another reading of them). The concepts page says what `timeOffset` means ("If timeOffset != PT0H, the observation represents the last
24 hr, at the time after midnight equal to timeOffset"). The windows were read off the data on 2026-11-07: the maximum of
the hourly `max(air_temperature PT1H)` stamped `D-1` 19:00 to `D` 18:00 equals the `PT18H` value on 16 of 16 days at
SN18700 and at SN50540 (2026-10-20 to 11-04), and the stamps `D` 00:00 to 23:00 equal the `PT0H` value on the same 16;
the same holds for the minimum and `min(air_temperature PT1H)`. The two windows are 5 hours apart in the hourly stamps.

Frost answers both series for a date when no `timeoffsets` is asked for, `PT0H` before `PT18H` (the offsets sort as
text), and the core keeps the first row of a reading. So a station that has both returned the calendar day where its
`PT0H` series has a date, and the 18-18 window on every date that only `PT18H` has: before the `PT0H` series began (at
362 of the 550 stations of the station list that have both a maximum, and at 358 of the 545 a minimum, `PT18H` is the
older series; 1,834,176 station-days of the maximum and 2,098,007 of the minimum have `PT18H` only) and wherever `PT0H`
has a gap. The window of one parameter changed along the series of a station, and from station to station: 133 and 138
stations of the station list have `PT18H` only.

The maintainer decided on 2026-11-07 that the extremes are strict, like the precipitation sums: only `PT18H` is returned.
All three readers (the batch, the single parameter and the time series discovery) keep the rows of `PT18H` of these two
elements and leave out the others, chosen on the `timeOffset` of each row, not by `timeoffsets`. So the answer does not
depend on the window asked for, and a station without a `PT18H` series returns no extremes (Frost's listing has 9 such
stations for the maximum, with `PT0H` only, and 9 for the minimum, with `PT6H` only; none of them is in the station
list, whose 683 stations of each element all have `PT18H`: 550 with both series and 133 with `PT18H` only for the maximum,
545 and 138 for the minimum). A date that only another series has is not returned, and the answer says so with an
`other-window-left-out` warning (the same code as for the precipitation, with the dates at each station, and never
`parameter-without-rows`). SN60850 has no `PT18H` value on 2022-09-27: a request of that day returns nothing and
says so, as does one of 2022-09-20 to 09-30, which returns the dates that have it.

### What changes

Counted from the readings Frost had on 2026-11-07, for the stations of the station list as it was then (Frost's `/sources`
catalogue of the stations valid now, see above: a station of the time-series listing that was not in it answered
`unknown-station` with or without this change; the closed stations are listed since GH-3847). Frost's listing has the maximum at 1,133 stations (579 with both series, 545 with `PT18H` only, 9 with `PT0H`
only) and the minimum at 1,161 (574, 578 and 9 with `PT6H` only); the station list has 683 stations of each, **550 and
545 with both**, 133 and 138 with `PT18H` only and none without it. Their values were read in nine years (1960, 1970,
1980, 2000, 2010, 2015, 2020, 2022 and 2024, the whole year each, every station of the list that has both and is active
in it: 818,561 station-days of the maximum and 807,673 of the minimum). The overlap of the two series is recent: no
date of 1960, 1970 or 1980 has both, about 300 station-days of each have in 2000 and about 1,600 in 2010.

| | station-days | with both series | the value differs | by 1 degC or more | median, 90th percentile, largest |
|---|---|---|---|---|---|
| maximum | 818,561 at 523 stations | 605,968 (74.0 %) at 512 stations | 165,731 (27.3 % of those) at 512 stations | 66,347 | 0.7, 2.6, 19.3 degC |
| minimum | 807,673 at 518 stations | 605,939 (75.0 %) at 512 stations | 248,362 (41.0 % of those) at 512 stations | 107,832 | 0.8, 2.7, 17.4 degC |

The percentages are of the station-days that have both series, in the nine years read. In 2024 alone the maximum differs
on 29.7 % of them (50,856 of 171,403) and the minimum on 45.2 % (77,396 of 171,376). A series stored from the old reader
holds the calendar day on those dates and does not join the new one.

The dates that are not returned any more, in any window, are of two kinds, counted apart:

- **Outside the validity of the `PT18H` series, all years**, from the time-series listing and the readings of those
  stretches: the maximum has 17 dates at 17 stations and the minimum 16 at 15 (34 and 33 days are valid for `PT0H` only,
  and Frost holds no value for the others; SN27780 has 2 of the minimum, every other station 1). SN18701 has 1, 2016-01-09
  (the validity says 2016-01-09 to 12; the reading is of the first only).
- **A gap inside the validity of the `PT18H` series**, in the nine years read: the maximum 50 dates at 33 stations (48 of
  them inside the validity, 2 outside it) and the minimum 53 at 35 (52 and 1; SN60850 4 and 5, SN26840 3 and 2, the others
  2 or fewer). The other years were not read, so this is a lower bound; the 2 and 1 that lie outside the validity are the
  same dates as the first kind.

Together at least 65 dates of the maximum and 68 of the minimum are no longer returned, against 2,673,078 and
2,651,296 station-days that both series are valid for. No station of the list loses its series: all 683 have `PT18H`.
The answer's warning counts both kinds for the window asked.

## The two series of the daily and monthly mean temperature

`mean(air_temperature P1D)` and `mean(air_temperature P1M)` have two series by `timeOffset` at most stations: `PT0H`, the
calendar day (the hourly readings stamped 00:00 to 23:00) or the calendar month, and `PT6H`, the mean from 06 UTC to 06 UTC. Frost's table of standard offsets
does not list them, and says "For cases not listed above, PT0H is always the preferred offset when multiple offsets are
returned". Frost answers both, `PT0H` first, and the core kept the first row of a date: the calendar day or month wherever `PT0H` has a
date, and the 06 UTC-offset mean on a date it lacks. One parameter was in two windows, along a station's series
([#3855](https://github.com/earthobservations/wetterdienst/issues/3855)).

**Decided on 2026-11-07, as for the precipitation sums and the temperature extremes: the mean is the calendar day (or month) alone.** Only
the rows of `PT0H` are returned. A date that only `PT6H` (or `PT18H`) has is not returned in any window, and the answer says
so with an `other-window-left-out` warning, never as "the source has no values". A station that has no `PT0H` series returns no
mean (none of the station list is without it). There is no option for the old series.

Counted from the readings Frost had on 2026-11-07, for the stations of the station list as it was then (Frost's `/sources`
catalogue of the stations valid now; a station of Frost's listing that was not in it answered `unknown-station`; the closed
stations are listed since GH-3847):

| element | stations with both series | days or months that only `PT6H` has |
|---|---|---|
| `mean(air_temperature P1D)` | 609 of the 1,138 with a daily mean (Frost's listing: 1,063 of 1,695; 7 stations have `PT6H` only and 1 has `PT18H` only, none of them in the station list) | **at least 3,694 days at 11 stations** (SN25830 2,966, SN27270 603, SN92750 84, SN20301 6, SN26900 12, SN26060 10, SN73550 4, SN27316 3, SN27214 2, SN27318 2, SN67280 2): read for the stations whose `PT6H` validity goes beyond the `PT0H` one, which reproduces the figure of the issue, and 11 of the days are 2026-11-07 itself. A lower bound: the days that `PT6H` has inside the validity of `PT0H` were not read for the other 598 stations |
| `mean(air_temperature P1M)` | 605 of the 650 with a monthly mean | **901 months at 179 stations**: 97 outside the validity of `PT0H` at 14 stations (SN25830 72, SN99754 10, SN55000 4) and 804 gaps inside it at 172 (SN56420 84, SN55000 50, SN92350 32, SN27450 26, SN31680 21); 10 of them are November 2026. This is every station, all years |

The issue gave 192 months at 14 stations; the 14 stations are right and the months with a reading outside the validity of
`PT0H` are 97. The monthly count shows what the daily lower bound leaves out: 804 of the 901 months are gaps inside the
validity, so the days that only `PT6H` has are many more than 3,694. Reading the daily series of all 609 stations (about 1,300
requests of 40-year windows at 1.1 s, which Frost answers at about eight a minute) was not done.

Where both exist the values differ. Months: 101,633 of 131,739 (77 %), by 1 degC or more in 1,697; median 0.2 degC where they
differ, largest 13.3. Days at the 11 stations: 56,657 of 58,152 (97 %), 32,200 by 1 degC or more; median 1.1 degC, largest 13.6.
SN25830 on 2020-01-01: -2.2 (`PT0H`) and -3.8 (`PT6H`); on 1993-11-16 only `PT6H` has a value, -9.8, which was returned and is not now.

Every other element has one offset except the ones above (the monthly and annual temperature extremes `PT18H`; the daily snow
depth, its monthly mean and the annual precipitation sum `PT6H`; the rest `PT0H`).

## Windows that have not closed

Frost serves the value of a period that is still going on, and marks nothing: an open value has the same `qualityCode`
as a closed one (`performanceCategory` and `exposureCategory` describe the sensor and the site), and a monthly row is
always code 2. Measured on 2026-11-07
([#3856](https://github.com/earthobservations/wetterdienst/issues/3856)):

- **Daily.** Frost starts serving a date at 00:00 UTC. Five minutes before 18 UTC, `max` and `min(air_temperature P1D)`
  (`PT18H`) had a value for that date at 456 and 461 stations; by 18:15 15 % of the minima had fallen (by up to 1.9 degC)
  and 37 to 39 more stations appeared. The `PT6H` precipitation sum is not served before its date starts. The `PT0H`
  mean was served at 7 stations, and the `PT0H` pressure at 191. The humidity, the wind means and the sunshine are `PT0H`
  daily values served before the day ends as well.
- **Monthly.** The value of the current month, month to date, is served all month: the mean, the extremes and the
  precipitation at about 450 to 630 stations.

A value of an open window is partial, and as the day's maximum, minimum, sum or mean it would be wrong. **Decided on
2026-11-07: a daily value is left out, and a monthly value is returned and marked; the maintainer added the annual value
to the monthly rule as a safeguard.**

| resolution | the window of the value closes at | what is returned | what is told |
|---|---|---|---|
| daily | the date `D` + the offset: `PT18H` (the extremes) 18 UTC, `PT6H` (the precipitation sum) 06 UTC; `PT0H` (the mean, and every other daily element) the end of `D` | the value is **left out** until the window has closed | `window-not-closed`: how many values were left out, at which stations, and when the earliest window closes |
| monthly | the last day `L` of the month + the offset: `PT18H` 18 UTC of `L`, `PT6H` 06 UTC of `L`; `PT0H` (the calendar month) the end of `L` | the value is **returned** with `completeness:Incomplete` as the last token of its `quality_flags` before `raw:` (`2,completeness:Incomplete`) | `window-not-closed`: the same, and that the values are marked |
| annual | the same around 31 December: `PT18H` 18 UTC, `PT6H` 06 UTC, `PT0H` (the calendar year) the end of the year | as monthly: **returned** with `completeness:Incomplete` | as monthly |

The rule has no parameters other than the stamp, the series and the time. The stamp is the date (or the month) the value
is stamped at, and a series stamped off midnight is the date of its stamp. The series is the row's own `timeOffset`, or
the one its element names where it gives none, or `PT0H`. The time is UTC when the station is read, or when the answer was
cached if that was before (Frost's answers are kept for five minutes, and a copy made at 17:57 is not the final value of a
window that closes at 18:00): a window that closes at that time is closed. A date whose window is open is therefore left
out by every reader, and the next request after the closing time returns it.

- **A month is open until the last day.** The monthly `PT6H` sum of November runs from 06 UTC on 31 October to 06 UTC on
  30 November ("the observation period lasts continuously from the previous date at 06 UTC to current date 06 UTC", for the
  month from the last day of the previous month), so November is open until 2026-11-30 06:00 UTC, the `PT18H` maximum and
  minimum until 18:00, and the calendar-month mean and every other `PT0H` element until 2026-12-01 00:00. February closes
  on its 28th (29th in a leap year).
- **Every daily aggregate.** Not only the standard series of the decision (the `PT18H` extremes, the `PT6H` sum, the `PT0H`
  mean): every daily element but the snow depth is the aggregate of a window and has its window closed by the same rule,
  with `PT0H` the calendar day, which is what the pressure, humidity, wind and sunshine are. The daily snow depth
  (`surface_snow_thickness`) is the reading of an instant, stamped at its time, and has no window.
- **A date left out as open is told once**, as open, and not again as `other-window-left-out` for the other series.
- **Closed does not mean final.** There is no grace period: a window is closed at its closing time, and the answer is
  not held back or marked after it. Frost may publish the last readings of a window late, and corrects values in its
  normal quality control cycle (`qualityCode` 1: "controlled and corrected"), so a value of a closed window can still
  change, and it is not marked as complete: only an open window is told.
- **The annual value** follows the monthly rule as a safeguard (the maintainer's decision of 2026-11-07, after the
  measurement): the current year is returned with `completeness:Incomplete` and the `window-not-closed` warning until the
  end of 31 December (`PT0H`), or 06 UTC (`PT6H`) or 18 UTC (`PT18H`) of it. Frost did not serve the current year of the
  annual mean, maximum and precipitation sum at SN18700 and SN50540 on 2026-11-07 (the last year returned was 2025), so
  the rule had no value to mark there; other stations were not read. Frost's documentation says "ReferenceTime and
  timeOffset for annual data follow the same conventions as for seasonal and monthly data" (concepts, case 2.5), so
  the closing time is that of the monthly rule around the last day of the year.

The token `completeness` is the one the Environment Agency's hydrology readings already have (`Incomplete`: based on
incomplete data); Frost writes only `Incomplete`, never `Complete`. To keep the closed periods alone, filter
`quality_flags` for the token; to keep the current month or year out, ask for a request window that ends before it.

## The code -1 of the precipitation sums

Frost writes the value `-1` into its precipitation sums. The element descriptions do not say what it is, but the
[data clarifications](https://frost.met.no/dataclarifications.html), in "Explanations for some coded negative value
elements", do:

| element | value | converted to | meaning |
|---|---|---|---|
| `sum(precipitation_amount PT6H)` | `-1` | not converted | No precipitation |
| `sum(precipitation_amount PT12H)` | `-1` | not converted | No precipitation |
| `sum(precipitation_amount P1D)` | `-1` | 0.0 mm | No precipitation |
| `sum_over_undefined_period(precipitation_amount PT1H)` | `-1` | not converted | No precipitation |

The range check took the `-1` for a reading below 0 mm and dropped it, so a station whose 6-hourly readings were all `-1`
had "no values". What wetterdienst returns now:

| `-1` of | from 1982 | before 1982 | basis |
|---|---|---|---|
| `6_hours/data/precipitation_amount` | `0.0` | `null` | Frost states it. The year is ours: Frost states no date limit, and we depart from it on data grounds (below) |
| `hourly/data/precipitation_amount` | `0.0` | `null` | **our reading**: Frost's table does not list `sum(precipitation_amount PT1H)`, only `sum_over_undefined_period(precipitation_amount PT1H)`. Evidence below |
| `daily/data/precipitation_amount` | `0.0` | `0.0` | Frost states it ("converted to 0.0 mm"), and the value is read at every station and in every year: no cut-off year. **One exception**: SN81930 (Storstilla) up to and including 1993 is `null`, where the `-1` is a day nobody read the gauge on ([below](#the-daily--1-and-the-weekly-reader)) |
| `10_minutes`, `monthly`, `annual` precipitation | `null` | `null` | Frost states nothing for them and none of the readings is `-1` (10-minute, annual), or none since 1954 (monthly): below the range, as before |

The code stays in `quality_flags` as the last token, after Frost's quality code (`2,raw:-1`), for the `0.0` and for the
`null` before 1982 (and the `null` of the weekly reader's unread days) alike, so `raw:-1` is the filter that finds every
one of them. A `0` of Frost is a `0.0` and stays one.

Only the daily sum of the 06-06 series is decided this way for the days. The monthly sum (305 `-1`, none since 1954), the
10-minute and the annual sum, and every other element keep the `null` of the range check, as before: a `-1` of a
temperature is a temperature.

### The daily `-1` and the weekly reader

The daily sum (`sum(precipitation_amount P1D)`, the 06-06 UTC series that is returned) has `-1` on 13,869 of its 8,940,078
rows (0.16 %), measured on 2026-11-07 over every station of the station list that has a daily series and all years
([#3820](https://github.com/earthobservations/wetterdienst/issues/3820)). The 18-18 series (`PT18H`) has none in 3,598,222
rows and is not returned. Most of it is two stations and a new series:

| group | days | stations | when | what the evidence says |
|---|---:|---:|---|---|
| SN99700 Bjørnøya (radiosonde) | 11,174 | 1 | 1895-07 to 1956-12 | a dry day: 1 mm or more on 25.6 % of its days (1930-56) against 25.3 % at SN99710 beside it and 24.6 % at SN99720 Hopen |
| **SN81930 Storstilla, up to 1993** | **1,860** | **1** | **1987-12 to 1993-11** | **a day nobody read the gauge on** |
| SN81930, from 1994 | 150 | 1 | 1994-01 to 2008-05 | dry-like (neighbours 18.9 % wet) |
| the WMO series Frost lists since 2026-11-03 | 597 | 202 | 2026-11-04 to 07 | a dry day: both 12-hourly halves are `-1` in 472 of 472 days that have both |
| isolated `-1` | 88 | 39 | 2006-10 to 2018-07 | mostly dry (neighbours wet on 9.4 %); 55 are on the first of a month |

**Returned as Frost states: `0.0` with `raw:-1`, at every station and in every year**, but for SN81930 up to and including
1993. Where a `-1` has a 12-hourly half, it is as dry as a daily `0` (485 of 485 days).

**The exception.** SN81930 is a weekly reader: the median gap between its readings is 7 days (in March 1990 the days 1 to 5 and
7 to 11 are `-1` and the 6th is 31.5 mm), and the days between are `-1`. The `-1` is the filler of a day nobody read, and the week's rain sits in the next
reading. The neighbours (75 to 100 km away, 450 to 550 m lower, so a baseline and no measurement of the same sky) are wet on
48.0 % of those days, as on 49.2 % of all days of the station: the `-1` says nothing about the weather. A reading after a run
of `-1` follows the run's total of the neighbours (Spearman 0.63) and not the day's (0.28). Those days are `null` with
`raw:-1`, and have no row by default. From 1994 the station writes rows on its reading day only and its few `-1` are
dry-like, and `0.0`.

**The rule that finds such a station.** In a calendar year, a median gap of 4 days or more between the readings and at least
half of the rows `-1`. It selects exactly SN81930 for 1987 to 1993 (7 station-years, 1,860 `-1`) of every station and year,
and nothing else. A live test holds it: `test_metno_frost_the_weekly_reader_rule_finds_storstilla_and_no_other_station_of_its_controls`
reads SN81930 and four stations that could be taken for it (SN99700, SN17150, SN30320, SN53101) through the reader, and the
years the rule finds must be the ones the reader names. A weekly reader at a station not among them is found by the census,
not by that test. The 58 stations with a median gap of 4 days or more in some year (monthly readers, mostly) write no `-1` but SN81930
and SN30320 (8 days, 2013 to 2016).

**Not covered.** The census names these so that they are not found again as a surprise: SN17150 Rygge 2006-10-08 has rain
beside it, and the first-of-the-month `-1` (on 2015-05-01 five stations of 498 have one, among them SN30320) look like an
artefact of the month boundary of the source. They are 0.06 % and 0.4 % of the `-1` and are `0.0`. The WMO series is four
days old: it is worth looking at again when it is a month old.

**Several rows for one day.** Four of the WMO stations (SN644700, SN1447400, SN647600, SN645100) write several rows for a
date, stamped at different times. On 2026-11-07 SN644700 has eight rows of `-1` (00:00 to 08:00) and five of `0.1` (10:00
to 16:00); of the 16 station-days of 2026-11-04 to 07 three have a `-1` beside a reading (that one, SN644700 on
2026-11-04, and SN647600 on 2026-11-04, a `0`). The core keeps the first row of a day that has a value, so a `-1` read as `0.0` would win over a reading that
is stamped later: the reader leaves out the `-1` rows of a day that another of its rows has a reading for.

**What it does to a caller.** `drop_nulls=False` keeps the unread days of Storstilla; the default drops them. A `0.0` that
carries `raw:-1` is no null to `drop_nulls` and is not judged by the checks (a code of the source), as the 6-hourly one
is ([below](#checks-do-not-see-the-code)). Bjørnøya's daily precipitation
of 1895 to 1956 had about half of its days dropped, and has them as `0.0` now. A series stored from the old reader holds
`null` (`rejected:range,raw:-1`) for every `-1`: read it anew, and filter on `raw:-1` to find the former nulls.

### Why `null` before 1982

Frost states no date limit for the 6-hourly `-1`. The data do. The share of `-1` among the 6-hourly readings is 0.2 %
in 1981 (10 of 4,030) and 53 % in 1982 (4,600 of 8,655), and what it is differs on the two sides. `dry` is the 12-hourly
sum that holds a 6-hourly reading (the one stamped six hours after the readings of 00 and 12 UTC) being `-1` or `0`; the
baseline is the share of dry 12-hourly sums of the station-year the `-1` is in, over both stamp hours (over the stamp
hour of the holding sums alone it is 54.9 % from 1982 and 60.5 % before).

- **From 1982:** the sum that holds a `-1` is dry in 86.4 % of the cases against a baseline of 57.0 %, and for a reading
  above 0 in 0.8 %. For 77.0 % of the `-1` the holding sum is itself `-1`, the code Frost states for the 12-hourly sum.
  The comparator is a measured `0`: dry in 64.4 % of the cases (baseline 55.6 %).
- **1920 to 1959:** 11,600 `-1` have a holding sum, dry in 61.6 % against a baseline of 60.4 %: no more than chance. In
  the 1940s and 1950s the `-1` is every reading of a station, wet days included (SN39040: 1,096 of 1,096 in 1950 to
  1952; on 1951-08-05 the 12-hourly sum that holds the 12 UTC reading is 67.3 mm and the daily sum of the 18-18 series
  is 79.3 mm, against a 6-hourly `-1`). A `0.0` there would write a dry period into a wet day.
- **1960 to 1981:** 891 `-1` have a holding sum, dry in 70.6 % against a baseline of 49.1 %, and a measured `0` in 63.2 %
  against 51.3 %. This is not "no information": the `-1` leans dry here, as a `0` does. It is 0.2 to 3.2 % of the
  readings of a year, from a handful of stations.
- **Why the cut stays at 1982 all the same:** the share of `-1` goes from 0.2 to 53 %, the median lift of a station-year
  (the dry share of its holding sums over its baseline, with 30 or more `-1`) is 1.9 points before 1982 and 31.1 from
  1982, and a null, a gap where there was a dry period, is the safe side of a `0.0` where there was none.

### Evidence

Read from Frost on 2026-11-06 and 07. 6-hourly: every one of the 243 series Frost lists; the others: every station that
has the element, in the windows named.

| element, period | readings | `-1` | what it is |
|---|---|---|---|
| 6-hourly, before 1982 | 56,976 at 68 stations | 12,873 (22.6 %) at 30 stations | 1920 to 1959: dry 61.6 % against 60.4 %, chance; 1960 to 1981: 70.6 % against 49.1 % (891 with a holding sum), 0.2 to 3.2 % of the readings of a year; pooled 62.3 % against 59.6 % |
| 6-hourly, 1982 to 2026-10 | 269,879 at 85 stations | 138,271 (51.2 %) at 77 stations | no precipitation: dry 86.4 % against 57.0 %. SN71550 and SN99754, the two with most readings, are 15.2 % of the readings and 14.7 % of the `-1`. The 1.4 % of the readings at 06 and 18 UTC have no 12-hourly sum that holds them and are left out of the shares |
| 6-hourly, WMO stations listed since 2026-11-03 | 861 at 122 stations | 657 (76.3 %) at 118 stations | no precipitation: the six hourly values it holds are `-1` or `0` in 158 of 158, and a reading above 0 has rain in an hour and equals the sum of the hours in 18 of 18 |
| hourly, 1994 to 2024 (all 857 stations active in the fortnights of January 1994, 1999, 2004, 2009, 2014, 2019, 2024 and July 2014, 2024) | 796,636 | 250 at 15 stations, in 1994, 1999 and 2004 only | the weak part: of the 78 days of those stations that hold one, none has all 24 hours, and 66 agree with the daily sum with `-1` as 0 |
| hourly, WMO stations listed since 2026-11-03 | 11,119 at 164 stations | 10,576 (95.1 %) at 164 stations | the strong part: a daily `-1` holds 24 hours of `-1` or `0` in 213 of 213, a daily `0` in 15 of 15, and a daily reading above 0 is the sum of its hours with `-1` as 0 in 79 of 79 |
| 10-minute, 2016, 2020, 2024 (3 days of June) | 394,188 at 515 stations | 0 | not read |
| monthly | 1,102,816 at 2,388 stations | 305 at 112 stations, all of 1884 to 1954 | not read |
| annual | 70,022 at 2,255 stations | 0 | not read |

### What does not fit

The evidence is the mainstream, and these are the places where it is not. They are returned as `0.0` all the same (the
6-hourly ones, from 1982 on), and named here:

- **6-hourly, station-years since 1982 whose `-1` tell little.** In these the holding 12-hourly sums are dry less than 10
  points more often than the station-year's own are (the rule is 29 points), at a station-year whose own sums are dry
  less than 85 % of the time (above that a lift cannot show), or every one of 150 or more readings is `-1`: SN18960 in
  1996 (181 of 181 readings, 59 % against 58 %), SN94500 in 2003, SN98550 in 2003 to 2005, SN4780 in 2004 (273 `-1`, 72 %
  against 81 %), SN59800 in 2004, SN6020 in 2004, SN69100 in 2004 (202 of 202), SN90490 in 2004 and 2005 (154 of 154 in
  2004), SN96400 in 2004 and SN59610 in 2011 and 2013 (157 of 157 and 168 of 168, 73 and 76 % against 33 and 39 %). The
  rule is applied to a station-year with at least 30 `-1` and 30 holding sums. A `0.0` there may be no precipitation or
  no reading.
- **6-hourly, `-1` that could not be checked.** 5,422 of the `-1` at 00 and 12 UTC since 1982 (3.9 % of the 138,271) have
  no holding 12-hourly sum: SN99950 3,483, SN99754 969, SN42160 741. And 19 station-years with 150 or more `-1` have
  fewer than 30 holding sums, so the test above cannot see them: SN99950 in 2009 to 2021 (13 of them), SN42160 in 2002 to
  2004, SN99754 in 2010 and 2011 and SN99990 in 2020. They are returned as `0.0` all the same.
- **Quality 7** ("Erroneous, value is not corrected"): 2 of the 138,271 6-hourly `-1` carry it, none of the hourly ones.

### Checks do not see the code

The code is kept as a `raw:` token, as snow depth's is, and a reading with a `raw:` token is not judged by the checks:

- `limits={"precipitation_amount": (0.5, None)}` keeps the `0.0` of a `-1`, where a measured `0` becomes `null` with
  `rejected:limits`.
- A `-1` of quality 7 comes back as `7,raw:-1` at `0.0`, where a measured reading of quality 7 is `7,suspect:source` (or
  `null` with `7,rejected:source,raw:0.5` under `plausibility={"source": "hard"}`; the decoded `0.0` stays under both).
  `leave_out_suspect`, which interpolation, summaries, stripes and `skip_empty` apply, nulls the measured one and keeps
  the decoded `0.0`.

Read the `raw:-1` token to tell the two zeros apart.

## The other coded values

Frost's [data clarifications](https://frost.met.no/dataclarifications.html) list every value of this kind in "Explanations
for some coded negative value elements": "Some elements can use negative observation values that are coded to mean a
certain thing - and are not an actual value for a measurement. Product time series also exist where these special values
are converted to a measurement value." The precipitation rows are above; these are the others, for the elements
wetterdienst reads. Read from Frost on 2026-11-06 (GH-3137), the numbers are readings, not stations unless said.

| element | value | Frost: converted, meaning | returned | read |
|---|---|---|---|---|
| `wind_from_direction` (`wind_direction_mean_last_10min`) | `-3` | not converted: "No unique wind direction is given when winds are weak" | `null`, `raw:-3`. The range check took it for a bearing below 0: it was `null`, `rejected:range,raw:-3` with `plausibility={"range": "hard"}`, and with `soft` the value `-3.0`, `suspect:range` | 72 of 9,255 hourly readings at 12 of the 249 foreign WMO stations with wind readings (22 October to 5 November 2026), all beside a speed of 0.5 to 2.6 m/s; none in 108,161 readings at 328 stations in 10 to 24 January 2026 |
| `cloud_area_fraction` (`cloud_cover_total`) | `-3` | not converted: "Cloud cover is not estimated because of fog or analogous phenomena" | `null`, `raw:-3` | none in 572,955 hourly readings at the 5 Norwegian stations with an open series of the element (2008 to 2025) or in 8,743 at the foreign ones |
| `cloud_area_fraction` | `9` | the description of the element: "Code -3 or 9 = cloud cover can not be estimated because the sky is obstructed from view" | `null`, `raw:9` | 19,669 of the 572,955 and 35 of the 8,743 |
| `surface_snow_thickness` (`snow_depth`) | `0` | not converted: "Snowdepth less than 0.5 cm" | `0.0`, no token | 32,879 of 75,143 daily readings at 25 of 40 stations asked, which returned readings (2000 to 2025) |
| `surface_snow_thickness` | `-1` | not converted: "Zero snowdepth or partial snow cover" (the description of the element: "Code=-1 means no snow") | `0.0`, `raw:-1` | 6,397 of the 75,143 daily readings, 3,005 of 33,991 hourly readings at 105 stations (10 to 24 January 2026); against the daily snow cover below |
| `surface_snow_thickness` | `-3` | not converted: "Not possible to measure snowdepth" | `null`, `raw:-3` (it was `-3.0` cm: the range of the parameter allows it) | none in about 150,000 readings (daily and hourly, Norwegian and foreign stations) |

The snow depth `-1` is read as a depth of zero, as before. Beside the daily `snow_coverage_type` of the same station and
day (`0` or `-1` no snow, `1` mostly snow-free ground, `2` equal parts, `3` mostly covered, `4` completely covered; 16
stations, 2015-10 to 2016-06), a `-1` has a cover of `1` to `4` on 11.2 % of its 954 days from November to April (107
days) and on 1.6 % of its 888 days from May to October, and a `0` on 8.7 % of its 196 days from November to April
(overall 6.6 % of 1,842 days for the `-1`, 8.4 % of 474 for the `0`; by the definition above a `0` is no snow in 91.6 %).
A depth of 5 cm or more is mostly or completely covered on 97.4 % of 1,161 days. This is one winter at 16 stations.
Frost's words for the `-1` are "zero snowdepth or partial snow cover"; the sample shows the cover classes beside it and
does not say what the code stands for on those days. A caller who needs the cover of the station area reads
`snow_coverage_type`, which wetterdienst does not serve. Negative depths that the table does not list are returned as
they are: a `-2` at SN91500 on 2017-07-24 (daily, quality `2`), the only one in the 75,143 daily readings, and 12 hourly
values of -0.29 to -0.01 at SN18700 on 2016-08-04 and 05 (quality `0`).

The `0` of the wind direction is not in Frost's table, but the element's own text says "360 degrees is north", and 360
exists (276 foreign and 463 Norwegian readings, about twice the neighbouring degrees). At the foreign stations the `0`
stands beside a speed of 0 in 359 of 372 readings. At the 20 Norwegian stations with most zeros in 10 to 24 January 2026
(chosen for them, so the first figure is not a share of all) it does so in 1,014 of 1,068, and 1,014 of the 1,030
readings of a speed of 0 have a direction of 0. So Frost writes a calm as 0, and a `0` beside a speed of 0 of the same
time and height is a calm: `null` with `raw:0`, as for the providers listed for the calm in
[Special values](../../../special_values.md#wind). A `0` beside a speed above 0 stays `0.0` (54 of the 1,068 zeros
of the Norwegian sample are not beside a speed of 0, and may be north), and so does a `0` read without its speed, which
happens only when Frost answers the request for the whole dataset with a 404 and each parameter is asked for by itself.
A station may measure the wind at several heights (71 have had a speed at more than one, and 32 a direction; 7 have a direction at two heights now): a direction
is held against the speed of its own height, and with none there it stays. At the 7 stations that have a direction at two
heights a calm or a `-3` of the first height, the 10 m one, is the answer for the hour and the other height does not
fill it ([the hourly page](hourly.md) says what the answer keeps, and the counts). The `0` was returned as `0.0` before
(GH-3833).

The rows of Frost's table for elements that are not read here (`low_type_cloud_area_fraction`, `cloud_area_fraction1`
and `cloud_base_height` `-3`; `max` and `min(surface_snow_thickness P1M)` `-1`; `snow_coverage_type` `-1`, its monthly
`min` and `max` `-1`; `state_of_ground` `-1`; `sum(precipitation_amount PT12H)` `-1`; `max(sum(precipitation_amount P1D)
P1M)`, `sum(precipitation_amount P30D)` and `sum_until_day_of_year(precipitation_amount P1D)` `-1` as 0.0 mm) are not
reachable, since no parameter names them. The monthly and annual means (`mean(surface_snow_thickness P1M)`,
`mean(cloud_area_fraction P1M)` and `P1Y`) leave the codes out of the mean: no mean was below 0 in 1,162 monthly snow
depths and 11 monthly cloud covers read.

## The source's own verdict (`source`)

Every value carries Frost's `qualityCode` as the plain flag of `quality_flags`. The check `source` reads the one code that
Frost's [data clarifications](https://frost.met.no/dataclarifications.html#quality-code) word as a verdict: `7`,
"Erroneous, value is not corrected". The page says "Frost tries to give the user a single value to represent the general
quality of the observation. This value is set in the field qualityCode", and lists `0` "OK, value is controlled and found
O.K.", `1` "OK, value is controlled and corrected, or value is missing and interpolated", `2` "Slightly uncertain, value
is not controlled", `4` "Slightly uncertain, value is not corrected", `5` "Very uncertain, value is not corrected" and
`6` "Very uncertain, model data. Value is controlled and corrected, or value is missing and is interpolated - automatic".
Those are a degree of confidence, a treatment or a model, no verdict, and are not read. Frost needs a client id, so this
mapping rests on the documentation and was not probed live.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the
default is `soft`, which keeps the value and writes `suspect:source`, so interpolation, summaries and climate stripes leave it
out. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

## License

Data is © Norwegian Meteorological Institute (MET Norway). See
[license terms](https://www.met.no/en/free-meteorological-data/Licensing-and-crediting).

```{toctree}
:hidden:

10_minutes.md
hourly.md
6_hours.md
daily.md
monthly.md
annual.md
```
