# Observation

## Overview

KNMI's [Data Platform](https://dataplatform.knmi.nl/) provides access to 10-minute,
hourly and daily in-situ meteorological observations from KNMI's station network across
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
wetterdienst.

The "validated" datasets lag real time (observed: ~1–2 days for hourly), so only
historical data is available; there is no real-time/`now` period.

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
```
