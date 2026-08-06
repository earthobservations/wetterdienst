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

| name                                  | original name                            | description                      | unit | constraints |
|---------------------------------------|------------------------------------------|----------------------------------|------|-------------|
| {term}`humidity`                      | relativeHumidity                         | mean humidity                    | %    | >=0,<=100   |
| {term}`precipitation_form`            | precipitationType                        | form of precipitation            | -    | -           |
| {term}`precipitation_height`          | totalPrecipitationOrTotalWaterEquivalent | precipitation height             | mm   | >=0         |
| {term}`precipitation_intensity`       | intensityOfPrecipitation                 | precipitation intensity          | mm/s | >=0         |
| {term}`road_surface_condition`        | roadSurfaceCondition                     | road surface condition           | -    | -           |
| {term}`temperature_air_mean_2m`       | airTemperature                           | mean air temperature in 2m       | K    | -           |
| {term}`temperature_dew_point_mean_2m` | dewpointTemperature                      | mean dew point temperature in 2m | K    | -           |
| {term}`temperature_surface_mean`      | roadSurfaceTemperature                   | road surface temperature         | K    | -           |
| {term}`visibility_range`              | horizontalVisibility                     | visibility range                 | m    | >=0         |
| {term}`water_film_thickness`          | waterFilmThickness                       | thickness of water film          | cm   | >=0         |
| {term}`wind_direction`                | windDirection                            | mean direction of wind           | °    | >=0,<=360   |
| {term}`wind_direction_gust_max`       | maximumWindGustDirection                 | direction of maximum wind gust   | °    | >=0,<=360   |
| {term}`wind_gust_max`                 | maximumWindGustSpeed                     | maximum wind gust                | m/s  | >=0         |
| {term}`wind_speed`                    | windSpeed                                | mean wind speed                  | m/s  | >=0         |
