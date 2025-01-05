# 15_minutes

## metadata

| property      | value                                                                          |
|---------------|--------------------------------------------------------------------------------|
| name          | 15_minutes                                                                     |
| original_name | 15_minutes                                                                     |
| url           | [here](https://opendata.dwd.de/weather/weather_reports/road_weather_stations/) |

## datasets

### data

#### metadata

| property      | value                                                                          |
|---------------|--------------------------------------------------------------------------------|
| name          | data                                                                           |
| original_name | data                                                                           |
| description   | 15-minute road weather data of German highway stations                         |
| access        | [here](https://opendata.dwd.de/weather/weather_reports/road_weather_stations/) |

#### parameters

| name                          | original name                            | description                      | unit type     | unit          | constraints |
|-------------------------------|------------------------------------------|----------------------------------|---------------|---------------|-------------|
| humidity                      | relativeHumidity                         | mean humidity                    | fraction      | %             | >=0,<=100   |
| precipitation_form            | precipitationType                        | form of precipitation            | dimensionless | -             | -           |
| precipitation_height          | totalPrecipitationOrTotalWaterEquivalent | precipitation height             | precipitation | mm            | >=0         |
| precipitation_intensity       | intensityOfPrecipitation                 | precipitation intensity          | speed         | mm/s          | >=0         |
| road_surface_condition        | roadSurfaceCondition                     | road surface condition           | dimensionless | -             | -           |
| temperature_air_mean_2m       | airTemperature                           | mean air temperature in 2m       | temperature   | K             | -           |
| temperature_dew_point_mean_2m | dewpointTemperature                      | mean dew point temperature in 2m | temperature   | K             | -           |
| temperature_surface_mean      | roadSurfaceTemperature                   | road surface temperature         | temperature   | K             | -           |
| visibility_range              | horizontalVisibility                     | visibility range                 | length_medium | m             | >=0         |
| water_film_thickness          | waterFilmThickness                       | thickness of water film          | length_short  | cm            | >=0         |
| wind_direction                | windDirection                            | mean direction of wind           | angle         | °             | >=0,<=360   |
| wind_direction_gust_max       | maximumWindGustDirection                 | direction of maximum wind gust   | angle         | °             | >=0,<=360   |
| wind_gust_max                 | maximumWindGustSpeed                     | maximum wind gust                | speed         | m/s           | >=0         |
| wind_speed                    | windSpeed                                | mean wind speed                  | speed         | m/s           | >=0         |
