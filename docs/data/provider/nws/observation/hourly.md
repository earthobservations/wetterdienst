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

| name                                    | original name             | description                                                                      | unit | constraints |
|-----------------------------------------|---------------------------|----------------------------------------------------------------------------------|------|-------------|
| {term}`humidity`                        | relativehumidity          | relative humidity                                                                | %    | >=0,<=100   |
| {term}`precipitation_height`            | precipitationlasthour     | precipitation height of last hour                                                | mm   | >=0         |
| {term}`precipitation_height_last_3h`    | precipitationlast3hours   | precipitation height of last three hours                                         | mm   | >=0         |
| {term}`precipitation_height_last_6h`    | precipitationlast6hours   | precipitation height of last six hours                                           | mm   | >=0         |
| {term}`pressure_air_site`               | barometricpressure        | air pressure at station height                                                   | Pa   | >=0         |
| {term}`pressure_air_sea_level`          | sealevelpressure          | air pressure at sea level                                                        | Pa   | >=0         |
| {term}`temperature_air_max_2m_last_24h` | maxtemperaturelast24hours | maximum air temperature in the last 24 hours                                     | °C   | -           |
| {term}`temperature_air_mean_2m`         | temperature               | Average air temperature in 2m                                                    | °C   | -           |
| {term}`temperature_air_min_2m_last_24h` | mintemperaturelast24hours | minimum air temperature in the last 24 hours                                     | °C   | -           |
| {term}`temperature_dew_point_mean_2m`   | dewpoint                  | Average dew point temperature in 2m                                              | °C   | -           |
| {term}`temperature_wind_chill`          | windchill                 | wind chill temperature calculated by NWS (https://www.weather.gov/gjt/windchill) | °C   | -           |
| {term}`visibility_range`                | visibility                | visibility range                                                                 | m    | >=0         |
| {term}`wind_direction`                  | winddirection             | wind direction                                                                   | °    | >=0,<=360   |
| {term}`wind_gust_max`                   | windgust                  | maximum wind gust                                                                | km/h | >=0         |
| {term}`wind_speed`                      | windspeed                 | wind speed                                                                       | km/h | >=0         |
