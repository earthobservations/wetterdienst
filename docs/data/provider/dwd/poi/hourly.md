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

| name                                               | original name                                                    | description                                                                                                                                                                                                                                                          | unit |
|----------------------------------------------------|------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`cloud_cover_total` | cloud_cover_total | Fraction of the sky covered by cloud of any kind, where the source states no statistic or a reading at one moment; the stated mean is `cloud_cover_total_mean`. | % |
| {term}`cloud_height_layer1` | height_of_base_of_lowest_cloud_above_station | Height above the station of the base of the lowest cloud. | m |
| {term}`evapotranspiration_last_24h` | evaporation/evapotranspiration_last_24_hours | Evaporation and evapotranspiration in the preceding 24 hours (DWD: "Evaporation (vergangene 24 Stunden)"), reported almost only at 06 UTC. | mm |
| {term}`humidity_relative` | relative_humidity | Relative humidity of the air. | % |
| {term}`precipitation_amount_last_1h` | precipitation_amount_last_hour | Precipitation collected in the preceding hour. | mm |
| {term}`precipitation_amount_last_3h` | precipitation_amount_last_3_hours | Precipitation collected in the preceding 3 hours, reported at the eight synoptic hours (00, 03, ... 21 UTC). | mm |
| {term}`precipitation_amount_last_6h` | precipitation_amount_last_6_hours | Precipitation collected in the preceding 6 hours, reported at 00, 06, 12 and 18 UTC. | mm |
| {term}`precipitation_amount_last_12h` | precipitation_last_12_hours | Precipitation collected in the preceding 12 hours, reported mostly at 06 and 18 UTC. | mm |
| {term}`precipitation_amount_last_24h` | precipitation_amount_last_24_hours | Precipitation collected in the preceding 24 hours, reported mostly at 06 UTC. | mm |
| {term}`pressure_air_sea_level` | pressure_reduced_to_mean_sea_level | Air pressure reduced to mean sea level. | hPa |
| {term}`radiation_global_intensity` | global_radiation_last_hour | Global irradiance of the preceding hour in W/m2 (DWD: "Globalstrahlung (letzte Stunde)"): the energy of that hour divided by 3600 s, not a reading at one moment. | W/m² |
| {term}`radiation_sky_short_wave_diffuse_intensity` | diffuse_solar_radiation_last_hour | Diffuse short-wave irradiance of the preceding hour in W/m2 (DWD: "Diffuse Strahlung (letzte Stunde)"): the energy of that hour divided by 3600 s, not a reading at one moment. | W/m² |
| {term}`radiation_sky_short_wave_direct_intensity` | direct_solar_radiation_last_hour | Direct short-wave irradiance of the preceding hour in W/m2 (DWD: "Direkte Strahlung (letzte Stunde)", no surface stated). It exceeds the global irradiance in some reports, so it is not the component on a horizontal surface. | W/m² |
| {term}`snow_depth` | total_snow_depth | Depth of the snow lying on the ground, where the source states no statistic or a reading at one moment; the stated mean is `snow_depth_mean`, the sum of the daily depths `snow_depth_sum`. | cm |
| {term}`snow_depth_new` | depth_of_new_snow | Depth of new snow (DWD: "Neuschneehoehe"). The file states no period; it is reported in the 06 UTC report only. | cm |
| {term}`sunshine_duration` | total_time_of_sunshine_during_last_hour | Length of time the sun shone in the preceding hour, in minutes; it agrees with the sum of DWD's 10-minute sunshine duration of that hour. | min |
| {term}`sunshine_duration_yesterday` | total_time_of_sunshine_past_day | Length of time the sun shone on the previous day (UTC at DWD's stations, checked at 06 UTC), in hours; stations outside Germany also report it at 00 or 03 UTC, with no day stated. | h |
| {term}`temperature_air_2m` | dry_bulb_temperature_at_2_meter_above_ground | Air temperature at 2 m above ground. | °C |
| {term}`temperature_air_0_05m` | temperature_at_5_cm_above_ground | Air temperature at 5 cm above ground. | °C |
| {term}`temperature_air_max_2m_last_12h` | maximum_temperature_last_12_hours_2_meters_above_ground | Maximum air temperature at 2 m above ground in the preceding 12 hours, reported mostly at 06 and 18 UTC. | °C |
| {term}`temperature_air_min_2m_last_12h` | minimum_temperature_last_12_hours_2_meters_above_ground | Minimum air temperature at 2 m above ground in the preceding 12 hours, reported mostly at 06, 09 and 18 UTC. | °C |
| {term}`temperature_air_min_0_05m_last_12h` | minimum_temperature_last_12_hours_5_cm_above_ground | Minimum air temperature at 5 cm above ground in the preceding 12 hours, reported mostly at 06, 09 and 18 UTC. | °C |
| {term}`temperature_air_mean_2m_yesterday` | daily_mean_of_temperature_previous_day | Mean air temperature at 2 m above ground on the previous day (UTC), reported at 06 UTC.          | °C |
| {term}`temperature_air_max_2m_yesterday` | maximum_of_temperature_for_previous_day | Maximum air temperature at 2 m above ground on the previous day (UTC), reported at 06 UTC.          | °C |
| {term}`temperature_air_min_2m_yesterday` | minimum_of_temperature_for_previous_day | Minimum air temperature at 2 m above ground on the previous day (UTC), reported at 06 UTC.          | °C |
| {term}`temperature_air_min_0_05m_yesterday` | minimum_of_temperature_at_5_cm_above_ground_for_previous_day | Minimum air temperature at 5 cm above ground on the previous day (UTC), reported at 06 UTC.          | °C |
| {term}`temperature_dew_point_2m` | dew_point_temperature_at_2_meter_above_ground | Dew point temperature at 2 m above ground. | °C |
| {term}`temperature_water` | sea/water_temperature | Temperature of the sea or lake water at the station. | °C |
| {term}`visibility` | horizontal_visibility | Horizontal distance at which an object can still be made out, where the source states no statistic or a reading at one moment; the stated mean is `visibility_mean`. | km |
| {term}`weather` | present_weather | Coded present weather at the time of observation, on DWD's 1..31 scale. | - |
| {term}`weather_past` | past_weather_1 | Coded past weather of a synoptic report (DWD: "vergangenes Wetter 1"). The values, 0 to 18, fit BUFR 0 20 004: 0 to 9 of WMO code table 4561 for a manned station, 10 to 19 (WMO code table 4531 plus 10) for an automatic one. Reported at the eight synoptic hours. DWD states no period; the WMO's is the 6 hours before the reports of 00, 06, 12 and 18 UTC and the 3 hours before those of 03, 09, 15 and 21 UTC. | - |
| {term}`weather_secondary_past` | past_weather_2 | Second coded past weather of a synoptic report (DWD: "vergangenes Wetter 2"; BUFR 0 20 005, coded as `past_weather_1`), reported at the eight synoptic hours. DWD states no period either (the WMO's, as for `past_weather_1`).                                      | - |
| {term}`wind_direction_mean_last_10min` | mean_wind_direction_during_last_10 min_at_10_meters_above_ground | Mean wind direction over the last 10 minutes, at 10 m above ground. The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays. | ° |
| {term}`wind_speed_mean_last_10min` | mean_wind_speed_during last_10_min_at_10_meters_above_ground | Mean wind speed over the last 10 minutes, at 10 m above ground. | km/h |
| {term}`wind_speed_rolling_mean_max` | maximum_wind_speed_as_10_minutes_mean_during_last_hour | Highest 10-minute mean wind speed in the preceding hour. | km/h |
| {term}`wind_speed_rolling_mean_max_last_6h` | maximum_of_10_minutes_mean_of_wind_speed_for_previous_day | Highest 10-minute mean wind speed in the 6 hours up to the stamp. DWD names the column "previous day", but it is carried at 00, 06, 12 and 18 UTC and is the maximum of the 6 hourly values up to the stamp. | km/h |
| {term}`wind_gust_max_last_1h` | maximum_wind_speed_last_hour | Strongest gust in the preceding hour. | km/h |
| {term}`wind_gust_max_last_6h` | maximum_wind_speed_during_last_6_hours | Strongest gust in the preceding 6 hours, reported at 00, 06, 12 and 18 UTC. | km/h |
| {term}`wind_gust_max_yesterday` | maximum_wind_speed_for_previous_day | Strongest gust on the previous day (UTC), reported at 06 UTC.          | km/h |
