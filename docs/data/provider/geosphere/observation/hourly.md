# hourly

## metadata

| property      | value                                                   |
|---------------|---------------------------------------------------------|
| name          | hourly                                                  |
| original name | klima-v1-1h                                             |
| url           | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-1h) |

## datasets

### data

#### metadata

| property      | value                                                                                 |
|---------------|---------------------------------------------------------------------------------------|
| name          | data                                                                                  |
| original name | data                                                                                  |
| description   | Historical hourly station observations of 2m air temperature and humidity for Germany |
| access        | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-1h)                               |

#### parameters

| name                       | original name | description                   | unit  | original unit | constraints |
|----------------------------|---------------|-------------------------------|-------|---------------|-------------|
| humidity                   | rf            | relative humidity             | %     | %             | >=0,<=100   |
| precipitation_duration     | rrm           | precipitation duration        | s     | min           | >=0         |
| precipitation_height       | rr            | precipitation height          | kg/m² | mm            | >=0         |
| pressure_air_site          | p             | air pressure at site          | Pa    | hPa           | >=0         |
| pressure_air_sl            | pred          | air pressure at sea level     | Pa    | hPa           | >=0         |
| radiation_global           | cglo          | global radiation              | J/m²  | J/cm²         | >=0         |
| snow_depth                 | sh            | snow depth                    | m     | cm            | >=0         |
| sunshine_duration          | so_h          | sunshine duration             | s     | h             | >=0         |
| temperature_air_mean_2m    | tl            | air temperature mean at 2m    | K     | °C            | -           |
| temperature_air_min_0_05m  | tsmin         | air temperature min at 0.05m  | K     | °C            | -           |
| temperature_soil_mean_0_1m | tb10          | soil temperature mean at 0.1m | K     | °C            | -           |
| temperature_soil_mean_0_2m | tb20          | soil temperature mean at 0.2m | K     | °C            | -           |
| temperature_soil_mean_0_5m | tb50          | soil temperature mean at 0.5m | K     | °C            | -           |
| temperature_soil_mean_1m   | tb100         | soil temperature mean at 1m   | K     | °C            | -           |
| temperature_soil_mean_2m   | tb200         | soil temperature mean at 2m   | K     | °C            | -           |
| wind_direction             | dd            | wind direction                | °     | °             | >=0,<=360   |
| wind_direction_gust_max    | ddx           | wind direction gust max       | °     | °             | >=0,<=360   |
| wind_gust_max              | ffx           | wind gust max                 | m/s   | m/s           | >=0         |
| wind_speed                 | ff            | wind speed                    | m/s   | m/s           | >=0         |
