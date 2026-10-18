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

KNMI's NetCDF `time` coordinate marks the *end* of the measuring interval: the 10-minute file
for 23:50 to 24:00 and the hourly file for 23:00 to 24:00 carry the time 00:00 of the next day,
the daily file for 2020-01-01 carries 2020-01-02. wetterdienst stamps the 10-minute and the
hourly values with that end, so the air temperature of 12:00 UTC (the "past minute" before it) is
at 12:00 and an hourly sum is at the end of its hour, and the daily values with the date of
their UTC day, matching KNMI's legacy CSV service. Before GH-2824 the 10-minute and hourly
values were stamped with the start of the interval.

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
