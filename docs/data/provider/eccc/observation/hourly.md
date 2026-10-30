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
| description   | Historical hourly station observations of air temperature, dew point, humidity, precipitation, station pressure, visibility, wind direction, wind speed, wind chill and humidex for Canada |
| access        | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

#### parameters

| name                             | original name     | description                                                                                                                               | unit | constraints |
|----------------------------------|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`temperature_air_2m` | temp | Air temperature in °C. The source states no height; the 2 m of the name is the convention. | °C | - |
| {term}`temperature_dew_point_2m` | dew_point_temp | Dew point temperature: the temperature to which the air would have to be cooled to reach saturation with respect to liquid water. The source states no height; the 2 m of the name is the convention. | °C | - |
| {term}`humidity_relative` | relative_humidity | Relative humidity in %: the ratio of the water vapour the air contains to the most it can hold at that temperature. | % | >=0,<=100 |
| {term}`precipitation_amount` | precip_amount | Precipitation amount in mm: the depth of water or water equivalent, to the nearest 0.2 mm; less is a trace. The source states no period for the hourly amount. | mm | >=0 |
| {term}`pressure_air_site` | station_pressure | Atmospheric pressure in kPa at the station elevation, not reduced to sea level. | kPa | >=0 |
| {term}`visibility` | visibility | Visibility in km: the distance at which objects of suitable size can be seen and identified. The source's largest value (15 statute miles, 24.1 km, at a manned station; 9, 14.5 km, at an automatic one) can stand for a larger visibility. | km | >=0 |
| {term}`wind_direction_mean_last_2min` | wind_direction | Direction (true, not magnetic) the wind blows from, the average of the two minutes ending at the time of observation, published in tens of degrees ("36 means 360 degrees true") and returned in degrees. The source's 0 beside a wind speed of 0 (a calm wind) is null. | ° | >=0,<=360 |
| {term}`wind_speed` | wind_speed | Wind speed in km/h: the average of the one-, two- or ten-minute period ending at the time of observation, usually at 10 m. | km/h | >=0 |
| {term}`temperature_wind_chill` | windchill | Wind chill: an index of how cold the weather feels, from the air temperature and the wind speed at 10 m. The source gives it only at 0 °C or below and a wind speed above 0. | °C | - |
| {term}`temperature_humidex` | humidex | Humidex: an index of how hot or humid the weather feels, the air temperature plus 0.5555 times the vapour pressure in hPa minus 10. The source shows it only when the air temperature is 20 °C or more and the humidex at least 1 degree above it. | °C | - |
