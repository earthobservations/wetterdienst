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

## The code -1 of the precipitation sums (our reading, not Frost's)

Frost writes the value `-1` into the precipitation sums of 6 hours, an hour and a day. Its descriptions of those elements
("Amount of precipitation per six hours", "Amount of precipitation per hour", "Daily precipitation sum (between 06-06
UTC)") say nothing of it; only snow depth's description documents a code ("Code=-1 means no snow"). **What
wetterdienst makes of the `-1` is our reading of the data, not a statement of Frost.** Before it, the range check took
the `-1` for a reading below 0 mm and dropped it, and a station whose 6-hourly readings were all `-1` had "no values".

| `-1` of | from 1982 | before 1982 |
|---|---|---|
| `6_hours/data/precipitation_amount` | `0.0`, a dry period | `null`: no information |
| `hourly/data/precipitation_amount` | `0.0`, a dry period | `null`: no information |
| `daily/data/precipitation_amount` | `0.0`, a dry period | `null`: no information |
| `10_minutes`, `monthly`, `annual` precipitation | not read: below the range, `null` | not read: below the range, `null` |

The code stays in `quality_flags` as the last token, after Frost's quality code (`2,raw:-1`), for the dry period and for
the null before 1982 alike. A `0` of Frost is a `0.0` and stays one. The year of the cut-off, 1982, is the year the code
becomes the mainstream of the 6-hourly series: 10 of 4,030 readings are `-1` in 1981, 4,600 of 8,655 in 1982.

### Evidence

Read from Frost on 2026-11-06 and 07, over every series Frost lists for each element (6-hourly: all 243 series; the
others: every station that has the element, in the windows named). `dry` is a holding sum (the 12-hourly sum that holds
a 6-hourly reading) that is `-1` or `0`.

| element, period | readings | `-1` | what `-1` is |
|---|---|---|---|
| 6-hourly, before 1982 | 56,976 at 68 stations | 12,873 (22.6 %) at 30 stations | no information: the holding sum is dry in 62.3 % of the cases, as for a `0` (63.7 %) and unlike a reading above 0 (0.1 %). In 1943 to 1965 it is (nearly) every reading of a station (SN39040: 1,096 of 1,096 in 1950 to 1952, and on 1951-08-05 the daily sum is 79.3 mm and the 12-hourly 67.3 mm against a 6-hourly `-1`); in 1971 to 1981 it is 0.2 to 3.2 % of the readings of a year |
| 6-hourly, 1982 to 2026-10 | 269,879 at 85 stations | 138,271 (51.2 %) at 77 stations | a dry period: the holding sum is dry in 86.3 % of the cases, for a `0` in 64.5 %, for a reading above 0 in 1.0 %. SN71550 and SN99754, the two with most readings, are 15.2 % of the readings and 14.7 % of the `-1` |
| 6-hourly, WMO stations listed since 2026-11-03 | 861 at 122 stations | 657 (76.3 %) at 118 stations | a dry period: the six hourly values it holds are all `-1` or `0` in 158 of 158, and a reading above 0 has rain in an hour and equals the sum of the hours in 18 of 18 |
| hourly, 1994 to 2024 (all 857 stations active in the fortnights of January 1994, 1999, 2004, 2009, 2014, 2019, 2024 and July 2014, 2024) | 796,636 | 250 at 15 stations, in 1994, 1999 and 2004 | a dry period, as far as it can be told: on 66 of the 78 days of those stations that hold one the daily sum is the sum of the hours with `-1` as 0, and none after 2004 |
| hourly, WMO stations listed since 2026-11-03 | 11,119 at 164 stations | 10,576 (95.1 %) at 164 stations | a dry period: a daily `-1` holds 24 hours of `-1` or `0` in 213 of 213, a daily `0` in 15 of 15, and a daily reading above 0 is the sum of its hours with `-1` as 0 in 79 of 79 |
| daily, before 1982 (1960, 1970, 1980) | 952,532 at 1,110 stations | 8,517 (0.9 %) at 23 stations | a dry period, at the stations that read by hand: the monthly sum is the sum of the days with `-1` as 0 in 91 of 96 months that hold one; the 5 others differ. It is `null` all the same, as the cut-off is the same for the three elements |
| daily, 1982 to 2026-10 (1985, 1990, 2000, 2010, 2020, 2024) | 1,997,270 at 1,447 stations | 8,815 (0.4 %) at 27 stations | a dry period: the monthly sum is the sum of the days with `-1` as 0 in 53 of 53 months that hold one; none in 2020 and 2024 |
| daily, WMO stations listed since 2026-11-03 | 958 at 232 stations | 541 (56.5 %) at 194 stations | a dry period: the two 12-hourly sums of a daily `-1` are both `-1` in 410 of 410, and the daily `0` and `>0` equal the sum of the halves in 43 of 43 and 193 of 197 |
| 10-minute, 2016, 2020, 2024 (3 days of June) | 394,188 at 515 stations | 0 | not read: there is none |
| monthly | 1,102,816 at 2,388 stations | 305 at 112 stations, all of 1884 to 1954, none since | not read: a month of a century ago that cannot be checked against days |
| annual | 70,022 at 2,255 stations | 0 | not read: there is none |

### What does not fit

The evidence is the mainstream, and these are the places where it is not. They are returned as `0.0` all the same
(1982 or later) or as `null` (before), and they are named here:

- **Since 1982, 6-hourly, station-years that look like the code of the 1940s and 1950s.** In these fewer than 70 % of
  the holding 12-hourly sums are dry (86 % is the rule) or every one of 150 or more readings is `-1`: SN18960 in 1996
  (181 of 181 readings, 59 % dry), SN94500 in 2003, SN98550 in 2003 to 2005 (51 to 60 %), SN59800 in 2004, SN69100 in
  2004 (202 of 202), SN90490 in 2004 and 2005 (154 of 154 in 2004), SN99710 in 2005 and 2006, SN28380 in 2016 and SN59610
  in 2011 and 2013 (157 of 157 and 168 of 168, 73 and 76 % dry). A `0.0` there may be a dry period or no reading.
- **Daily, SN30320 on 2015-05-01.** `-1`, with no quality code, beside 7.4 mm of hourly rain on that day and the one
  before it.
- **Daily, quality 7.** 357 of the 17,332 `-1` carry the quality code 7 ("Erroneous, value is not corrected"), 287 of them
  since 1982. For the 6-hourly `-1` this is 2 of 138,271, for the hourly 0 of 250 and of 10,576.
- **Before 1982, the daily `-1` is mostly a dry day** (91 of 96 months) and is returned as `null`: a cut-off of its own
  for the daily sum would return it. The 6-hourly `-1` of the 1970s, from a handful of stations, is `null` too.

### Checks do not see the code

The code is kept as a `raw:` token, as snow depth's is, and a reading with a `raw:` token is not judged by the checks.
So `limits={"precipitation_amount": (0.5, None)}` keeps the `0.0` of a `-1`, where a measured `0` becomes `null` with
`rejected:limits`, and a `-1` of quality 7 comes back as `7,raw:-1` without `suspect:source`. Read the token to tell
the two zeros apart.

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
