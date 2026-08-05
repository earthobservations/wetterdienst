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

| name                               | original name | description                   | unit | constraints |
|------------------------------------|---------------|-------------------------------|------|-------------|
| {term}`humidity`                   | rf            | relative humidity             | %    | >=0,<=100   |
| {term}`precipitation_duration`     | rrm           | precipitation duration        | min  | >=0         |
| {term}`precipitation_height`       | rr            | precipitation height          | mm   | >=0         |
| {term}`pressure_air_site`          | p             | air pressure at site          | hPa  | >=0         |
| {term}`pressure_air_sea_level`     | pred          | air pressure at sea level     | hPa  | >=0         |
| {term}`radiation_global_intensity` | cglo          | global radiation              | W/m² | >=0         |
| {term}`snow_depth`                 | sh            | snow depth                    | cm   | >=0         |
| {term}`sunshine_duration`          | so_h          | sunshine duration             | h    | >=0         |
| {term}`temperature_air_mean_2m`    | tl            | air temperature mean at 2m    | °C   | -           |
| {term}`temperature_air_min_0_05m`  | tsmin         | air temperature min at 0.05m  | °C   | -           |
| {term}`temperature_soil_mean_0_1m` | tb10          | soil temperature mean at 0.1m | °C   | -           |
| {term}`temperature_soil_mean_0_2m` | tb20          | soil temperature mean at 0.2m | °C   | -           |
| {term}`temperature_soil_mean_0_5m` | tb50          | soil temperature mean at 0.5m | °C   | -           |
| {term}`temperature_soil_mean_1m`   | tb100         | soil temperature mean at 1m   | °C   | -           |
| {term}`temperature_soil_mean_2m`   | tb200         | soil temperature mean at 2m   | °C   | -           |
| {term}`wind_direction`             | dd            | wind direction                | °    | >=0,<=360   |
| {term}`wind_direction_gust_max`    | ddx           | wind direction gust max       | °    | >=0,<=360   |
| {term}`wind_gust_max`              | ffx           | wind gust max                 | m/s  | >=0         |
| {term}`wind_speed`                 | ff            | wind speed                    | m/s  | >=0         |
