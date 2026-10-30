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

## Incomplete months

ECCC's archive flags a monthly value `I` when the month has missing days ([Technical
Documentation](https://climate.weather.gc.ca/doc/Technical_Documentation.pdf), Notes 25 and 26: for the
extreme temperatures and the totals of rain, snow and precipitation one or more missing daily values,
for the mean temperatures more than 3 consecutive or more than 5 missing in total, beginning in 1994).
The `climate-monthly` collection publishes the value without the flag, so the library derives it, as the
plain `I` in `quality_flags`, from the days of the month and the `count_days_valid_*` of the value:

- `temperature_air_max_2m`, `temperature_air_min_2m`, `precipitation_amount` and `snow_depth_new`: `I` when
  any day of the month is not valid.
- `temperature_air_mean_minmax_2m`: `I` when more than 5 days are not valid. The "more than 3 consecutive"
  half of Note 26 needs the run of missing days, which the collection does not give, so a month of 4 or 5
  missing days in a row is not flagged here, where the archive flags it: the flag under-flags the mean.
- A value whose count of valid days is null is not flagged, and neither are the sunshine, the degree days,
  the counts and the normals, which no note names.

Which collection field is which element is our reading, not ECCC's statement: `MAX_TEMPERATURE` and
`MIN_TEMPERATURE` are the extremes of the month (elements 044 and 046), `TOTAL_PRECIPITATION` and
`TOTAL_SNOWFALL` are elements 050 and 049, `MEAN_TEMPERATURE` is 042. The flag is derived for every month,
also before 1994, where the archive set none: there it is ours and not the archive's. Ridgetown
(`4679`) 1990-03, a mean temperature from 12 days, is such a month.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
```