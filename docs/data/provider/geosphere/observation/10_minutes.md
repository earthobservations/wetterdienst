# 10_minutes

## metadata

| property      | value                                                      |
|---------------|------------------------------------------------------------|
| name          | 10_minutes                                                 |
| original name | klima-v1-10min                                             |
| url           | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-10min) |

## datasets

### data

#### metadata

| property      | value                                                      |
|---------------|------------------------------------------------------------|
| name          | data                                                       |
| original name | data                                                       |
| description   | historical 10 minute data                                  |
| access        | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-10min) |

#### parameters

| name                             | original name | description                      | unit  | original unit | constraints |
|----------------------------------|---------------|----------------------------------|-------|---------------|-------------|
| humidity                         | rf            | relative humidity                | %     | %             | >=0,<=100   |
| precipitation_duration           | rrm           | precipitation duration           | s     | min           | >=0         |
| precipitation_height             | rr            | precipitation height             | kg/m² | mm            | >=0         |
| pressure_air_site                | p             | air pressure at site             | Pa    | hPa           | >=0         |
| pressure_air_sl                  | pred          | air pressure at sea level        | Pa    | hPa           | >=0         |
| radiation_global                 | cglo          | global radiation                 | J/m²  | J/cm²         | >=0         |
| radiation_sky_short_wave_diffuse | chim          | sky short wave diffuse radiation | J/m²  | J/cm²         | >=0         |
| snow_depth                       | sh            | snow depth                       | m     | cm            | >=0         |
| sunshine_duration                | so            | sunshine duration                | s     | s             | >=0         |
| temperature_air_max_0_05m        | tsmax         | air temperature max at 0.05m     | K     | °C            | -           |
| temperature_air_max_2m           | tlmax         | air temperature max at 2m        | K     | °C            | -           |
| temperature_air_mean_0_05m       | ts            | air temperature mean at 0.05m    | K     | °C            | -           |
| temperature_air_mean_2m          | tl            | air temperature mean at 2m       | K     | °C            | -           |
| temperature_air_min_0_05m        | tsmin         | air temperature min at 0.05m     | K     | °C            | -           |
| temperature_air_min_2m           | tlmin         | air temperature min at 2m        | K     | °C            | -           |
| temperature_soil_mean_0_1m       | tb10          | soil temperature mean at 0.1m    | K     | °C            | -           |
| temperature_soil_mean_0_2m       | tb20          | soil temperature mean at 0.2m    | K     | °C            | -           |
| temperature_soil_mean_0_5m       | tb50          | soil temperature mean at 0.5m    | K     | °C            | -           |
| wind_direction                   | dd            | wind direction                   | °     | °             | >=0,<=360   |
| wind_direction_gust_max          | ddx           | wind direction gust max          | °     | °             | >=0,<=360   |
| wind_gust_max                    | ffx           | wind gust max                    | m/s   | m/s           | >=0         |
| wind_speed                       | ff            | wind speed                       | m/s   | m/s           | >=0         |
| wind_speed_arithmetic            | ffam          | arithmetic mean of wind speed    | m/s   | m/s           | >=0         |
