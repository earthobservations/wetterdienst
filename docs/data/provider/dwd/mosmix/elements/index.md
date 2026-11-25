# Mosmix elements: windows and steps

What DWD's [element table](https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_elemente_xls.xlsx?__blob=publicationFile&v=3)
(`mosmix_elemente_xls.xlsx`, as of 2020-05-25) gives for each element is its unit, its window ("Total precipitation
during the last 3 hours") and the product that carries it. It does not say at which steps a window ends, how far into
the run an element goes, or what an element does late in a run. The only statement about range is the product's, on
DWD's [MOSMIX page](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html): "MOSMIX_S
(24x täglich, 40 Parameter, bis +240h), MOSMIX_L (4x täglich, ca. 115 Parameter, bis +240h)".

This page is what the files give. It was measured on 2026-11-17, key-less and read-only, on MOSMIX-L of the stations
`10382` (Berlin-Tegel), `10147` (Hamburg), `P0489` and `10961` (Zugspitze) for the runs of 2026-11-16 09 and 15 UTC and
2026-11-17 03 UTC, and on MOSMIX-S of all 5,648 stations for the run of 2026-11-17 03 UTC. The files are DWD's, so a
change of the product changes this page's truth; `tests/provider/dwd/mosmix/test_element_cadence.py` holds the table to
two trimmed runs of those files, and the table and its columns are built from the metadata when these docs are built.

## What the table says

- Every value is the window that **ends** at its timestamp (see the [time reference](../../../../time_reference.md)), so a
  value of `RR6c` at 06 UTC is the 6 hours from 00 to 06 UTC.
- Each element keeps **one cadence for the whole run** (1, 3, 6, 12 or 24 h). There is no "hourly for the first days,
  then 3-hourly" any more: every precipitation element reaches the last step of its cadence, like `TTT` and `FF`.
- The steps fall at fixed **UTC clock hours**, not at fixed distances from the run: `RR6c` is given at 00, 06, 12 and 18
  UTC, `RRhc` at 06 and 18 UTC, `RRdc` at 06 UTC. A run at 09 UTC has its first `RR6c` at 12 UTC, 3 h after the issue.
- The UTC hours of the steps are the same in every run; only the offsets change. The first step is the next of an
  element's listed UTC hours after the issue (except `WPch1` and `WPcd1`, which start later), the last the last listed
  hour within +247 h (+246 h for some hourly elements; see the table) in MOSMIX-L or +240 h in MOSMIX-S. The table gives
  both for the run of 03 UTC, as measured. A step an element is not given at is a `-` in the file (a null with `raw:-`
  in `quality_flags`, and no row by default).
- Which elements a station gets, and at which hours, depends on the station: `TX` and `TN` are at 06 and 18 UTC at
  about 70 % of the MOSMIX-S stations (run of 03 UTC: `TX` 4,022, `TN` 3,948 of 5,648); at the others at one of
  them (687 `TX` at 18 only, 766 `TN` at 06 only), at all four of 00/06/12/18 (307, 290), or at 00 or 12 UTC (166 at 12
  only for `TX`, 34 at 00 only). MOSMIX-S carries 40 of the 114 elements, and a quarter of its stations lack some
  steps of `RR1c` (see below).

```{mosmix-elements}
```

## `RR1c` and `RR3c` are zero late in the run

At most German lowland stations of the runs measured (2026-11-16/17) `RR1c` is exactly `0.0` from about +100 to +125 h
(MOSMIX-S, stations below 300 m: the last non-zero step is at +125 h or sooner at 85 % of the German stations and 39 %
of the others), and `RR3c` is often (65 % and 36 %; the median last non-zero step is +132 h). The 12 and 24 h totals
(`RRhc`, `RRdc`) and the probabilities (`R101` to `R150`, `R602`, `Rd02`) still carry rain; the 6 h total (`RR6c`) falls
to zero early at some stations (at `10147` its last non-zero step is +117 h in the run of 03 UTC of the 17th, and in
the run of 09 UTC of the 16th its 6 h sums are 0.0 on 4 of 6 late days where `RRdc` is 0.5 to 1.3 mm). The zeros
are **real values, not missing ones**, so they are returned as `0.0` and no option drops them. A forecast for the
coming days that sums or plots `precipitation_amount_significant_weather_last_1h` therefore shows the days from the
sixth on as dry where DWD's own 24 h total has rain; use
{term}`precipitation_amount_significant_weather_last_12h` or {term}`precipitation_amount_significant_weather_last_24h`
for them (and {term}`precipitation_amount_significant_weather_last_6h` where it still has rain), which are stamped at
06/18 and 06 UTC (00/06/12/18 for the 6 h total; see the table) and so do not line up with a local day.

DWD describes `RR1c` as "consistent with significant weather". That the hourly amounts are quantised to 0.1 mm, or
set to zero where the hourly weather is dry, would explain it, but DWD documents neither. The evidence, measured on
2026-11-17:

- The last step with a non-zero value, hours after the issue, run of 03 UTC, MOSMIX-L:

  | station | `RR1c` | `RR3c` | `RR6c` | `RRhc` | `RRdc` | `R101` |
  |---|---|---|---|---|---|---|
  | `10382` Berlin-Tegel | +111 | +123 | +231 | +243 | +243 | +247 |
  | `10147` Hamburg | +110 | +111 | +117 | +243 | +243 | +247 |
  | `P0489` | +110 | +228 | +243 | +243 | +243 | +247 |
  | `10961` Zugspitze | +241 | +246 | +243 | +243 | +243 | +247 |

- 24 h sums (06 to 06 UTC) of the hourly and the 6 and 12 h amounts against `RRdc`, mean of 12 station-runs: on the days
  1 to 4 `RRdc` is 8.4 to 11.0 mm and the sum of `RR1c` 98 to 103 % of it (`RR6c` and `RRhc` 100 %); on day 6 `RRdc` is
  2.38 mm and the sums are 1.68 (`RR1c`), 2.20 (`RR6c`) and 2.37 (`RRhc`); on day 8, 2.23 against 1.40, 1.92 and 2.23;
  on day 10, 3.38 against 2.42, 2.82 and 3.38.
- At `10382` (run of 09 UTC of the 16th) the days 6 to 10 have `RRdc` of 1.5, 0.9, 0.5, 1.2 and 1.3 mm, and the sum of
  `RR1c` is 0.0 mm on every one of them. Of 90 day windows with `RRdc` of at least 1 mm, 23 have a sum of `RR1c` below
  0.1 mm.
- The hourly `ww` codes of those days are 2 or 3, no precipitation.
- The mountain station `10961` is the exception: its `RR1c` carries rain to +241 h.
- MOSMIX-S has `RR1c` and `RR3c` only (no `RR6c`, `RRhc` or `RRdc`): its median last non-zero `RR1c` is +105 h over
  the stations, and it has `R602`, `Rd02` and the `Rh*` probabilities for the late days.

## MOSMIX-S: `RR1c` stops early at about a quarter of the stations

`RR1c` runs to +240 h at 4,009 of the 5,310 MOSMIX-S stations that carry it (run of 03 UTC, 2026-11-17). The other 1,301
(25 %) lack hours: every one of them the last 3 h (+238 to +240 h), about 1,260 +22 to +24 h as well, and 489 the last
9 h (+232 to +240 h) of the run. Some lack a block of every day, 97 of them the hours +4 to +9 of each day. `RRS1c` has
the same gaps as `RR1c`; `RR3c` and `RRS3c` are complete at 3,835 stations and have them at the others. A hole is a null
with `raw:-` in `quality_flags`, which is no rain: count the hours given before summing a day.

## `DRR1`, the duration of precipitation

`DRR1` (MOSMIX-L only, in seconds) is 0 for most rainy hours at `10382`: in the run of 03 UTC all of its 247 hourly
values are 0 while `RR1c` is above zero in 75 of them (in the run of 09 UTC of the 16th 10 values are above zero),
where at `10147` and `P0489` 239 and 241 of the 247 values are above zero. At the Zugspitze (`10961`) it is not given
at all: the file has a `-` at every step. With `skip_empty=True` a station whose requested parameter is given at no
step counts as having no values and is skipped, so asking for {term}`precipitation_duration` with `skip_empty=True`
drops `10961`; the default returns its nulls.

## `skip_empty` and an element that ends early

`skip_empty` measures each element against the steps **the file gives**, not against every hour (the steps at which
some station of the file has a value, GH-4093). That is what makes `TX` at 06 and 18 UTC or `RRdc` at 06 UTC a
complete element, and it is why it cannot tell that an element ends before the run does: the element's last step is
whichever step the file last gives. No file measured has an element that ends early (every element above reaches the
last step of its cadence), but the fault would pass `skip_empty`.
