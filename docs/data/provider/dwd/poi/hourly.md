# hourly

## metadata

| property      | value                                                        |
|---------------|--------------------------------------------------------------|
| name          | hourly                                                       |
| original name | hourly                                                       |
| url           | [here](https://opendata.dwd.de/weather/weather_reports/poi/) |

## datasets

### data

#### metadata

| property      | value                                                        |
|---------------|--------------------------------------------------------------|
| name          | data                                                         |
| original name | data                                                         |
| description   | Hourly weather reports of the last day, for the stations DWD forecasts for. |
| access        | [here](https://opendata.dwd.de/weather/weather_reports/poi/) |

#### parameters

| name                                               | original name                                                    | description                                                             | unit |
|----------------------------------------------------|------------------------------------------------------------------|-------------------------------------------------------------------------|------|
| {term}`cloud_cover_total`                          | cloud_cover_total                                                | Fraction of the sky covered by cloud of any kind.                       | %    |
| {term}`cloud_height_layer1`                        | height_of_base_of_lowest_cloud_above_station                     | Height above the station of the base of the lowest cloud.               | m    |
| {term}`evapotranspiration_last_24h`                | evaporation/evapotranspiration_last_24_hours                     | Evaporation and evapotranspiration in the preceding 24 hours.           | mm   |
| {term}`humidity`                                   | relative_humidity                                                | Relative humidity of the air.                                           | %    |
| {term}`precipitation_height_last_1h`               | precipitation_amount_last_hour                                   | Precipitation collected in the preceding hour.                          | mm   |
| {term}`precipitation_height_last_3h`               | precipitation_amount_last_3_hours                                | Precipitation collected in the preceding 3 hours.                       | mm   |
| {term}`precipitation_height_last_6h`               | precipitation_amount_last_6_hours                                | Precipitation collected in the preceding 6 hours.                       | mm   |
| {term}`precipitation_height_last_12h`              | precipitation_last_12_hours                                      | Precipitation collected in the preceding 12 hours.                      | mm   |
| {term}`precipitation_height_last_24h`              | precipitation_amount_last_24_hours                               | Precipitation collected in the preceding 24 hours.                      | mm   |
| {term}`pressure_air_sea_level`                     | pressure_reduced_to_mean_sea_level                               | Air pressure reduced to mean sea level.                                 | hPa  |
| {term}`radiation_global_intensity`                 | global_radiation_last_hour                                       | Global irradiance in the preceding hour.                                | W/m² |
| {term}`radiation_sky_short_wave_diffuse_intensity` | diffuse_solar_radiation_last_hour                                | Diffuse short-wave irradiance in the preceding hour.                    | W/m² |
| {term}`radiation_sky_short_wave_direct_intensity`  | direct_solar_radiation_last_hour                                 | Direct short-wave irradiance in the preceding hour.                     | W/m² |
| {term}`snow_depth`                                 | total_snow_depth                                                 | Depth of the snow lying on the ground.                                  | cm   |
| {term}`snow_depth_new`                             | depth_of_new_snow                                                | Depth of the snow that fell since the previous observation.             | cm   |
| {term}`sunshine_duration`                          | total_time_of_sunshine_during_last_hour                          | Length of time the sun shone in the preceding hour.                     | min  |
| {term}`sunshine_duration_yesterday`                | total_time_of_sunshine_past_day                                  | Length of time the sun shone on the previous day.                       | h    |
| {term}`temperature_air_mean_2m`                    | dry_bulb_temperature_at_2_meter_above_ground                     | Air temperature at 2 m above ground.                                    | °C   |
| {term}`temperature_air_mean_0_05m`                 | temperature_at_5_cm_above_ground                                 | Air temperature at 5 cm above ground.                                   | °C   |
| {term}`temperature_air_max_2m_last_12h`            | maximum_temperature_last_12_hours_2_meters_above_ground          | Maximum air temperature at 2 m above ground in the preceding 12 hours.  | °C   |
| {term}`temperature_air_min_2m_last_12h`            | minimum_temperature_last_12_hours_2_meters_above_ground          | Minimum air temperature at 2 m above ground in the preceding 12 hours.  | °C   |
| {term}`temperature_air_min_0_05m_last_12h`         | minimum_temperature_last_12_hours_5_cm_above_ground              | Minimum air temperature at 5 cm above ground in the preceding 12 hours. | °C   |
| {term}`temperature_air_mean_2m_yesterday`          | daily_mean_of_temperature_previous_day                           | Mean air temperature at 2 m above ground on the previous day.           | °C   |
| {term}`temperature_air_max_2m_yesterday`           | maximum_of_temperature_for_previous_day                          | Maximum air temperature at 2 m above ground on the previous day.        | °C   |
| {term}`temperature_air_min_2m_yesterday`           | minimum_of_temperature_for_previous_day                          | Minimum air temperature at 2 m above ground on the previous day.        | °C   |
| {term}`temperature_air_min_0_05m_yesterday`        | minimum_of_temperature_at_5_cm_above_ground_for_previous_day     | Minimum air temperature at 5 cm above ground on the previous day.       | °C   |
| {term}`temperature_dew_point_mean_2m`              | dew_point_temperature_at_2_meter_above_ground                    | Dew point temperature at 2 m above ground.                              | °C   |
| {term}`temperature_water`                          | sea/water_temperature                                            | Temperature of the sea or lake water at the station.                    | °C   |
| {term}`visibility_range`                           | horizontal_visibility                                            | Horizontal distance at which an object can still be made out.           | km   |
| {term}`weather`                                    | present_weather                                                  | Coded present weather at the time of observation, on DWD's 1..31 scale. | -    |
| {term}`weather_last_3h`                            | past_weather_1                                                   | Coded weather observed over the preceding 3 hours.                      | -    |
| {term}`weather_secondary_last_3h`                  | past_weather_2                                                   | Second coded weather observed over the preceding 3 hours.               | -    |
| {term}`wind_direction`                             | mean_wind_direction_during_last_10 min_at_10_meters_above_ground | Mean wind direction over the last 10 minutes, at 10 m above ground.     | °    |
| {term}`wind_speed`                                 | mean_wind_speed_during last_10_min_at_10_meters_above_ground     | Mean wind speed over the last 10 minutes, at 10 m above ground.         | km/h |
| {term}`wind_speed_rolling_mean_max`                | maximum_wind_speed_as_10_minutes_mean_during_last_hour           | Highest 10-minute mean wind speed in the preceding hour.                | km/h |
| {term}`wind_speed_rolling_mean_max_yesterday`      | maximum_of_10_minutes_mean_of_wind_speed_for_previous_day        | Highest 10-minute mean wind speed on the previous day.                  | km/h |
| {term}`wind_gust_max_last_1h`                      | maximum_wind_speed_last_hour                                     | Strongest gust in the preceding hour.                                   | km/h |
| {term}`wind_gust_max_last_6h`                      | maximum_wind_speed_during_last_6_hours                           | Strongest gust in the preceding 6 hours.                                | km/h |
| {term}`wind_gust_max_yesterday`                    | maximum_wind_speed_for_previous_day                              | Strongest gust on the previous day.                                     | km/h |
