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
baseline is the share of dry 12-hourly sums of the station-year the `-1` is in.

- **From 1982:** the sum that holds a `-1` is dry in 86.4 % of the cases against a baseline of 57.0 %, and for a reading
  above 0 in 0.8 %. For 77.0 % of the `-1` the holding sum is itself `-1`, the code Frost states for the 12-hourly sum.
- **Before 1982:** 62.3 % against a baseline of 59.6 %: no more than chance. In the 1940s and 1950s the `-1` is every
  reading of a station, wet days included (SN39040: 1,096 of 1,096 in 1950 to 1952, and on 1951-08-05 the daily sum is
  79.3 mm and the 12-hourly sum 67.3 mm against a 6-hourly `-1`). A `0.0` there would write a dry period into a wet day.

### Evidence

Read from Frost on 2026-11-06 and 07. 6-hourly: every one of the 243 series Frost lists; the others: every station that
has the element, in the windows named.

| element, period | readings | `-1` | what it is |
|---|---|---|---|
| 6-hourly, before 1982 | 56,976 at 68 stations | 12,873 (22.6 %) at 30 stations | no information: dry 62.3 % against 59.6 %; in 1971 to 1981 it is 0.2 to 3.2 % of the readings of a year |
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
  points more often than the station-year's own are (the rule is 29 points), at a station-year that is not dry
  anyway, or every one of 150 or more readings is `-1`: SN18960 in 1996 (181 of 181 readings, 59 % against 58 %), SN94500
  in 2003, SN98550 in 2003 to 2005, SN4780 in 2004 (273 `-1`, 72 % against 81 %), SN59800 in 2004, SN6020 in 2004,
  SN69100 in 2004 (202 of 202), SN90490 in 2004 and 2005 (154 of 154 in 2004), SN96400 in 2004 and SN59610 in 2011 and
  2013 (157 of 157 and 168 of 168, 73 and 76 % against 33 and 39 %). A `0.0` there may be no precipitation or no
  reading.
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
