# monthly

## metadata

| property      | value                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | monthly                                                                                                                                                                            |
| original name | mly                                                                                                                                                                                |
| url           | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0) |

## datasets

### data

#### metadata

| property    | value                                                                                                                                                                                                                                      |
|-------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name        | data                                                                                                                                                                                                                                       |
| original    | data                                                                                                                                                                                                                                       |
| description | Historical monthly station observations for Canada ([details](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0)) |
| access      | [here](https://www.canada.ca/en/environment-climate-change/services/climate-change/canadian-centre-climate-services/display-download/technical-documentation-daily-data.html#toc0)                                                         |

#### parameters

| name                                | original name              | description                                | unit | constraints |
|-------------------------------------|----------------------------|--------------------------------------------|------|-------------|
| {term}`precipitation_height`        | total precip (mm)          | total precipitation                        | mm   | >=0         |
| {term}`precipitation_height_liquid` | total rain (mm)            | total liquid precipitation                 | mm   | >=0         |
| {term}`snow_depth`                  | snow grnd last day (cm)    | total snow depth                           | cm   | >=0         |
| {term}`snow_depth_new`              | total snow (cm)            | new snow depth                             | cm   | >=0         |
| {term}`temperature_air_max_2m`      | extr max temp (°c)         | monthly maximum 2m air temperature         | °C   | -           |
| {term}`temperature_air_max_2m_mean` | mean max temp (°c)         | monthly mean of maximum 2m air temperature | °C   | -           |
| {term}`temperature_air_mean_2m`     | mean temp (°c)             | monthly mean of 2m air temperature         | °C   | -           |
| {term}`temperature_air_min_2m`      | extr min temp (°c)         | monthly minimum 2m air temperature         | °C   | -           |
| {term}`temperature_air_min_2m_mean` | mean min temp (°c)         | monthly mean of minimum 2m air temperature | °C   | -           |
| {term}`wind_direction_gust_max`     | dir of max gust (10's deg) | wind direction of maximum wind gust        | °    | >=0,<=360   |
| {term}`wind_gust_max`               | spd of max gust (km/h)     | maximum wind gust                          | km/h | >=0         |
