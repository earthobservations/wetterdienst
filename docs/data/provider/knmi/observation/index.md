# Observation

## Overview

KNMI's [Data Platform](https://dataplatform.knmi.nl/) provides access to 10-minute,
hourly, daily, monthly and annual in-situ meteorological observations from KNMI's station network across
the Netherlands. A free API key is required; request one at
[developer.dataplatform.knmi.nl](https://developer.dataplatform.knmi.nl/).

Set the API key via the `WD_AUTH__KNMI=<api_key>` environment variable or the
`Settings(auth={"knmi": "<api_key>"})` argument.

Unlike most providers, KNMI's Data Platform has no per-station history endpoint: each
dataset file covers a single timestamp for every station in the network at once, and
there is no OPeNDAP/THREDDS/Zarr access. The only way to build a station time series is
to download one file per timestamp and extract that station's row. As a result a wide
date range translates into many individual file downloads — a 30-day hourly query is 720
downloads, and a single day at 10-minute resolution is 144 — so large sub-daily ranges
are impractical. The monthly and annual files make long ranges cheap: a file is about 80 KB and holds every
station for one month or one year, so 30 years of monthly values are 360 downloads and 30 years of annual values 30. This is a documented characteristic of KNMI's API, not a limitation of
wetterdienst.

The "validated" datasets lag real time (observed: ~1–2 days for hourly, and a month's file appears in the
first days of the next month), so only historical data is available; there is no real-time/`now` period.

The monthly and annual files are the `monthly-in-situ-meteorological-observations-validated` and
`annual-in-situ-meteorological-observations-validated` datasets (version 1.0, read with a key on 2026-11-11):
`monthly-observations-validated-YYYYMM.nc` from 190101 to 202610 (1510 files, none missing) and
`annual-observations-validated-YYYY.nc` from 1901 to 2025 (125 files, none missing). The file is named for its
period and its time coordinate is the end of it (the 1st of the next month, 1 January of the next year, 00:00 UTC,
"Time (in UTC) indicating the end of the monthly measurement interval"), so a value is stamped with the first day of
its period, as the daily values are with their date: the file of September 2026 gives the stamp 2026-09-01. A start
inside a month or a year includes it. The variables are those of the daily file, with `TG` the mean of the daily
means, `TN` and `TX` the extremes of the period, and `RH`, `DR`, `SQ` and `Q` the sums. The files of the early years
hold few of them (January 1901: the temperatures, the humidity and the sunshine of one station), and a variable a
station does not measure is missing. A file that is not published (the current month) is skipped with a warning.

Not served from the monthly and annual files, because the canonical parameters have no name for them yet:
`EV24` (the potential evapotranspiration of the period, where `evapotranspiration_potential_last_24h` is a day's),
`FHVEC` (the vector mean wind speed), `T10N` (the minimum air temperature at 10 cm), `VVN` and `VVX` (the minimum and
maximum visibility, a code from 0 to 89 and no distance), and `W1`, `W2`, `W3`, `W5` and `W6` (the number of "daily
intervals" with fog, rain, snow, thunderstorm and ice formation: they hold 0 or 1 for a whole year, so they are no count
of days, which the description does not explain).

The station list of a monthly or annual request is that of the latest file (October 2026, and 2025), so a station that
is no longer in the network (Soesterberg `06265`, Valkenburg `06210`), whose
values are in the old files, is not listed.

KNMI's NetCDF `time` coordinate marks the *end* of the measuring interval, and the three datasets
name their files differently (read from real files, GH-2824): a 10-minute file is named for that end
(`..._202610140900.nc` has the time 09:00 and covers 08:50 to 09:00), an hourly file for the start
of its hour (`...-20261014-08.nc` has the time 09:00), a daily file for its date (the time is
the next 00:00). wetterdienst stamps the 10-minute values with the file's name and the hourly values
with the name plus one hour, which is the time coordinate in both, so the air temperature of 09:00 UTC
(the "past minute" before it) is at 09:00 in both and an hourly sum is at the end of its hour; the
daily values get the date of their UTC day, matching KNMI's legacy CSV service. Before GH-2824 the
hourly values were stamped with the start of the hour.

Requests hitting a transient failure (rate limiting, dropped connections) are retried
automatically with a short backoff — a couple of retries, a few seconds each. This is
deliberately modest, not an attempt to wait out a sustained outage.

Each station's `station_id` is the WMO station number at the end of its WIGOS station identifier
(`06260` for De Bilt); the full identifier (`0-20000-0-06260`) is the station's `wigos_id`.

## License

Data is © KNMI. See the [KNMI Data Platform](https://dataplatform.knmi.nl/) for further
information and usage conditions.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
monthly.md
annual.md
```
