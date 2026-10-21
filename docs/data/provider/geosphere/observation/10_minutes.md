# 10_minutes

## metadata

| property      | value                                                        |
|---------------|--------------------------------------------------------------|
| name          | 10_minutes                                                   |
| original name | klima-v2-10min                                               |
| url           | [here](https://data.hub.geosphere.at/dataset/klima-v2-10min) |

## datasets

### data

#### metadata

| property      | value                                                                           |
|---------------|---------------------------------------------------------------------------------|
| name          | data                                                                            |
| original name | data                                                                            |
| description   | Historical 10-minute station observations for Austria, with quality information |
| access        | [here](https://data.hub.geosphere.at/dataset/klima-v2-10min)                    |

#### parameters

| name                                               | original name | description                                                                               | unit | constraints |
|----------------------------------------------------|---------------|-------------------------------------------------------------------------------------------|------|-------------|
| {term}`humidity_relative`                          | rf            | Relative humidity, 10-minute measured value.                                              | %    | >=0,<=100   |
| {term}`precipitation_duration`                     | rrm           | Precipitation duration, calculated from 1-minute precipitation detector data.             | min  | >=0         |
| {term}`precipitation_amount`                       | rr            | Precipitation sum, calculated from 1-minute precipitation data.                           | mm   | >=0         |
| {term}`pressure_air_sea_level`                     | pred          | Reduced air pressure (reduced to sea level): calculated 10-minute value.                  | hPa  | >=0         |
| {term}`pressure_air_site`                          | p             | Air pressure, 10-minute measured value.                                                   | hPa  | >=0         |
| {term}`radiation_global_intensity`                 | cglo          | Global radiation, calibrated, 10-minute mean value.                                       | W/m² | >=0         |
| {term}`radiation_sky_short_wave_diffuse_intensity` | chim          | Diffuse radiation, not quality-checked, calibrated, 10-minute mean value.                 | W/m² | >=0         |
| {term}`snow_depth`                                 | sh            | Total snow depth from snow gauge measurement, 10-minute mean value, offset corrected.     | cm   | >=0         |
| {term}`sunshine_duration`                          | so            | Sunshine duration in seconds, 10-minute sum.                                              | s    | >=0         |
| {term}`temperature_air_max_0_05m`                  | tsmax         | Air temperature at 5 cm height, 10-minute maximum value                                   | °C   | -           |
| {term}`temperature_air_max_2m`                     | tlmax         | Air temperature at 2 m height, 10-minute maximum value                                    | °C   | -           |
| {term}`temperature_air_0_05m`                      | ts            | Air temperature at 5 cm height, 10-minute measured value                                  | °C   | -           |
| {term}`temperature_air_2m`                         | tl            | Air temperature at 2 m height, 10-minute measured value                                   | °C   | -           |
| {term}`temperature_air_min_0_05m`                  | tsmin         | Air temperature at 5 cm height, 10-minute minimum value                                   | °C   | -           |
| {term}`temperature_air_min_2m`                     | tlmin         | Air temperature at 2 m height, 10-minute minimum value                                    | °C   | -           |
| {term}`temperature_soil_0_1m`                      | tb10          | Soil temperature at 10 cm depth, 10-minute measured value                                 | °C   | -           |
| {term}`temperature_soil_0_2m`                      | tb20          | Soil temperature at 20 cm depth, 10-minute measured value                                 | °C   | -           |
| {term}`temperature_soil_0_5m`                      | tb50          | Soil temperature at 50 cm depth, 10-minute measured value                                 | °C   | -           |
| {term}`wind_direction`                             | dd            | Wind direction [360°], vector 10-minute mean value. The source's 0 (a calm wind) is null. | °    | >=0,<=360   |
| {term}`wind_direction_gust_max`                    | ddx           | Wind direction of the maximum wind speed (peak gust) [360°].                              | °    | >=0,<=360   |
| {term}`wind_gust_max`                              | ffx           | Wind speed at 10 m height, 10-minute maximum value (peak gust).                           | m/s  | >=0         |
| {term}`wind_speed`                                 | ff            | Wind speed at 10 m height, vector 10-minute mean value.                                   | m/s  | >=0         |
| {term}`wind_speed_arithmetic`                      | ffam          | Wind speed at 10 m height, arithmetic 10-minute mean value.                               | m/s  | >=0         |
