# 10_minutes

## metadata

| property      | value |
|---------------|-------|
| name          | 10_minutes |
| original name | t |

## datasets

### data

#### metadata

| property      | value |
|---------------|-------|
| name          | data |
| original name | ogd-smn |
| grouped       | True |
| periods       | historical, recent, now |

#### parameters

| name                                               | original name | description                                                      | unit                  |
|----------------------------------------------------|---------------|------------------------------------------------------------------|-----------------------|
| {term}`wind_direction`                             | dkl010z0      | Wind direction; ten minutes mean                                 | degree                |
| {term}`wind_speed`                                 | fkl010z0      | Wind speed scalar; ten minutes mean in m/s                       | meter_per_second      |
| {term}`wind_gust_max`                              | fkl010z1      | Gust peak (one second); maximum in m/s                           | meter_per_second      |
| {term}`precipitation_height`                       | rre150z0      | Precipitation; ten minutes total                                 | millimeter            |
| {term}`pressure_air_site`                          | prestas0      | Atmospheric pressure at barometric altitude (QFE); current value | hectopascal           |
| {term}`pressure_air_sea_level`                     | pp0qffs0      | Atmospheric pressure reduced to sea level (QFF); current value   | hectopascal           |
| {term}`pressure_vapor`                             | pva200s0      | Vapour pressure 2 m above ground; current value                  | hectopascal           |
| {term}`radiation_global_intensity`                 | gre000z0      | Global radiation; ten minutes mean                               | watt_per_square_meter |
| {term}`radiation_sky_short_wave_diffuse_intensity` | ods000z0      | Diffuse radiation; ten minutes mean                              | watt_per_square_meter |
| {term}`radiation_sky_long_wave_intensity`          | oli000z0      | Longwave incoming radiation; ten minutes mean                    | watt_per_square_meter |
| {term}`sunshine_duration`                          | sre000z0      | Sunshine duration; ten minutes total                             | minute                |
| {term}`snow_depth`                                 | htoauts0      | Snow depth (automatic measurement); current value                | centimeter            |
| {term}`temperature_air_mean_2m`                    | tre200s0      | Air temperature 2 m above ground; current value                  | degree_celsius        |
| {term}`temperature_air_mean_0_05m`                 | tre005s0      | Air temperature at 5 cm above grass; current value               | degree_celsius        |
| {term}`temperature_soil_mean_0_05m`                | tso005s0      | Soil temperature at 5 cm depth; current value                    | degree_celsius        |
| {term}`temperature_soil_mean_0_1m`                 | tso010s0      | Soil temperature at 10 cm depth; current value                   | degree_celsius        |
| {term}`temperature_soil_mean_0_2m`                 | tso020s0      | Soil temperature at 20 cm depth; current value                   | degree_celsius        |
| {term}`humidity`                                   | ure200s0      | Relative air humidity 2 m above ground; current value            | percent               |
| {term}`temperature_dew_point_mean_2m`              | tde200s0      | Dew point 2 m above ground; current value                        | degree_celsius        |

