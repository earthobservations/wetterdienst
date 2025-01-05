# hourly

## metadata

| property      | value                                                          |
|---------------|----------------------------------------------------------------|
| name          | hourly                                                         |
| original name | hourly                                                         |
| url           | [here](https://www.weather.gov/documentation/services-web-api) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                              |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                                                                               |
| original name | data                                                                                                                                                               |
| description   | Historical hourly station observations (temperature, pressure, precipitation, etc.) for the US ([details](https://www.weather.gov/documentation/services-web-api)) |
| access        | [here](https://www.weather.gov/documentation/services-web-api)                                                                                                     |

#### parameters

| name                            | original name             | description                                                                      | unit type     | unit | constraints |
|---------------------------------|---------------------------|----------------------------------------------------------------------------------|---------------|------|-------------|
| humidity                        | relativehumidity          | relative humidity                                                                | fraction      | %    | >=0,<=100   |
| precipitation_height            | precipitationlasthour     | precipitation height of last hour                                                | precipitation | mm   | >=0         |
| precipitation_height_last_3h    | precipitationlast3hours   | precipitation height of last three hours                                         | precipitation | mm   | >=0         |
| precipitation_height_last_6h    | precipitationlast6hours   | precipitation height of last six hours                                           | precipitation | mm   | >=0         |
| pressure_air_sh                 | barometricpressure        | air pressure at station height                                                   | pressure      | Pa   | >=0         |
| pressure_air_sl                 | sealevelpressure          | air pressure at sea level                                                        | pressure      | Pa   | >=0         |
| temperature_air_max_2m_last_24h | maxtemperaturelast24hours | maximum air temperature in the last 24 hours                                     | temperature   | °C   | -           |
| temperature_air_mean_2m         | temperature               | Average air temperature in 2m                                                    | temperature   | °C   | -           |
| temperature_air_min_2m_last_24h | mintemperaturelast24hours | minimum air temperature in the last 24 hours                                     | temperature   | °C   | -           |
| temperature_dew_point_mean_2m   | dewpoint                  | Average dew point temperature in 2m                                              | temperature   | °C   | -           |
| temperature_wind_chill          | windchill                 | wind chill temperature calculated by NWS (https://www.weather.gov/gjt/windchill) | temperature   | °C   | -           |
| visibility_range                | visibility                | visibility range                                                                 | length_medium | m    | >=0         |
| wind_direction                  | winddirection             | wind direction                                                                   | angle         | °    | >=0,<=360   |
| wind_gust_max                   | windgust                  | maximum wind gust                                                                | speed         | km/h | >=0         |
| wind_speed                      | windspeed                 | wind speed                                                                       | speed         | km/h | >=0         |
