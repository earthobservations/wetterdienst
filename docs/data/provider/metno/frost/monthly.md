# monthly

## metadata

| property      | value   |
|---------------|---------|
| name          | monthly |
| original name | P1M     |

## datasets

### data

#### parameters

| name                                  | original name                       | description                                                                                                                                                                                                     | unit |
|---------------------------------------|-------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean(air_temperature P1M) | Monthly mean temperature. The mean is an arithmetic mean of daily values. | degree_celsius |
| {term}`temperature_air_max_2m` | max(air_temperature P1M) | Highest recorded air temperature per month | degree_celsius |
| {term}`temperature_air_min_2m` | min(air_temperature P1M) | Lowest recorded air temperature per month | degree_celsius |
| {term}`temperature_dew_point_mean_2m` | mean(dew_point_temperature P1M) | Monthly mean dew-point temperature. Dew-point temperature is the temperature at which the air, when cooled, will become saturated (and dew is formed). | degree_celsius |
| {term}`precipitation_height` | sum(precipitation_amount P1M) | Monthly precipitation sum. | millimeter |
| {term}`wind_speed` | mean(wind_speed P1M) | Monthly mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`wind_speed_rolling_mean_max` | max(wind_speed P1M) | Monthly maximum mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`humidity` | mean(relative_humidity P1M) | Monthly mean relative humidity. | percent |
| {term}`pressure_air_sea_level` | mean(air_pressure_at_sea_level P1M) | Monthly mean air pressure reduced to sea level. The parameter is usually called QFF in aviation and shows the measured air pressure reduced to mean sea level by applying actual atmospheric conditions. | hectopascal |
| {term}`pressure_air_site` | mean(surface_air_pressure P1M) | Monthly mean air pressure at the station. The parameter is usually called QFE in aviation and shows the measured air pressure reduced to the reference height of the station. | hectopascal |
| {term}`cloud_cover_total` | mean(cloud_area_fraction P1M) | Monthly mean cloud cover. The mean is an arithmetic mean of three daily observations (06, 12 and 18 UTC). | one_eighth |
| {term}`snow_depth` | mean(surface_snow_thickness P1M) | Monthly mean snow depth. The mean value is an arithmetic mean of daily values. | centimeter |
| {term}`sunshine_duration` | sum(duration_of_sunshine P1M) | Number of hours of sunshine over the last month. | second |
