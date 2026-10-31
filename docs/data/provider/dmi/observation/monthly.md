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
| {term}`temperature_air_mean_2m` | mean_temp | Mean air temperature of the month: the average of all the underlying daily values. | °C |
| {term}`temperature_air_max_2m` | max_temp_w_date | Highest air temperature of the month: the highest of the underlying daily values. | °C |
| {term}`temperature_air_min_2m` | min_temp | Lowest air temperature of the month: the lowest of the underlying daily values. | °C |
| {term}`humidity_relative_mean` | mean_relative_hum | Mean relative humidity of the month: the average of the underlying daily values. | % |
| {term}`pressure_air_sea_level_mean` | mean_pressure | Mean atmospheric pressure of the month, reduced to mean sea level: the average of the underlying daily values. | hPa |
| {term}`precipitation_amount` | acc_precip | Accumulated precipitation of the month, in mm: the sum of the underlying daily values. | mm |
| {term}`wind_speed_mean` | mean_wind_speed | Mean wind speed of the month: the average of the underlying daily values. | m/s |
| {term}`wind_speed_rolling_mean_max` | max_wind_speed_10min | Highest 10 minute average wind speed of the month: the highest of the underlying daily values. | m/s |
| {term}`wind_gust_max` | max_wind_speed_3sec | Highest 3 second average wind speed (gust) of the month: the highest of the underlying daily values. | m/s |
| {term}`wind_direction_mean` | mean_wind_dir | Direction the wind blows from (north is 360, 0 means calm) over the month: the mean of components. The source's 0 beside a mean wind speed of 0 (a calm wind) is null. | ° |
| {term}`pressure_air_sea_level_max` | max_pressure | Highest atmospheric pressure of the month, reduced to mean sea level: the highest of the underlying daily values. | hPa |
| {term}`pressure_air_sea_level_min` | min_pressure | Lowest atmospheric pressure of the month, reduced to mean sea level: the lowest of the underlying daily values. | hPa |
| {term}`heating_degree_day` | acc_heating_degree_days_17 | Heating degree days of the month: the sum of the underlying daily values (the base temperature minus the daily mean temperature). The base is 17 °C in Denmark (acc_heating_degree_days_17) and 19 °C in Greenland (acc_heating_degree_days_19), which are read as this one parameter. | °Cd |
| {term}`sunshine_duration` | bright_sunshine | Sunshine duration of the month, in hours: the sum of the underlying daily values. The source says that the algorithm that calculates it has changed since week 11 of 2026. | h |
| {term}`cloud_cover_total_mean` | mean_cloud_cover | Mean cloud cover of the month, in percent: the average of the underlying daily values. | % |
| {term}`radiation_global` | mean_radiation | Global radiation (305 to 2800 nm) of the month, as the energy summed over the month: the sum of the underlying daily values, which the source publishes in MJ/m² (the library multiplies it by 1000 and returns kJ/m², converted to the unit asked for). | kJ/m² |
| {term}`pressure_vapor_mean` | mean_vapour_pressure | Mean vapour pressure of the month, in hPa: the average of the underlying daily values. | hPa |
| {term}`snow_depth_max` | max_snow_depth | Greatest snow depth of the month, in cm: the highest of the underlying daily values of snow_depth, which are read by hand once a day, with the date and the place. A value of 999.0 (24043 and 31259, September 2020) is no depth and is null. | cm |
| {term}`count_days_ice` | no_ice_days | Number of ice days of the month: the days on which the highest temperature (max_temp_w_date) was below 0 °C. | - |
| {term}`count_days_frost` | no_frost_days | Number of days with frost of the month: the days on which the lowest temperature (min_temp) was below 0 °C. | - |
| {term}`count_days_summer` | no_summer_days | Number of summer days of the month: the days on which the highest temperature (max_temp_w_date) was above 25 °C. A day at exactly 25.0 °C is no summer day here, where the canonical name counts from 25 °C. | - |
| {term}`count_days_tropical_night` | no_tropical_nights | Number of tropical nights of the month: the days on which the lowest temperature (min_temp) was above 20 °C. A day at exactly 20.0 °C is no tropical night here, where the canonical name counts from 20 °C. | - |
| {term}`count_days_precipitation_amount_ge_0_1mm` | no_days_acc_precip_01 | Number of days of the month with 0.1 mm of precipitation or more: the days on which acc_precip was 0.1 or more. | - |
| {term}`count_days_precipitation_amount_ge_1mm` | no_days_acc_precip_1 | Number of days of the month with 1 mm of precipitation or more: the days on which acc_precip was 1 or more. | - |
| {term}`count_days_precipitation_amount_ge_10mm` | no_days_acc_precip_10 | Number of days of the month with 10 mm of precipitation or more: the days on which acc_precip was 10 or more. | - |
| {term}`count_days_temperature_air_min_2m_lt_minus_10c` | no_cold_days | Number of cold days of the month: the days on which the lowest temperature (min_temp) was less than -10 °C. | - |
| {term}`count_days_wind_speed_rolling_mean_max_ge_10_8mps` | no_windy_days | Number of windy days of the month: the days on which max_wind_speed_10min, the highest 10 minute average wind speed, was greater than or equal to 10.8 m/s. The source's parameter list says mean wind speed, its calculation table (and its counts) the 10 minute maximum. | - |
| {term}`count_days_wind_speed_rolling_mean_max_ge_20_8mps` | no_stormy_days | Number of stormy days of the month: the days on which max_wind_speed_10min, the highest 10 minute average wind speed, was greater than or equal to 20.8 m/s. | - |
| {term}`count_days_wind_speed_rolling_mean_max_ge_24_5mps` | no_days_w_storm | Number of days with storm of the month: the days on which max_wind_speed_10min, the highest 10 minute average wind speed, was greater than or equal to 24.5 m/s. | - |
| {term}`count_days_wind_speed_rolling_mean_max_ge_28_5mps` | no_days_w_hurricane | Number of days with hurricane of the month: the days on which max_wind_speed_10min, the highest 10 minute average wind speed, was greater than or equal to 28.5 m/s. | - |
| {term}`count_days_snow_cover_gt_50pct` | no_days_snow_cover | Number of days with snow cover of the month: the days on which snow_depth was greater than 0 and snow_cover (the share of the ground covered, in percent) was greater than 50. Published for 2011 to 2015 only. | - |
| {term}`count_days_cloud_cover_total_mean_lt_20pct` | no_clear_days | Number of clear days of the month: the days on which mean_cloud_cover was less than 20%. | - |
| {term}`count_days_cloud_cover_total_mean_gt_80pct` | no_cloudy_days | Number of cloudy days of the month: the days on which mean_cloud_cover was greater than 80%. | - |
| {term}`temperature_air_max_2m_mean` | mean_daily_max_temp | Mean of the daily maximum air temperature of the month: the average of all the underlying daily values of the highest temperature. | °C |
| {term}`temperature_air_min_2m_mean` | mean_daily_min_temp | Mean of the daily minimum air temperature of the month: the average of all the underlying daily values of the lowest temperature. | °C |
| {term}`humidity_relative_max` | max_relative_hum | Highest relative humidity of the month: the highest of all the daily values, each the highest hourly mean relative humidity of its day. | % |
| {term}`humidity_relative_min` | min_relative_hum | Lowest relative humidity of the month: the lowest of all the daily values, each the lowest hourly mean relative humidity of its day. | % |
| {term}`precipitation_amount_max`    | max_precip_24h             | Largest daily precipitation total of the month, the highest of the underlying daily values.                                        | mm   |
