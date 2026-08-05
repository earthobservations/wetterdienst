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
| description   | Historical hourly station observations of 2m air temperature, humidity, wind direction, wind speed, visibility range, air pressure, wind gust and weather for Canada               |
| access        | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

#### parameters

| name                                  | original name       | description              | unit | constraints |
|---------------------------------------|---------------------|--------------------------|------|-------------|
| {term}`humidity`                      | rel hum (%)         | humidity                 | %    | >=0,<=100   |
| {term}`pressure_air_site`             | stn press (kpa)     | air pressure at site     | kPa  | >=0         |
| {term}`temperature_air_mean_2m`       | temp (°c)           | 2m air temperature       | °C   | -           |
| {term}`temperature_dew_point_mean_2m` | dew point temp (°c) | 2m dew point temperature | °C   | -           |
| {term}`visibility_range`              | visibility (km)     | visibility range         | km   | >=0         |
| {term}`weather`                       | weather             | weather code             | -    | -           |
| {term}`wind_direction`                | wind dir (10s deg)  | wind direction           | °    | >=0,<=360   |
| {term}`wind_gust_max`                 | wind gust (km/h)    | wind gust maximum        | km/h | >=0         |
| {term}`wind_speed`                    | wind spd (km/h)     | wind speed               | km/h | >=0         |
