# Frost

## Overview

The Frost API provides access to historical and recent observations from the Norwegian
Meteorological Institute's station network. An API client ID is required; register for
free at [frost.met.no](https://frost.met.no/auth/requestCredentials.html).

Set the client ID via the `WD_AUTH__METNO_FROST=<client_id>` environment variable or the
`Settings(auth={"metno_frost": "<client_id>"})` argument.

## Stations

The station list is Frost's catalogue of `SensorSystem` sources, about 2,200 entries. 24 of
them have no position: Frost gives them no `geometry`, and no latitude or longitude in any other
field. They are mobile platforms, such as ships (`SN76999` SCARABEO 8, `SN77049` MS ASTERIX,
`SN20930` POLARSTERN), rigs (`SN76946` ROSS RIG) and gliders (`SN20957` SG644 GLIDER), 20 of them
with ship codes, so there is no fixed place to state. They stay in the list with a null
`latitude` and `longitude`, and a search by distance or bounding box, an interpolation or a
summary never picks them.

The list also holds about 237 foreign SYNOP stations, with ids made of `SN` and the WMO number
times 100 (`SN743400` is Limoges-Bellegarde in France, `SN623500` De Kooy in the Netherlands,
`SN848200` Malaga in Spain). Frost serves observations for them, but mostly with short, recent
series: those of Limoges and De Kooy start on 2026-10-26. They show up in `stations`, so
check the dates a station has values for before relying on a long record.

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
  `min(air_temperature P1D)` from `PT0H` to `PT18H`, which is a change of its own (below).

A date that only the 18-18 series has is not returned: it would be a sum of another window under this one's name. The
answer says so, with an `other-window-left-out` warning that names the parameter, the stations and the number of dates
left out at each (the first ten stations), in the batch, the single and the discovery reading alike, and counts only the
dates within the window asked for. It is no "the source has no values": `parameter-without-rows` does not name a
parameter, nor a dataset asked for whole, that this warning names, because the source has those values. So an answer
with fewer rows than the source holds at a station never reads as no data; see
[the response metadata](../../../../usage/restapi.md#response-metadata). `timeoffsets=default` would return the 18-18 sum
at those dates, under the name of the 06-06 one.

### What changes

Counted from the readings Frost had on 2026-11-07. Frost lists a `PT18H` series of the daily sum at 987 of its 2,334
stations (and two more that have `PT18H` only), and of the monthly sum at 964 of 2,388; the other stations have the
`PT6H` series only and nothing changes for them. The values first, at the stations and dates that have both series: the
daily sum of every station that was active in nine years (1960, 1970, 1980, 1985, 1990, 2000, 2010, 2020 and 2024, the
whole year each), and the monthly sum of every station, all years.

| sum | station-dates in the sample | with both series | the value differs | by 1 mm or more |
|---|---|---|---|---|
| daily | 2,206,547 at 2,048 stations | 744,221 (33.7 %) at 849 stations | 434,573 (58.4 % of those) at 843 stations | 270,871 |
| monthly | 922,494 at 2,388 stations | 180,958 (19.6 %) at 963 stations | 122,231 (67.5 % of those) at 959 stations | 74,073 |

Where the two differ, the median difference is 1.6 mm for the daily sum (90th percentile 9.5, largest 321.5 mm) and 1.5 mm
for the monthly sum (90th percentile 8.6, largest 317.3 mm). A series stored from the old reader holds the 18-18 sums at
those stations and does not join the new one.

#### The dates that are left out

The dates that only the 18-18 series has, which are not returned any more (and are told, as above). They are of two
kinds, and the first is counted over all years, from the listing of every time series (`availableTimeSeries`: the
stretches in which a station's `PT18H` series is valid and its `PT6H` series is not), then the readings of those
stretches:

- **Outside the validity of the `PT6H` series, all years.** Daily: 2,139 dates at 352 stations. 338 of them lose one
  date, the first of their 18-18 series (the day before their 06-06 series starts, at 334); 14 lose more, five of them
  many: SN85380 692 dates from 2015-10 to 2020-03 (315 in 2018 and 301 in 2019; its last `PT6H` date is 2015-09-01),
  SN55840 549 (1952-07 to 1953-12), SN12648 302 (2017-07 to 2018-05, a series that is still open), SN59580 128
  (1961 to 1972) and SN69570 75 (1971 to 1977), then SN28360 23 and SN27470 16. The two stations with `PT18H` only have
  one date each (SN10000 on 1998-07-21 and SN59680 on 2005-04-01). Monthly: 216 months at 181 stations, 173 of them the
  first month of the series; SN55840 18, SN85380 9 and SN94280 6 are the largest.
- **Inside the validity of the `PT6H` series, a gap of the 06-06 series.** Monthly, all years and every station: 1,076
  months at 299 stations (SN55830 85, SN76450 57, SN8850 52, SN63705 50, SN99917 24), so that the monthly sum has 1,292
  months at 392 stations that only the 18-18 series has. Daily, in the nine sampled years only: 470 dates at 163
  stations (SN93140 82, SN99990 44, SN44554 20). The daily figure is a lower bound for all years, since the other years
  were not read (the readings of both series of every station would be about 13 million), so at least 2,609 dates at
  more than 352 stations.

The largest blocks are the ones a caller notices: SN85380 from 2015-10 and SN12648 from 2017-07 to 2018-05 return 06-06
sums up to the day the 06-06 series ends and then nothing, with the warning, where they returned the 18-18 sums.

### Other elements with several series

Of the elements the provider reads, these have more than one offset at a station (series listed on 2026-11-07, stations
with both). Nothing is changed for them here:

| element | offsets | stations with both | what is returned |
|---|---|---|---|
| `mean(air_temperature P1D)` | `PT0H`, `PT6H` | 1,063 of 1,695 (7 have `PT6H` only, 1 `PT18H` only) | `PT0H`, the calendar day (00-00 UTC) the description says: it sorts first; `PT6H` or `PT18H` at the 8 stations that have no other |
| `max(air_temperature P1D)` | `PT0H`, `PT18H` | 579 of 1,133 (545 have `PT18H` only) | `PT0H` where both exist, `PT18H` where it is the only one |
| `min(air_temperature P1D)` | `PT0H`, `PT18H` | 574 of 1,161 (578 have `PT18H` only, 9 `PT6H` only) | as the maximum |
| `mean(air_temperature P1M)` | `PT0H`, `PT6H` | 1,054 of 1,316 (5 have `PT6H` only) | `PT0H`; `PT6H` at the 5 stations that have no other |

Every other element has one offset (the monthly and annual temperature extremes `PT18H`; the daily snow depth, its
monthly mean and the annual precipitation sum `PT6H`; the rest `PT0H`). The temperature extremes of a station that has both come back as the calendar day,
and those of a station that has `PT18H` only as the 19-18 UTC window, which Frost names its standard ("Standard sampling
period for temperature extremes is 19-18 UTC"). Read in 2024 at the 448 and 449 stations that have both open through
the year, the two differ on 47,342 of 157,948 days of the maximum (30.0 %, 20,122 by 1 degC or more, median 0.8, 90th
percentile 2.7, largest 16.1) and on 71,795 of 158,242 of the minimum (45.4 %, 32,422 by 1 degC or more, median 0.8, 90th
percentile 2.7, largest 15.6). The maintainer has decided that the daily maximum and minimum are the 19-18 UTC series where a station has it; that is
a change of its own, and the table above is what they return until it lands.

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
| `daily/data/precipitation_amount` | `null` | `null` | Frost states `0.0` mm. Left as it was (`rejected:range,raw:-1`) until [#3820](https://github.com/earthobservations/wetterdienst/issues/3820) has measured it: at stations that read periodically, once a week, the `-1` also marks a day that was not read |
| `10_minutes`, `monthly`, `annual` precipitation | `null` | `null` | Frost states nothing for them and none of the readings is `-1` (10-minute, annual), or none since 1954 (monthly): below the range, as before |

The code stays in `quality_flags` as the last token, after Frost's quality code (`2,raw:-1`), for the `0.0` and for the
`null` before 1982 alike, so `raw:-1` is the filter that finds every one of them. A `0` of Frost is a `0.0` and stays
one.

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
