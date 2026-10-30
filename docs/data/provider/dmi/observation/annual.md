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
| {term}`temperature_air_max_2m_mean` | mean_daily_max_temp | Mean of the daily maximum air temperature of the year: the average of all the underlying daily values of the highest temperature. | °C |
| {term}`temperature_air_min_2m_mean` | mean_daily_min_temp | Mean of the daily minimum air temperature of the year: the average of all the underlying daily values of the lowest temperature. | °C |
| {term}`precipitation_amount_max`    | max_precip_24h             | Largest daily precipitation total of the year, the highest of the underlying daily values.                                         | mm   |
