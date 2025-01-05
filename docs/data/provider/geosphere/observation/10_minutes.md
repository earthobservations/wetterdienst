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

| name                             | original name | description                      | unit type       | unit  | constraints |
|----------------------------------|---------------|----------------------------------|-----------------|-------|-------------|
| humidity                         | rf            | relative humidity                | fraction        | %     | >=0,<=100   |
| precipitation_duration           | rrm           | precipitation duration           | time            | min   | >=0         |
| precipitation_height             | rr            | precipitation height             | precipitation   | mm    | >=0         |
| pressure_air_site                | p             | air pressure at site             | pressure        | hPa   | >=0         |
| pressure_air_sl                  | pred          | air pressure at sea level        | pressure        | hPa   | >=0         |
| radiation_global                 | cglo          | global radiation                 | energy_per_area | J/cm² | >=0         |
| radiation_sky_short_wave_diffuse | chim          | sky short wave diffuse radiation | energy_per_area | J/cm² | >=0         |
| snow_depth                       | sh            | snow depth                       | length_short    | cm    | >=0         |
| sunshine_duration                | so            | sunshine duration                | time            | s     | >=0         |
| temperature_air_max_0_05m        | tsmax         | air temperature max at 0.05m     | temperature     | °C    | -           |
| temperature_air_max_2m           | tlmax         | air temperature max at 2m        | temperature     | °C    | -           |
| temperature_air_mean_0_05m       | ts            | air temperature mean at 0.05m    | temperature     | °C    | -           |
| temperature_air_mean_2m          | tl            | air temperature mean at 2m       | temperature     | °C    | -           |
| temperature_air_min_0_05m        | tsmin         | air temperature min at 0.05m     | temperature     | °C    | -           |
| temperature_air_min_2m           | tlmin         | air temperature min at 2m        | temperature     | °C    | -           |
| temperature_soil_mean_0_1m       | tb10          | soil temperature mean at 0.1m    | temperature     | °C    | -           |
| temperature_soil_mean_0_2m       | tb20          | soil temperature mean at 0.2m    | temperature     | °C    | -           |
| temperature_soil_mean_0_5m       | tb50          | soil temperature mean at 0.5m    | temperature     | °C    | -           |
| wind_direction                   | dd            | wind direction                   | angle           | °     | >=0,<=360   |
| wind_direction_gust_max          | ddx           | wind direction gust max          | angle           | °     | >=0,<=360   |
| wind_gust_max                    | ffx           | wind gust max                    | speed           | m/s   | >=0         |
| wind_speed                       | ff            | wind speed                       | speed           | m/s   | >=0         |
| wind_speed_arithmetic            | ffam          | arithmetic mean of wind speed    | speed           | m/s   | >=0         |
