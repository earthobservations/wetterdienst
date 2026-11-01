# hourly

## metadata

| property      | value |
|---------------|-------|
| name          | hourly |
| original name | hour |

## datasets

### data

#### parameters

| name                                | original name        | description                                                                                                                        | unit |
|-------------------------------------|----------------------|------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean_temp | Mean air temperature of the hour (UTC), measured 2 m over terrain; in Greenland possibly the reading at minute 0. | °C |
| {term}`temperature_air_max_2m` | max_temp_w_date | Highest air temperature of the hour (UTC), measured 2 m over terrain. | °C |
| {term}`temperature_air_min_2m` | min_temp | Lowest air temperature of the hour (UTC), measured 2 m over terrain. | °C |
| {term}`humidity_relative_mean` | mean_relative_hum | Mean relative humidity of the hour (UTC), measured 2 m over terrain: in Denmark the average of the 6 underlying values within the hour. | % |
| {term}`pressure_air_sea_level_mean` | mean_pressure | Mean atmospheric pressure of the hour (UTC), reduced to mean sea level: in Denmark the average of the 6 underlying values within the hour. | hPa |
| {term}`precipitation_amount` | acc_precip | Accumulated precipitation of the hour (UTC), in mm. | mm |
| {term}`wind_speed_mean` | mean_wind_speed | Mean wind speed of the hour (UTC), measured 10 m over terrain: the average of the 6 underlying values within the hour. For Greenland the source says the value is not calculated correctly before 2024. | m/s |
| {term}`wind_speed_rolling_mean_max` | max_wind_speed_10min | Highest of the 6 underlying 10 minute average wind speeds within the hour (UTC), measured 10 m over terrain. | m/s |
| {term}`wind_gust_max` | max_wind_speed_3sec | Highest 3 second average wind speed (gust) of the hour (UTC), measured 10 m over terrain. | m/s |
| {term}`wind_direction_mean` | mean_wind_dir | Direction the wind blows from (north is 360, 0 means calm) over the hour (UTC), measured 10 m over terrain; in Greenland possibly the reading at minute 0. The source's 0 beside a mean wind speed of 0 (a calm wind) is null. | ° |
| {term}`sunshine_duration` | bright_sunshine | Minutes of sunshine within the hour (UTC), from the global radiation. The source says that the algorithm that calculates it has changed since week 11 of 2026. | min |
| {term}`radiation_global_intensity_mean` | mean_radiation | Mean intensity of the global radiation (305 to 2800 nm) over the hour (UTC), in W/m². The source gives the radiation of a day, month and year as a sum in MJ/m². | W/m² |
| {term}`cloud_cover_total` | mean_cloud_cover | Fraction of the sky covered by cloud of any type or height at minute 0 of the hour (UTC), in percent. The source writes the oktas as 0, 10 (1 okta or less, but not 0), 25, 40, 50, 60, 75, 90 (7 oktas or more, but not 8) and 100 (8 oktas); a value above 100, such as the 112 of its observations for an obscured sky, is null. | % |
| {term}`temperature_air_max_2m_last_12h` | max_temp_12h | Highest temperature within the last 12 hours, in °C: the highest of the 12 hourly values before the time (UTC) the value is dated by, which is the end of the 12 hours, the time of the report. Given at 06:00 and 18:00 UTC and at 12:00 and 00:00 UTC by part of the stations. | °C |
| {term}`temperature_air_min_2m_last_12h` | min_temperature_12h | Lowest temperature within the last 12 hours, in °C: the lowest of the 12 hourly values before the time (UTC) the value is dated by, which is the end of the 12 hours, the time of the report. Given at 06:00 and 18:00 UTC and at 12:00 and 00:00 UTC by part of the stations. | °C |
| {term}`precipitation_amount_last_12h` | acc_precip_past12h | Accumulated precipitation during the past 12 hours, in mm, up to the time (UTC) the value is dated by, which is the end of the 12 hours, the time of the report; given at 06:00 and 18:00 UTC. It is the gauge's own reading, not the sum of the hourly values, which differs from it by a few tenths of a millimetre. A trace, below 0.1 mm, is written -0.1 and is 0.0 here. | mm |
| {term}`precipitation_amount_last_24h` | acc_precip_past24h | Accumulated precipitation during the past 24 hours, in mm, up to the time (UTC) the value is dated by, which is the end of the 24 hours, the time of the report; given at 06:00, 12:00, 18:00 and 00:00 UTC by part of the stations. It is the gauge's own reading, not the sum of the hourly values, which differs from it by a few tenths of a millimetre. A trace, below 0.1 mm, is written -0.1 and is 0.0 here. | mm |
| {term}`temperature_soil_mean_0_1m` | temp_soil_10 | Soil temperature at a depth of 10 cm, in °C: the mean of the hour (UTC), given by part of the stations. | °C |
| {term}`temperature_air_mean_grass_height` | temp_grass | Air temperature measured at grass height (5-20 cm over terrain), in °C: the mean of the hour (UTC), given by part of the stations. | °C |
| {term}`leaf_wetness_duration` | leaf_moisture | Leaf moisture (in Danish bladfugt), in minutes: the minutes of the hour (UTC), 0 to 60, during which the leaf was wet, given by part of the stations. A few hours are outside the hour (62.0 at 06019 on 2022-05-24; -33.0 in every hour of 06041 from 2023-03-04 on). | min |
| {term}`vapor_pressure_deficit_mean` | vapour_pressure_deficit_mean | Vapour pressure deficit (in Danish mætningsdeficit), in kPa, to one decimal: the saturation vapour pressure of the hourly mean temperature, 0.611 exp(17.27 t / (t + 237.3)) above 0 °C and 0.611 exp(21.87 t / (t + 265.5)) at or below it, times (100 - the mean relative humidity) / 100. A few hours are negative (-0.3 at 06193 on 2025-07-25). | kPa |
