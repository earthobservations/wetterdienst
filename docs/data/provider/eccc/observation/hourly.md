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
| url           | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

#### parameters

| name                          | original name       | description              | unit          | original unit  | constraints                |
|-------------------------------|---------------------|--------------------------|---------------|----------------|----------------------------|
| humidex                       | hmdx                | humidex                  | :math:`-`     | :math:`-`      | :math:`\geq{0}`            |
| humidity                      | rel hum (%)         | humidity                 | :math:`%`     | :math:`%`      | :math:`\geq{0}, \leq{100}` |
| pressure_air_site             | stn press (kpa)     | air pressure at site     | :math:`Pa`    | :math:`kPa`    | :math:`\geq{0}`            |
| temperature_air_mean_2m       | temp (°c)           | 2m air temperature       | :math:`K`     | :math:`°C`     | :math:`None`               |
| temperature_dew_point_mean_2m | dew point temp (°c) | 2m dew point temperature | :math:`K`     | :math:`°C`     | :math:`None`               |
| visibility_range              | visibility (km)     | visibility range         | :math:`m`     | :math:`km`     | :math:`\geq{0}`            |
| weather                       | weather             | weather code             | :math:`-`     | :math:`-`      | none                       |
| wind_direction                | wind dir (10s deg)  | wind direction           | :math:`°`     | :math:`°`      | :math:`\geq{0}, \leq{360}` |
| wind_gust_max                 | wind gust (km/h)    | wind gust maximum        | :math:`m / s` | :math:`km / h` | :math:`\geq{0}`            |
| wind_speed                    | wind spd (km/h)     | wind speed               | :math:`m / s` | :math:`km / h` | :math:`\geq{0}`            |
