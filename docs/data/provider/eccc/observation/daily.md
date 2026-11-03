# daily

## metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | daily                                                                                                                                                                              |
| original name | dly                                                                                                                                                                                |
| url           | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                                                                                               |
| original name | data                                                                                                                                                                               |
| description   | Historical daily station observations for Canada                                                                                                                                   |
| access        | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

#### parameters

| name                                | original name             | description                         | unit | constraints |
|-------------------------------------|---------------------------|-------------------------------------|------|-------------|
| {term}`cooling_degree_day` | cooling_degree_days | Cooling degree-days of the day: the degrees Celsius that the mean temperature is above 18 °C, 0 if it is at or below. | °Cd | >=0 |
| {term}`heating_degree_day` | heating_degree_days | Heating degree-days of the day: the degrees Celsius that the mean temperature is below 18 °C, 0 if it is at or above. | °Cd | >=0 |
| {term}`humidity_relative_max` | max_rel_humidity | Highest relative humidity over the period. | %       | - |
| {term}`humidity_relative_min` | min_rel_humidity | Lowest of the hourly relative humidity values of the day, in %. | % | - |
| {term}`precipitation_amount` | total_precipitation | Total precipitation of the climatological day (at a station that observes all day, since July 1961, 0601 UTC to 0600 UTC of the next day): the rainfall plus the water equivalent of the snowfall, in mm. | mm | >=0 |
| {term}`precipitation_amount_liquid` | total_rain | Total rainfall of the climatological day (at a station that observes all day, since July 1961, 0601 UTC to 0600 UTC of the next day): all liquid precipitation (rain, drizzle, freezing rain, hail), in mm. | mm | >=0 |
| {term}`snow_depth` | snow_on_ground | Depth of snow on the ground in cm at the time of the observation, found from a series of measurements over the site (at a station that observes twice a day, the morning observation). | cm | >=0 |
| {term}`snow_depth_new` | total_snow | Total snowfall of the climatological day (at a station that observes all day, since July 1961, 0601 UTC to 0600 UTC of the next day): the measured depth of newly fallen snow (snow, ice pellets), in cm. | cm | >=0 |
| {term}`temperature_air_max_2m` | max_temperature | Highest air temperature of the climatological day (at a station that observes all day, since July 1961, 0601 UTC to 0600 UTC of the next day). The source states no height; the 2 m of the name is the convention. | °C | - |
| {term}`temperature_air_mean_minmax_2m` | mean_temperature | Mean air temperature of the climatological day (at a station that observes all day, since July 1961, 0601 UTC to 0600 UTC of the next day): (maximum + minimum) / 2, as the source defines it. | °C | - |
| {term}`temperature_air_min_2m` | min_temperature | Lowest air temperature of the climatological day (at a station that observes all day, since July 1961, 0601 UTC to 0600 UTC of the next day). The source states no height; the 2 m of the name is the convention. | °C | - |
| {term}`wind_direction_gust_max` | direction_max_gust | Direction (true, not magnetic) the day's maximum gust blew from, published in tens of degrees ("36 means 360 degrees true") and returned in degrees. The source reports it only if the gust exceeds 29 km/h. The source's 0 beside a gust of 0 (none reported) is null. | ° | >=0,<=360 |
| {term}`wind_gust_max` | speed_max_gust | Speed of the day's maximum gust: the peak instantaneous reading of the anemometer, which typically lasts 3 to 5 seconds. The source reports it only above 30 km/h; the collection's 0 for the other days is null. | km/h | >=0 |
