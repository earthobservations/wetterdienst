# hourly

Real-time (observación convencional) data. Unlike `daily`/`monthly`/`annual`, this does
not accept a date range — AEMET always returns whatever rolling window of recent
observations (typically the last ~24h) it currently holds for the station.

## metadata

| property      | value        |
|---------------|--------------|
| name          | hourly       |
| original name | convencional |

## datasets

### data

#### parameters

| name                                  | original name | unit |
|---------------------------------------|---------------|------|
| {term}`temperature_air_mean_2m`       | ta            | °C   |
| {term}`temperature_air_max_2m`        | tamax         | °C   |
| {term}`temperature_air_min_2m`        | tamin         | °C   |
| {term}`temperature_dew_point_mean_2m` | tpr           | °C   |
| {term}`precipitation_height`          | prec          | mm   |
| {term}`wind_direction`                | dv            | °    |
| {term}`wind_direction_gust_max`       | dmax          | °    |
| {term}`wind_speed`                    | vv            | m/s  |
| {term}`wind_gust_max`                 | vmax          | m/s  |
| {term}`pressure_air_site`             | pres          | hPa  |
| {term}`pressure_air_sea_level`        | pres_nmar     | hPa  |
| {term}`humidity`                      | hr            | %    |
