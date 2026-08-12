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
| description | Historical monthly station observations for Canada ([details](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0)) |
| access      | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0)                                                         |

#### parameters

| name                            | original name           | description                | unit | constraints |
|---------------------------------|-------------------------|----------------------------|------|-------------|
| {term}`cooling_degree_day`      | cooling_degree_days     | cooling degree days        | °Cd  | >=0         |
| {term}`heating_degree_day`      | heating_degree_days     | heating degree days        | °Cd  | >=0         |
| {term}`precipitation_height`    | total_precipitation     | precipitation height       | mm   | >=0         |
| {term}`snow_depth`              | snow_on_ground_last_day | snow depth on the last day | cm   | >=0         |
| {term}`snow_depth_new`          | total_snowfall          | snowfall total             | cm   | >=0         |
| {term}`sunshine_duration`       | bright_sunshine         | bright sunshine duration   | h    | >=0         |
| {term}`temperature_air_max_2m`  | max_temperature         | 2m maximum air temperature | °C   | -           |
| {term}`temperature_air_mean_2m` | mean_temperature        | 2m mean air temperature    | °C   | -           |
| {term}`temperature_air_min_2m`  | min_temperature         | 2m minimum air temperature | °C   | -           |
| {term}`count_days_precipitation_height_ge_1mm` | days_with_precip_ge_1mm | days with >= 1 mm precipitation | - | >=0 |
| {term}`count_days_valid_temperature_air_max_2m` | days_with_valid_max_temp | days with a valid maximum temperature | - | >=0 |
| {term}`count_days_valid_temperature_air_mean_2m` | days_with_valid_mean_temp | days with a valid mean temperature | - | >=0 |
| {term}`count_days_valid_temperature_air_min_2m` | days_with_valid_min_temp | days with a valid minimum temperature | - | >=0 |
| {term}`count_days_valid_precipitation_height` | days_with_valid_precip | days with a valid precipitation observation | - | >=0 |
| {term}`count_days_valid_snow_depth_new` | days_with_valid_snowfall | days with a valid snowfall observation | - | >=0 |
| {term}`count_days_valid_sunshine_duration` | days_with_valid_sunshine | days with a valid sunshine observation | - | >=0 |
| {term}`temperature_air_mean_2m_normal` | normal_mean_temperature | normal of the mean air temperature | °C | - |
| {term}`precipitation_height_normal` | normal_precipitation | normal of the precipitation height | mm | >=0 |
| {term}`snow_depth_new_normal` | normal_snowfall | normal of the snowfall total | cm | >=0 |
| {term}`sunshine_duration_normal` | normal_sunshine | normal of the sunshine duration | h | >=0 |
