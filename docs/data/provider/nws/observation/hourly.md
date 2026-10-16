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

| property      | value                                                                                                                                                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                                                                                                                                           |
| original name | data                                                                                                                                                                                                                           |
| description   | Station observations (temperature, pressure, precipitation, etc.) for the US, one report for each hour: the METAR or SPECI report nearest to the full hour, else the nearest 5-minute row ([details](https://www.weather.gov/documentation/services-web-api)) |
| access        | [here](https://www.weather.gov/documentation/services-web-api)                                                                                                                                                                 |

#### parameters

| name                                    | original name             | description                                                                      | unit | constraints |
|-----------------------------------------|---------------------------|----------------------------------------------------------------------------------|------|-------------|
| {term}`temperature_air_2m`              | temperature               | air temperature                                                                  | °C   | -           |
| {term}`temperature_dew_point_2m`        | dewpoint                  | dew point temperature                                                            | °C   | -           |
| {term}`wind_direction`                  | winddirection             | wind direction. The source's 0 (a calm wind) is null.                            | °    | >=0,<=360   |
| {term}`wind_speed`                      | windspeed                 | wind speed                                                                       | km/h | >=0         |
| {term}`wind_gust_max`                   | windgust                  | maximum wind gust                                                                | km/h | >=0         |
| {term}`pressure_air_site`               | barometricpressure        | air pressure at station height                                                   | Pa   | >=0         |
| {term}`pressure_air_sea_level`          | sealevelpressure          | air pressure at sea level                                                        | Pa   | >=0         |
| {term}`visibility`                      | visibility                | visibility range                                                                 | m    | >=0         |
| {term}`temperature_air_max_2m_last_24h` | maxtemperaturelast24hours | maximum air temperature in the last 24 hours                                     | °C   | -           |
| {term}`temperature_air_min_2m_last_24h` | mintemperaturelast24hours | minimum air temperature in the last 24 hours                                     | °C   | -           |
| {term}`precipitation_amount`            | precipitationlasthour     | precipitation height of last hour                                                | mm   | >=0         |
| {term}`precipitation_amount_last_3h`    | precipitationlast3hours   | precipitation height of last three hours                                         | mm   | >=0         |
| {term}`precipitation_amount_last_6h`    | precipitationlast6hours   | precipitation height of last six hours                                           | mm   | >=0         |
| {term}`humidity_relative`               | relativehumidity          | relative humidity                                                                | %    | >=0,<=100   |
| {term}`temperature_wind_chill`          | windchill                 | wind chill temperature calculated by NWS (https://www.weather.gov/gjt/windchill) | °C   | -           |
