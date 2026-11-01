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
| {term}`pressure_air_sea_level_max` | max_pressure | Highest atmospheric pressure of the day, reduced to mean sea level: the highest hourly value of mean_pressure within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). Published for some stations only. | hPa |
| {term}`pressure_air_sea_level_min` | min_pressure | Lowest atmospheric pressure of the day, reduced to mean sea level: the lowest hourly value of mean_pressure within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). Published for some stations only. | hPa |
| {term}`humidity_relative_max` | max_relative_hum | Highest relative humidity of the day: the highest of all hourly mean relative humidities within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | % |
| {term}`humidity_relative_min` | min_relative_hum | Lowest relative humidity of the day: the lowest of all hourly mean relative humidities within the day (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | % |
| {term}`sunshine_duration` | bright_sunshine | Sunshine duration of the day, in hours: the sum of the hourly minutes within the day divided by 60 (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). The source says that the algorithm that calculates it has changed since week 11 of 2026. | h |
| {term}`cloud_cover_total_mean` | mean_cloud_cover | Mean cloud cover of the day, in percent: the average of the hourly values, given a day with at least 12 of them and no more than 2 missing in a row (the local day in Denmark; 06:00 to 06:00 UTC in Greenland and the Faroe Islands). | % |
| {term}`radiation_global` | mean_radiation | Global radiation (305 to 2800 nm) of the day, as the energy summed over the day: the sum of the underlying hourly values, which the source publishes in MJ/m² (the library multiplies it by 1000 and returns kJ/m², converted to the unit asked for). Published for some stations only. | kJ/m² |
| {term}`pressure_vapor_mean` | mean_vapour_pressure | Mean vapour pressure of the day, in hPa: the mean of the hourly values that could be calculated from the hourly mean temperature and mean relative humidity. The source marks some values 0.0 with validity false. | hPa |
| {term}`temperature_soil_mean_0_1m` | temp_soil_10 | Soil temperature at a depth of 10 cm, in °C: the average of the hourly values within the day. | °C |
| {term}`temperature_air_mean_grass_height` | temp_grass | Air temperature measured at grass height (5-20 cm over terrain), in °C: the average of the hourly values within the day. Not quality controlled by DMI's climatologists, so data can be erroneous. | °C |
| {term}`temperature_soil_mean_0_3m` | temp_soil_30 | Soil temperature at a depth of 30 cm, in °C: the average of the hourly values within the day. Not quality controlled by DMI's climatologists, so data can be erroneous. | °C |
| {term}`leaf_wetness_duration` | leaf_moisture | Leaf moisture (in Danish bladfugt), in minutes: the minutes of the day, 0 to 1440, during which the leaf was wet. The source says the day is the average of the hourly values, but the values are their sum (1332.0 at 06135 on 2025-06-10, which no mean of minutes could be). Not quality controlled by DMI's climatologists, so data can be erroneous. Some days are outside the day (for example 1442.0 at 06019 on 2022-05-24 and -799.0 at 06041 on 2023-03-05). | min |
| {term}`vapor_pressure_deficit_mean` | vapour_pressure_deficit_mean | Vapour pressure deficit (in Danish mætningsdeficit), in kPa, to one decimal: the average of the hourly values within the day, each the saturation vapour pressure of the hourly mean temperature, 0.611 exp(17.27 t / (t + 237.3)) above 0 °C and 0.611 exp(21.87 t / (t + 265.5)) at or below it, times (100 - the mean relative humidity) / 100. Not quality controlled by DMI's climatologists, so data can be erroneous. Some days are slightly negative (for example -0.1 at 06169 on 2024-12-26). | kPa |
| {term}`snow_cover` | snow_cover | Snow cover, the share of the ground covered by snow, in percent: observed by hand once a day and "derived directly, but codes are changed to %" (a day of 06:00 to 06:00 UTC, labelled by the date it begins). Published from 2011-01-01 to 2015-11-21 only, for 91 stations. | % |
| {term}`count_days_cloud_cover_total_mean_lt_20pct` | no_clear_days | Clear day: 1 if the mean cloud cover (mean_cloud_cover) of the day was less than 20%, 0 if it was 20% or more. | - |
| {term}`count_days_cloud_cover_total_mean_gt_80pct` | no_cloudy_days | Cloudy day: 1 if the mean cloud cover (mean_cloud_cover) of the day was greater than 80%, 0 if it was 80% or less. | - |
| {term}`snow_depth_manual` | snow_depth | Depth of the snow lying on the ground, measured by hand once a day at 07:00 UTC at the stations that do so, in cm (a day of 06:00 to 06:00 UTC, labelled by the date it begins). DMI turns the codes of its source into numbers: -1 (less than 0.5 cm) is 0.5 and -2 is 0. | cm |
| {term}`precipitation_amount_max_30min` | max_precip_30m             | Largest precipitation depth in any 30 minutes of the day, found from 23:31 local time of the previous day to 24:00 local time of the day. | mm   |
| {term}`heating_degree_day` | acc_heating_degree_days_17 | Heating degree days of the day: the base temperature minus the daily mean temperature, 0 for a mean above the base. The base is 17 °C in Denmark (acc_heating_degree_days_17) and 19 °C in Greenland (acc_heating_degree_days_19), which are read as this one parameter. The source lists the unit as “no. of days”; the values are degrees (a mean of 2.0 °C is 15.0 in Denmark). | °Cd |
