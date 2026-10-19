# Observation

## Overview

Environment and Climate Change Canada (ECCC) publishes historical weather observations for the
Canadian station network at hourly, daily and monthly resolution. The network is large
and reaches back to the 19th century, though the parameters and period covered vary strongly
between stations.

Data is retrieved from the ECCC OGC API
([api.weather.gc.ca](https://api.weather.gc.ca)), with station metadata resolved from the same
service. No authentication is required. As only historical data is offered, a date range is
required when requesting values.

A station is listed for the hourly or the daily resolution only if the station list gives its hourly
(`HLY_FIRST_DATE`) or daily (`DLY_FIRST_DATE`) collection a first date, and its `start_timestamp` and
`end_timestamp` are the dates of that collection, not those of the station as a whole. The list gives
no such date for 6750 of its 8435 stations for hourly and 95 for daily. None of the 95 has a daily
row and none of 1049 of the 6750 drawn at random has an hourly one (read 2026-10-15); of the 1961
probed earlier 2 have, 4333 with no value in any column and 27490 with hourly precipitation of 2008,
which is not reached. The monthly dates of the list are null for stations that do have monthly
values, so every station is listed for monthly. The monthly `end_timestamp` is null: `MLY_LAST_DATE`
stops at 2018-02 for every station of the list while the rows run to 2026-09 (read 2026-10-19), so a
window of recent months would leave out every station that has monthly values.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
```