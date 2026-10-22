# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | daily |

## datasets

### data

#### parameters

| name                            | original name | description                                                                                                                                                                                 | unit |
|---------------------------------|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | T             | Air temperature at 2 m, the daily mean: the observations at 06:00, 13:00 and 20:00 UTC, the last counted twice, (T06 + T13 + 2 T20) / 4, not their plain average.                           | °C   |
| {term}`temperature_air_max_2m`  | TMA           | Maximum air temperature at 2 m, the source's 20:00 UTC term: the maximum of the 24 hours up to 20:00 UTC of the day it is dated. The source states no window.                               | °C   |
| {term}`temperature_air_min_2m`  | TMI           | Minimum air temperature at 2 m, the source's 20:00 UTC term: the minimum of the 24 hours up to 20:00 UTC of the day it is dated. The source states no window.                               | °C   |
| {term}`precipitation_amount`    | SRA           | Precipitation, the source's 06:00 UTC term: the total of the 24 hours from 06:00 UTC of the day it is dated to 06:00 UTC of the next day. The source states no window.                      | mm   |
| {term}`humidity_relative_mean`  | H             | Relative humidity at 2 m, the daily mean: the plain average of the observations at 06:00, 13:00 and 20:00 UTC.                                                                              | %    |
| {term}`pressure_air_site_mean`  | P             | Air pressure at station level, the daily mean: the plain average of the observations at 06:00, 13:00 and 20:00 UTC.                                                                         | hPa  |
| {term}`wind_speed_mean`         | F             | Wind speed at 10 m by convention (the source gives each series its own height: 10 m at most stations), the daily mean: the plain average of the observations at 06:00, 13:00 and 20:00 UTC. | m/s  |
| {term}`wind_speed_max`          | Fmax          | Maximum wind speed at 10 m by convention (the source gives each series its own height: 10 m at most stations) of the day it is dated. The source states no window and calls it the maximum speed, not a gust.                          | m/s  |
| {term}`snow_depth`              | SCE           | Snow depth at ground level, a reading at 06:00 UTC.                                                                                                                                         | cm   |
| {term}`sunshine_duration`       | SSV           | Sunshine duration of the day it is dated, published in hours. The source states no window.                                                                                                  | h    |
