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

| name                            | original name | description                                                           | unit |
|---------------------------------|---------------|-----------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | 45            | Air temperature. Instantaneous value, every minute.                   | °C   |
| {term}`pressure_air_sea_level`  | 44            | Air pressure reduced to sea level. Instantaneous value, every minute. | hPa  |
| {term}`humidity`                | 43            | Relative humidity. Instantaneous value, every minute.                 | %    |
| {term}`snow_depth`              | 52            | Snow depth. Instantaneous value, every minute.                        | m    |
| {term}`visibility_range`        | 51            | Visibility. One minute mean, every minute.                            | m    |
| {term}`wind_speed`              | 47            | Wind speed. One minute mean, every minute.                            | m/s  |
| {term}`wind_direction`          | 48            | Wind direction. One minute mean, every minute.                        | °    |
| {term}`precipitation_height`    | 46            | Precipitation amount. Precipitation during one minute.                | mm   |
