# hourly

## metadata

| property      | value                                                                                 |
|---------------|---------------------------------------------------------------------------------------|
| name          | hourly                                                                                |
| original name | hourly                                                                                |
| url           | [here](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/index.html) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                                                                                                                    |
| original name | data                                                                                                                                                                                                    |
| description   | Historical hourly weather data from the Global Historical Climatology Network (GHCN) ([details](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf)) |
| url           | [here](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/index.html)                                                                                                                   |

#### parameters

| name                            | original name          | description                                                                                                                                                                                 | unit             | original unit | constraints                |
|---------------------------------|------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|---------------|----------------------------|
| humidity                        | relative_humidity      | Relative humidity is calculated from air (dry bulb) temperature and dewpoint temperature (whole percent)                                                                                    | :math:`\%`       | :math:`\%`    | :math:`\geq{0}, \leq{100}` |
| precipitation_height            | precipitation          | total liquid precipitation (rain or melted snow) for past hour; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters)                                | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_3h    | precipitation_3_hour   | 3-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters)  | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_6h    | precipitation_6_hour   | 6-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters)  | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_9h    | precipitation_9_hour   | 9-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters)  | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_12h   | precipitation_12_hour  | 12-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters) | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_15h   | precipitation_15_hour  | 15-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters) | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_18h   | precipitation_18_hour  | 18-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters) | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_21h   | precipitation_21_hour  | 21-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters) | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| precipitation_height_last_24h   | precipitation_24_hour  | 24-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount of precipitation (millimeters) | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`            |
| pressure_air_sea_level          | sea_level_pressure     | Sea level pressure (hectopascals)                                                                                                                                                           | :math:`Pa`       | :math:`hPa`   | :math:`\geq{0}`            |
| pressure_air_site               | station_level_pressure | Station pressure (hectopascals)                                                                                                                                                             | :math:`Pa`       | :math:`hPa`   | :math:`\geq{0}`            |
| pressure_air_site_delta_last_3h | pressure_3hr_change    | 3-hour pressure change (hectopascals)                                                                                                                                                       | :math:`Pa`       | :math:`hPa`   | :math:`\geq{0}`            |
| pressure_air_site_reduced       | altimeter              | Reduced pressure (hectopascals)                                                                                                                                                             | :math:`Pa`       | :math:`hPa`   | :math:`\geq{0}`            |
| snow_depth                      | snow_depth             | depth of snowpack on the ground (centimeters/m)                                                                                                                                             | :math:`m`        | :math:`cm`    | :math:`\geq{0}`            |
| temperature_air_mean_2m         | temperature            | 2 meter (circa) Above Ground Level Air (dry bulb) Temperature (⁰C to tenths)                                                                                                                | :math:`K`        | :math:`°C`    |
| temperature_dew_point_mean_2m   | dew_point_temperature  | Dew Point Temperature (⁰C to tenths)                                                                                                                                                        | :math:`K`        | :math:`°C`    |
| temperature_wet_mean_2m         | wet_bulb_temperature   | Wet bulb temperature (⁰C to tenths)                                                                                                                                                         | :math:`K`        | :math:`°C`    |
| visibility_range                | visibility             | horizontal distance at which an object can be seen and identified (kilometers)                                                                                                              | :math:`m`        | :math:`km`    | :math:`\geq{0}`            |
| wind_direction                  | wind_direction         | Wind direction from true north using compass directions (e.g. 360=true north, 180=south, 270=west, etc.). Note: A direction of “000” is given for calm winds. (whole degrees)               | :math:`°`        | :math:`°`     | :math:`\geq{0}, \leq{360}` |
| wind_gust_max                   | wind_gust              | Peak short duration (usually < 20 seconds) wind speed (meters per second) that exceeds the wind_speed average                                                                               | :math:`m/s`      | :math:`m/s`   | :math:`\geq{0}`            |
| wind_speed                      | wind_speed             | Wind speed (meters per second)                                                                                                                                                              | :math:`m/s`      | :math:`m/s`   | :math:`\geq{0}`            |
