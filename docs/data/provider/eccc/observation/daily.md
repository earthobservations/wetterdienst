# daily

## metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | daily                                                                                                                                                                              |
| original name | dly                                                                                                                                                                                |
| url           | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                                                                                               |
| original name | data                                                                                                                                                                               |
| description   | Historical daily station observations for Canada                                                                                                                                   |
| access        | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

#### parameters

| name                        | original name             | description                         | unit type     | unit | constraints |
|-----------------------------|---------------------------|-------------------------------------|---------------|------|-------------|
| count_days_cooling_degree   | cool deg days (°c)        | count of cooling degree days        | dimensionless | -    | >=0         |
| count_days_heating_degree   | heat deg days (°c)        | count of heating degree days        | dimensionless | -    | >=0         |
| precipitation_height        | total precip (mm)         | total precipitation                 | precipitation | mm   | >=0         |
| precipitation_height_liquid | total rain (mm)           | total liquid precipitation          | precipitation | mm   | >=0         |
| snow_depth                  | snow on grnd (cm)         | total snow depth                    | length_short  | cm   | >=0         |
| snow_depth_new              | total snow (cm)           | new snow depth                      | length_short  | cm   | >=0         |
| temperature_air_max_2m      | max temp (°c)             | daily maximum 2m air temperature    | temperature   | °C   | -           |
| temperature_air_mean_2m     | mean temp (°c)            | daily mean 2m air temperature       | temperature   | °C   | -           |
| temperature_air_min_2m      | min temp (°c)             | daily minimum 2m air temperature    | temperature   | °C   | -           |
| wind_direction_gust_max     | dir of max gust (10s deg) | wind direction of maximum wind gust | angle         | °    | >=0,<=360   |
| wind_gust_max               | spd of max gust (km/h)    | maximum wind gust                   | speed         | km/h | >=0         |
