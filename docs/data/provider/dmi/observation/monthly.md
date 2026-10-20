# monthly

## metadata

| property      | value |
|---------------|-------|
| name          | monthly |
| original name | month |

## datasets

### data

#### parameters

| name                                | original name              | description                                                                                                                        | unit |
|-------------------------------------|----------------------------|------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m`     | mean_temp                  | Mean air temperature at 2 m above ground.                                                                                          | °C   |
| {term}`temperature_air_max_2m`      | max_temp_w_date            | Maximum air temperature at 2 m above ground.                                                                                       | °C   |
| {term}`temperature_air_min_2m`      | min_temp                   | Minimum air temperature at 2 m above ground.                                                                                       | °C   |
| {term}`humidity_relative_mean`      | mean_relative_hum          | Mean relative humidity of the air over the period, the fraction of the moisture it could hold at that temperature.                 | %    |
| {term}`pressure_air_sea_level_mean` | mean_pressure              | Mean air pressure reduced to mean sea level over the period, so that stations at different heights compare.                        | hPa  |
| {term}`precipitation_amount`        | acc_precip                 | Depth of precipitation collected over the period.                                                                                  | mm   |
| {term}`wind_speed_mean`             | mean_wind_speed            | Mean speed of the wind over the period.                                                                                            | m/s  |
| {term}`wind_speed_rolling_mean_max` | max_wind_speed_10min       | Highest rolling mean wind speed over the period.                                                                                   | m/s  |
| {term}`wind_gust_max`               | max_wind_speed_3sec        | Speed of the strongest gust of the period.                                                                                         | m/s  |
| {term}`wind_direction_mean`         | mean_wind_dir              | Direction the wind is blowing from, clockwise from true north. The source's 0 beside a mean wind speed of 0 (a calm wind) is null. | °    |
| {term}`heating_degree_day`          | acc_heating_degree_days_17 | Heating degree days, the temperature shortfall below a base value summed over each day.                                            | °Cd  |
| {term}`temperature_air_max_2m_mean` | mean_daily_max_temp        | Mean of the daily maximum air temperature at 2 m above ground over the period.                                                     | °C   |
| {term}`temperature_air_min_2m_mean` | mean_daily_min_temp        | Mean of the daily minimum air temperature at 2 m above ground over the period.                                                     | °C   |
| {term}`humidity_relative_max`       | max_relative_hum           | Highest relative humidity over the period.                                                                                         | %    |
| {term}`humidity_relative_min`       | min_relative_hum           | Lowest relative humidity over the period.                                                                                          | %    |
| {term}`precipitation_amount_max`    | max_precip_24h             | Largest daily precipitation total of the month, the highest of the underlying daily values.                                        | mm   |
