# annual

## metadata

| property      | value |
|---------------|-------|
| name          | annual |
| original name | year |

## datasets

### data

#### parameters

| name                                | original name              | description                                                                                                                        | unit |
|-------------------------------------|----------------------------|------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean_temp | Mean air temperature of the year: the average of all the underlying daily values. | °C |
| {term}`temperature_air_max_2m` | max_temp_w_date | Highest air temperature of the year: the highest of the underlying daily values. | °C |
| {term}`temperature_air_min_2m` | min_temp | Lowest air temperature of the year: the lowest of the underlying daily values. | °C |
| {term}`humidity_relative_mean` | mean_relative_hum | Mean relative humidity of the year: the average of the underlying daily values. | % |
| {term}`pressure_air_sea_level_mean` | mean_pressure | Mean atmospheric pressure of the year, reduced to mean sea level: the average of the underlying daily values. | hPa |
| {term}`precipitation_amount` | acc_precip | Accumulated precipitation of the year, in mm: the sum of the underlying daily values. | mm |
| {term}`wind_speed_mean` | mean_wind_speed | Mean wind speed of the year: the average of the underlying daily values. | m/s |
| {term}`wind_speed_rolling_mean_max` | max_wind_speed_10min | Highest 10 minute average wind speed of the year: the highest of the underlying daily values. | m/s |
| {term}`wind_gust_max` | max_wind_speed_3sec | Highest 3 second average wind speed (gust) of the year: the highest of the underlying daily values. | m/s |
| {term}`wind_direction_mean` | mean_wind_dir | Direction the wind blows from (north is 360, 0 means calm) over the year: the mean of components. The source's 0 beside a mean wind speed of 0 (a calm wind) is null. | ° |
| {term}`heating_degree_day` | acc_heating_degree_days_17 | Heating degree days of the year: the sum of the underlying daily values (17 °C minus the daily mean temperature). | °Cd |
| {term}`sunshine_duration` | bright_sunshine | Sunshine duration of the year, in hours: the sum of the underlying daily values. The source says that the algorithm that calculates it has changed since week 11 of 2026. | h |
| {term}`cloud_cover_total_mean` | mean_cloud_cover | Mean cloud cover of the year, in percent: the average of the underlying daily values. | % |
| {term}`count_days_ice` | no_ice_days | Number of ice days of the year: the days on which the highest temperature (max_temp_w_date) was below 0 °C. | - |
| {term}`count_days_frost` | no_frost_days | Number of days with frost of the year: the days on which the lowest temperature (min_temp) was below 0 °C. | - |
| {term}`count_days_precipitation_amount_ge_0_1mm` | no_days_acc_precip_01 | Number of days of the year with 0.1 mm of precipitation or more: the days on which acc_precip was 0.1 or more. | - |
| {term}`count_days_precipitation_amount_ge_1mm` | no_days_acc_precip_1 | Number of days of the year with 1 mm of precipitation or more: the days on which acc_precip was 1 or more. | - |
| {term}`count_days_precipitation_amount_ge_10mm` | no_days_acc_precip_10 | Number of days of the year with 10 mm of precipitation or more: the days on which acc_precip was 10 or more. | - |
| {term}`temperature_air_max_2m_mean` | mean_daily_max_temp | Mean of the daily maximum air temperature of the year: the average of all the underlying daily values of the highest temperature. | °C |
| {term}`temperature_air_min_2m_mean` | mean_daily_min_temp | Mean of the daily minimum air temperature of the year: the average of all the underlying daily values of the lowest temperature. | °C |
| {term}`humidity_relative_max` | max_relative_hum | Highest relative humidity of the year: the highest of all the daily values, each the highest hourly mean relative humidity of its day. | % |
| {term}`humidity_relative_min` | min_relative_hum | Lowest relative humidity of the year: the lowest of all the daily values, each the lowest hourly mean relative humidity of its day. | % |
| {term}`precipitation_amount_max`    | max_precip_24h             | Largest daily precipitation total of the year, the highest of the underlying daily values.                                         | mm   |
