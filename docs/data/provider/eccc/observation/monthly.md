# monthly

## metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | monthly                                                                                                                                                                            |
| original name | mly                                                                                                                                                                                |
| url           | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

## datasets

### data

#### metadata

| property    | value                                                                                                                                                                                                                                      |
|-------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name        | data                                                                                                                                                                                                                                       |
| original    | data                                                                                                                                                                                                                                       |
| description   | Historical monthly station observations for Canada |
| access      | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0)                                                         |

#### parameters

| name                            | original name           | description                | unit | constraints |
|---------------------------------|-------------------------|----------------------------|------|-------------|
| {term}`sunshine_duration` | bright_sunshine | Bright sunshine duration of the month, in hours. The source lists it by name and gives no more. | h | >=0 |
| {term}`cooling_degree_day` | cooling_degree_days | Cooling degree-days of the month: the sum of the daily values (the degrees Celsius that the mean temperature is above 18 °C). Published even when days are missing; `days_with_valid_mean_temp` counts the days behind it. | °Cd | >=0 |
| {term}`heating_degree_day` | heating_degree_days | Heating degree-days of the month: the sum of the daily values (the degrees Celsius that the mean temperature is below 18 °C). Published even when days are missing; `days_with_valid_mean_temp` counts the days behind it. | °Cd | >=0 |
| {term}`temperature_air_max_2m` | max_temperature | Highest daily maximum air temperature of the month (the source's extreme maximum). The source states no height; the 2 m of the name is the convention. A month with a missing day reads `I` in `quality_flags`, which wetterdienst derives from `days_with_valid_max_temp`. | °C | - |
| {term}`temperature_air_mean_minmax_2m` | mean_temperature | Mean air temperature of the month: the mean of the daily mean temperatures. Published even when days are missing; `days_with_valid_mean_temp` counts the days behind it. A month of more than 5 missing days reads `I` in `quality_flags`, which wetterdienst derives from that count. | °C | - |
| {term}`temperature_air_min_2m` | min_temperature | Lowest daily minimum air temperature of the month (the source's extreme minimum). The source states no height; the 2 m of the name is the convention. A month with a missing day reads `I` in `quality_flags`, which wetterdienst derives from `days_with_valid_min_temp`. | °C | - |
| {term}`snow_depth` | snow_on_ground_last_day | Depth of snow on the ground in cm on the last day of the month: "the monthly value displayed is for the final day of the month". | cm | >=0 |
| {term}`precipitation_amount` | total_precipitation | Total precipitation of the month: the sum of the daily totals (rainfall plus the water equivalent of the snowfall), in mm. Published even when days are missing; `days_with_valid_precip` counts the days behind it. A month with a missing day reads `I` in `quality_flags`, which wetterdienst derives from that count. | mm | >=0 |
| {term}`snow_depth_new` | total_snowfall | Total snowfall of the month: the sum of the daily snowfalls, in cm. Published even when days are missing; `days_with_valid_snowfall` counts the days behind it. A month with a missing day reads `I` in `quality_flags`, which wetterdienst derives from that count. | cm | >=0 |
| {term}`count_days_precipitation_amount_ge_1mm` | days_with_precip_ge_1mm | Number of days of the month with 1.0 mm of precipitation or more. | - | >=0 |
| {term}`count_days_valid_temperature_air_max_2m` | days_with_valid_max_temp | Number of days of the month with a valid daily maximum temperature. | - | >=0 |
| {term}`count_days_valid_temperature_air_mean_minmax_2m` | days_with_valid_mean_temp | Number of days of the month with a valid daily mean temperature, the daily mean being calculated from the daily extremes. | - | >=0 |
| {term}`count_days_valid_temperature_air_min_2m` | days_with_valid_min_temp | Number of days of the month with a valid daily minimum temperature. | - | >=0 |
| {term}`count_days_valid_precipitation_amount` | days_with_valid_precip | Number of days of the month with a valid precipitation total. | - | >=0 |
| {term}`count_days_valid_snow_depth_new` | days_with_valid_snowfall | Number of days of the month with a valid snowfall total. | - | >=0 |
| {term}`count_days_valid_sunshine_duration` | days_with_valid_sunshine | Number of days of the month with a valid sunshine observation. 39 of the 285 values of Ontario in 1985 are fractions of a day, always a whole number of 24ths. | - | >=0 |
| {term}`temperature_air_mean_minmax_2m_normal` | normal_mean_temperature | Climate normal of the mean air temperature for the calendar month, the daily mean being calculated from the daily extremes. The source lists it by name and states no period. | °C | - |
| {term}`precipitation_amount_normal` | normal_precipitation | Climate normal of the total precipitation for the calendar month. The source lists it by name and states no period. | mm | >=0 |
| {term}`snow_depth_new_normal` | normal_snowfall | Climate normal of the total snowfall for the calendar month. The source lists it by name and states no period. | cm | >=0 |
| {term}`sunshine_duration_normal` | normal_sunshine | Climate normal of the bright sunshine duration for the calendar month. The source lists it by name and states no period. | h | >=0 |
