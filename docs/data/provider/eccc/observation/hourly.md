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

| name                                  | original name     | description                      | unit | constraints |
|---------------------------------------|-------------------|----------------------------------|------|-------------|
| {term}`temperature_air_2m`            | temp              | 2m air temperature               | °C   | -           |
| {term}`temperature_dew_point_2m`      | dew_point_temp    | 2m dew point temperature         | °C   | -           |
| {term}`humidity_relative`             | relative_humidity | humidity                         | %    | >=0,<=100   |
| {term}`precipitation_amount`          | precip_amount     | precipitation height             | mm   | >=0         |
| {term}`pressure_air_site`             | station_pressure  | air pressure at site             | kPa  | >=0         |
| {term}`visibility`                    | visibility        | visibility range                 | km   | >=0         |
| {term}`wind_direction`                | wind_direction    | wind direction (source: 10s deg) | °    | >=0,<=360   |
| {term}`wind_speed`                    | wind_speed        | wind speed                       | km/h | >=0         |
| {term}`temperature_wind_chill`        | windchill         | wind chill temperature           | °C   | -           |
| {term}`temperature_humidex`           | humidex           | humidex apparent temperature     | °C   | -           |
