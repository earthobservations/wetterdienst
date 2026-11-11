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
are impractical. This is a documented characteristic of KNMI's API, not a limitation of
wetterdienst. The monthly and annual files make long ranges cheap: a file is about 80 KB and holds every station
for one month or one year, so 30 years of monthly values are 360 downloads and 30 years of annual values 30.

The "validated" datasets lag real time (observed: ~1–2 days for hourly, and a month's file appears in the
first days of the next month), so only historical data is available; there is no real-time/`now` period.

The monthly and annual files are the `monthly-in-situ-meteorological-observations-validated` and
`annual-in-situ-meteorological-observations-validated` datasets (version 1.0, read with a key on 2026-11-11):
`monthly-observations-validated-YYYYMM.nc` from 190101 to 202610 (1510 files, none missing) and
`annual-observations-validated-YYYY.nc` from 1901 to 2025 (125 files, none missing). The file is named for its period
and its time coordinate is the end of it (the 1st of the next month, 1 January of the next year, 00:00 UTC, "Time (in
UTC) indicating the end of the monthly measurement interval"), so a value is stamped with the first day of its period,
as the daily values are with their date: the file of September 2026 gives the stamp 2026-09-01. A start inside a month
or a year includes it when the request asks for that resolution alone. The variables are those of the daily file, with
`TG` the mean of the daily means, `TN` and `TX` the extremes of the period, and `RH`, `DR`, `SQ` and `Q` the sums. The
dataset pages say that "daily observations have been aggregated to monthly intervals" and that "monthly observations
have been aggregated to annual intervals", which is why `PG`, whose description reads "mean sea level pressure" and no
more, is named a mean (the daily one is "calculated as a mean of the 24 pressure values of that day"). The files of
the early years hold few of them (January 1901: the temperatures, the humidity and the sunshine of one station), and a
variable a station does not measure is missing. A period that has not ended (the running 10 minutes, hour, day, month or
year) has no file and is not asked for, with no warning. A period that has ended may still have none: the validated
hourly files are made 5.5 to 78 hours after their hour (median 25, read 2026-11-11) and the daily ones at least 4.3
hours after their day, so the latest of them are skipped with a warning, as is any file KNMI has not published.

Not served from the monthly and annual files, because the canonical parameters have no name for them yet:
`EV24` (the potential evapotranspiration of the period, where `evapotranspiration_potential_last_24h` is a day's),
`FHVEC` (the vector mean wind speed), `T10N` (the minimum air temperature at 10 cm), `VVN` and `VVX` (the minimum and
maximum visibility, a code from 0 to 89 and no distance), and `W1`, `W2`, `W3`, `W5` and `W6` (the number of "daily
intervals" with fog, rain, snow, thunderstorm and ice formation: they hold 0 or 1 for a whole year, so they are no count
of days, which the description does not explain).

## Stations

The stations are those of KNMI's own catalogue of its observation network, the dataset `waarneemstations_csv`
(version 1.0, one small CSV file for each date a station was opened, closed or moved, 77 stations in the file of
2026-06-15). The Open Data API serves it with the same key as the observations, so the list needs no second key and
costs two requests of the quota (the listing and the link of the file) whatever the resolutions asked for. The file is
kept for a week, the listing that names the newest file for 12 hours, since KNMI publishes the file weeks after the date
in its name. It replaced the station axis of the latest file of each resolution (GH-4008), which holds the stations that
reported in its interval: the latest 10-minute file held 57 stations, where those of 2024 held 69 and the files since
2012 76 of the 77, and a station that had closed was in none (Soesterberg `06265`, closed in 2008, and Valkenburg
`06210`, closed in 2016, whose values are in the files, were not listed).

- The list of a resolution is the catalogue without the stations its dataset cannot hold. The four fog stations
  (Assendelft `06233`, Muiden `06236`, Nieuw-Vennep `06237`, Nieuwkoop `06238`) are in the 10-minute files only and are
  not listed at the other resolutions (the type is compared stripped and in lower case), no annual file holds the
  Caribbean stations (WMO block 78: Saba `78871`, Sint Eustatius `78873`, Bonaire `78990`, which the hourly, daily and
  monthly files of 2026 do), and a station that closed before a dataset began (the 10-minute files start in 2012) is
  not listed for it.
- The name, the position and the height are those of the newest catalogue. A station that was moved is listed where
  it is now: Eindhoven `06370` was at 51.4497, 5.3769 and Deelen `06275` at 52.0547, 5.8722 in the files until
  June 2026, and De Bilt was "DE BILT AWS" in the files until late 2024.
- `start_timestamp` is empty. The catalogue's start date is not that of the data: Schiphol's data begins in 1951 and its
  start is 1990-07-01 (15 of the 77 stations have data before it).
- `end_timestamp` is the stop date of a station that has closed and 62 days more, and empty for one that is open. The
  stop date is no exact end of the data (Soesterberg's is in the monthly file of 2008-12, its stop date is 2008-11-15,
  and F16-A's ends before its own), hence the margin. A stations listing for a window leaves out a station closed
  before it (Soesterberg from a window in 2026), as it does for the providers that publish the end of a record. `values`
  asked for a station by its id is not cut by it.
- Where the catalogue cannot be read (it is gone, or its columns changed), the stations are read from the latest file
  of each resolution as before, with their WSI from the file's `wsi` variable.

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
