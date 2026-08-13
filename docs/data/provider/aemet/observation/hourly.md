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

| name                                  | original name | description                                                                                                                                                  | unit |
|---------------------------------------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m`       | ta            | Instantaneous air temperature at the time given by 'fint' (degrees Celsius).                                                                                 | °C   |
| {term}`temperature_air_max_2m`        | tamax         | Maximum air temperature, the highest of the 60 instantaneous 'ta' values measured in the 60 minutes preceding the observation time 'fint' (degrees Celsius). | °C   |
| {term}`temperature_air_min_2m`        | tamin         | Minimum air temperature, the lowest of the 60 instantaneous 'ta' values measured in the 60 minutes preceding the observation time 'fint' (degrees Celsius).  | °C   |
| {term}`temperature_dew_point_mean_2m` | tpr           | Calculated dew point temperature at the time given by 'fint' (degrees Celsius).                                                                              | °C   |
| {term}`precipitation_height`          | prec          | Accumulated precipitation measured by the rain gauge during the 60 minutes preceding the observation time 'fint' (mm, equivalent to l/m2).                   | mm   |
| {term}`wind_direction`                | dv            | Mean wind direction over the 10 minutes preceding the time given by 'fint' (degrees).                                                                        | °    |
| {term}`wind_direction_gust_max`       | dmax          | Direction of the maximum wind recorded in the 60 minutes preceding the time given by 'fint' (degrees).                                                       | °    |
| {term}`wind_speed`                    | vv            | Mean wind speed, the scalar mean of the samples taken every 0.25 or 1 second over the 10 minutes preceding 'fint' (m/s).                                     | m/s  |
| {term}`wind_gust_max`                 | vmax          | Maximum wind speed, the highest wind sustained for 3 seconds recorded in the 60 minutes preceding the observation time 'fint' (m/s).                         | m/s  |
| {term}`pressure_air_site`             | pres          | Instantaneous pressure at the level where the barometer is installed, at the time given by 'fint' (hPa).                                                     | hPa  |
| {term}`pressure_air_sea_level`        | pres_nmar     | Pressure reduced to sea level, for stations at an altitude of 750 metres or less, at the time given by 'fint' (hPa).                                         | hPa  |
| {term}`humidity`                      | hr            | Instantaneous relative humidity of the air at the time given by 'fint' (%).                                                                                  | %    |
