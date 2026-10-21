# hourly

## metadata

| property      | value                                                     |
|---------------|-----------------------------------------------------------|
| name          | hourly                                                    |
| original name | klima-v2-1h                                               |
| url           | [here](https://data.hub.geosphere.at/dataset/klima-v2-1h) |

## datasets

### data

#### metadata

| property      | value                                                                        |
|---------------|------------------------------------------------------------------------------|
| name          | data                                                                         |
| original name | data                                                                         |
| description   | Historical hourly station observations for Austria, with quality information |
| access        | [here](https://data.hub.geosphere.at/dataset/klima-v2-1h)                    |

#### parameters

| name                                    | original name | description                                                                            | unit | constraints |
|-----------------------------------------|---------------|----------------------------------------------------------------------------------------|------|-------------|
| {term}`humidity_relative`               | rf            | Relative humidity, hourly measured value.                                              | %    | >=0,<=100   |
| {term}`precipitation_duration`          | rrm           | Precipitation duration, hourly sum.                                                    | min  | >=0         |
| {term}`precipitation_amount`            | rr            | Precipitation, hourly sum.                                                             | mm   | >=0         |
| {term}`pressure_air_sea_level`          | pred          | Reduced air pressure (reduced to sea level): calculated hourly value.                  | hPa  | >=0         |
| {term}`pressure_air_site`               | p             | Air pressure at station level, hourly measured value.                                  | hPa  | >=0         |
| {term}`radiation_global_intensity_mean` | cglo          | Global radiation, calibrated hourly mean value.                                        | W/m² | >=0         |
| {term}`snow_depth`                      | sh            | Total snow depth from snow gauge measurement, offset corrected.                        | cm   | >=0         |
| {term}`sunshine_duration`               | so_h          | Sunshine duration, hourly sum.                                                         | h    | >=0         |
| {term}`temperature_air_2m`              | tl            | Air temperature at 2 m height, hourly measured value                                   | °C   | -           |
| {term}`temperature_air_min_0_05m`       | tsmin         | Air temperature at 5 cm height, hourly minimum                                         | °C   | -           |
| {term}`temperature_soil_0_1m`           | tb10          | Soil temperature at 10 cm depth, hourly measured value                                 | °C   | -           |
| {term}`temperature_soil_0_2m`           | tb20          | Soil temperature at 20 cm depth, hourly measured value                                 | °C   | -           |
| {term}`temperature_soil_0_5m`           | tb50          | Soil temperature at 50 cm depth, hourly measured value                                 | °C   | -           |
| {term}`temperature_soil_1m`             | tb100         | Soil temperature at 100 cm depth, hourly measured value                                | °C   | -           |
| {term}`temperature_soil_2m`             | tb200         | Soil temperature at 200 cm depth, hourly measured value                                | °C   | -           |
| {term}`wind_direction_mean`             | dd            | Wind direction [360°], vector hourly mean value. The source's 0 (a calm wind) is null. | °    | >=0,<=360   |
| {term}`wind_direction_gust_max`         | ddx           | Wind direction of the maximum wind speed (peak gust), hourly value.                    | °    | >=0,<=360   |
| {term}`wind_gust_max`                   | ffx           | Maximum wind speed (peak gust), hourly maximum value.                                  | m/s  | >=0         |
| {term}`wind_speed_mean`                 | ff            | Wind speed, vector hourly mean value.                                                  | m/s  | >=0         |
