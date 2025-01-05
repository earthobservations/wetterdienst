# hourly

## metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | hourly                                                                                                                                                                             |
| original name | hly                                                                                                                                                                                |
| url           | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                                                                                               |
| original name | data                                                                                                                                                                               |
| description   | Historical hourly station observations of 2m air temperature, humidity, wind direction, wind speed, visibility range, air pressure, humidex, wind gust and weather for Canada      |
| access        | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

#### parameters

| name                          | original name       | description              | unit type     | unit | constraints |
|-------------------------------|---------------------|--------------------------|---------------|------|-------------|
| humidex                       | hmdx                | humidex                  | dimensionless | -    | >=0         |
| humidity                      | rel hum (%)         | humidity                 | fraction      | %    | >=0,<=100   |
| pressure_air_site             | stn press (kpa)     | air pressure at site     | pressure      | kPa  | >=0         |
| temperature_air_mean_2m       | temp (°c)           | 2m air temperature       | temperature   | °C   | -           |
| temperature_dew_point_mean_2m | dew point temp (°c) | 2m dew point temperature | temperature   | °C   | -           |
| visibility_range              | visibility (km)     | visibility range         | length_medium | km   | >=0         |
| weather                       | weather             | weather code             | dimensionless | -    | -           |
| wind_direction                | wind dir (10s deg)  | wind direction           | angle         | °    | >=0,<=360   |
| wind_gust_max                 | wind gust (km/h)    | wind gust maximum        | speed         | km/h | >=0         |
| wind_speed                    | wind spd (km/h)     | wind speed               | speed         | km/h | >=0         |
