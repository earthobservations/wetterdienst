# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | day |

## datasets

### data

#### parameters

| name                                   | original name              | description                                                                                                                               | unit |
|----------------------------------------|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean_temp | Mean air temperature of the day: the average of all hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | °C |
| {term}`temperature_air_max_2m` | max_temp_w_date | Highest air temperature of the day: the highest of all the hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | °C |
| {term}`temperature_air_min_2m` | min_temp | Lowest air temperature of the day: the lowest of all the hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | °C |
| {term}`humidity_relative_mean` | mean_relative_hum | Mean relative humidity of the day: the average of all hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | % |
| {term}`pressure_air_sea_level_mean` | mean_pressure | Mean atmospheric pressure of the day, reduced to mean sea level: the average of all hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | hPa |
| {term}`precipitation_amount` | acc_precip | Accumulated precipitation of the day, in mm: the sum of all hourly values within the day (the local day in Denmark; in Greenland and the Faroe Islands 06:00 to 06:00 UTC, or 12:00 to 12:00 UTC at the few Greenland stations that measure it by hand). | mm |
| {term}`wind_speed_mean` | mean_wind_speed | Mean wind speed of the day: the average of all hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | m/s |
| {term}`wind_speed_rolling_mean_max` | max_wind_speed_10min | Highest 10 minute average wind speed of the day: the highest of all hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | m/s |
| {term}`wind_gust_max` | max_wind_speed_3sec | Highest 3 second average wind speed (gust) of the day: the highest of all hourly values within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | m/s |
| {term}`wind_direction_mean` | mean_wind_dir | Direction the wind blows from (north is 360, 0 means calm) over the day: the mean of components of the hourly values (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). The source's 0 beside a mean wind speed of 0 (a calm wind) is null. | ° |
| {term}`humidity_relative_max` | max_relative_hum | Highest relative humidity of the day: the highest of all hourly mean relative humidities within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | % |
| {term}`humidity_relative_min` | min_relative_hum | Lowest relative humidity of the day: the lowest of all hourly mean relative humidities within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | % |
| {term}`sunshine_duration` | bright_sunshine | Sunshine duration of the day, in hours: the sum of the hourly minutes within the day divided by 60 (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). The source says that the algorithm that calculates it has changed since week 11 of 2026. | h |
| {term}`cloud_cover_total_mean` | mean_cloud_cover | Mean cloud cover of the day, in percent: the average of the hourly values, given a day with at least 12 of them and no more than 2 missing in a row (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | % |
| {term}`snow_depth_manual` | snow_depth | Depth of the snow lying on the ground, measured by hand once a day at 07:00 UTC at the stations that do so, in cm (a day of 06:00 to 06:00 UTC, labelled by the date it begins). DMI turns the codes of its source into numbers: -1 (less than 0.5 cm) is 0.5 and -2 is 0. | cm |
| {term}`precipitation_amount_max_30min` | max_precip_30m             | Largest precipitation depth in any 30 minutes of the day, found from 23:31 local time of the previous day to 24:00 local time of the day. | mm   |
| {term}`heating_degree_day` | acc_heating_degree_days_17 | Heating degree days of the day: 17 °C minus the daily mean temperature, 0 for a mean above 17 °C. The source lists the unit as “no. of days”; the values are degrees (a mean of 2.0 °C is 15.0). | °Cd |
