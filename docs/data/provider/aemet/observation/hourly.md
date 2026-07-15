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

| name                          | original name | unit type     | unit |
|--------------------------------|---------------|----------------|------|
| temperature_air_mean_2m        | ta            | temperature    | °C   |
| temperature_air_max_2m         | tamax         | temperature    | °C   |
| temperature_air_min_2m         | tamin         | temperature    | °C   |
| temperature_dew_point_mean_2m  | tpr           | temperature    | °C   |
| precipitation_height           | prec          | precipitation  | mm   |
| wind_direction                 | dv            | angle          | °    |
| wind_direction_gust_max        | dmax          | angle          | °    |
| wind_speed                     | vv            | speed          | m/s  |
| wind_gust_max                  | vmax          | speed          | m/s  |
| pressure_air_site               | pres          | pressure       | hPa  |
| pressure_air_sea_level          | pres_nmar     | pressure       | hPa  |
| humidity                       | hr            | fraction       | %    |
