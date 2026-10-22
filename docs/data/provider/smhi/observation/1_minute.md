# 1_minute

Live/rolling data with no fixed historical window — SMHI only exposes a short rolling
window for 1-minute data (via the `latest-day` period), similar to a real-time
observation feed.

## metadata

| property      | value    |
|---------------|----------|
| name          | 1_minute |
| original name | 1_minute |

## datasets

### data

#### parameters

| name                           | original name | description                                                                                                                                               | unit |
|--------------------------------|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_2m`     | 45            | Air temperature at 2 m. Instantaneous value, every minute.                                                                                                | °C   |
| {term}`pressure_air_sea_level` | 44            | Air pressure reduced to sea level. Instantaneous value, every minute.                                                                                     | hPa  |
| {term}`humidity_relative`      | 43            | Relative humidity at 2 m. Instantaneous value, every minute.                                                                                              | %    |
| {term}`snow_depth`             | 52            | Snow depth. Instantaneous value, every minute.                                                                                                            | m    |
| {term}`visibility_mean`        | 51            | Visibility. One minute mean, every minute.                                                                                                                | m    |
| {term}`wind_speed_mean`        | 47            | Wind speed at 10 m. One minute mean, every minute.                                                                                                        | m/s  |
| {term}`wind_direction_mean`    | 48            | Wind direction at 10 m. One minute mean, every minute. The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays. | °    |
| {term}`precipitation_amount`   | 46            | Precipitation amount. Precipitation during one minute.                                                                                                    | mm   |
