# hourly

## metadata

| property      | value |
|---------------|-------|
| name          | hourly |
| original name | h |

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

| name                                               | original name | description                                                    | unit                  |
|----------------------------------------------------|---------------|----------------------------------------------------------------|-----------------------|
| {term}`wind_direction`                             | dkl010h0      | Wind direction; hourly mean                                    | degree                |
| {term}`wind_speed`                                 | fkl010h0      | Wind speed scalar; hourly mean in m/s                          | meter_per_second      |
| {term}`wind_gust_max`                              | fkl010h1      | Gust peak (one second); hourly maximum in m/s                  | meter_per_second      |
| {term}`precipitation_height`                       | rre150h0      | Precipitation; hourly total                                    | millimeter            |
| {term}`pressure_air_site`                          | prestah0      | Atmospheric pressure at barometric altitude (QFE); hourly mean | hectopascal           |
| {term}`pressure_air_sea_level`                     | pp0qffh0      | Atmospheric pressure reduced to sea level (QFF); hourly mean   | hectopascal           |
| {term}`pressure_vapor`                             | pva200h0      | Vapour pressure 2 m above ground; hourly mean                  | hectopascal           |
| {term}`radiation_global_intensity`                 | gre000h0      | Global radiation; hourly mean                                  | watt_per_square_meter |
| {term}`radiation_sky_short_wave_diffuse_intensity` | ods000h0      | Diffuse radiation; hourly mean                                 | watt_per_square_meter |
| {term}`radiation_sky_long_wave_intensity`          | oli000h0      | Longwave incoming radiation; hourly mean                       | watt_per_square_meter |
| {term}`sunshine_duration`                          | sre000h0      | Sunshine duration; hourly total                                | minute                |
| {term}`snow_depth`                                 | htoauths      | Snow depth (automatic measurement); hourly current value       | centimeter            |
| {term}`temperature_air_mean_2m`                    | tre200h0      | Air temperature 2 m above ground; hourly mean                  | degree_celsius        |
| {term}`temperature_air_min_2m`                     | tre200hn      | Air temperature 2 m above ground; hourly minimum               | degree_celsius        |
| {term}`temperature_air_max_2m`                     | tre200hx      | Air temperature 2 m above ground; hourly maximum               | degree_celsius        |
| {term}`temperature_air_mean_0_05m`                 | tre005h0      | Air temperature at 5 cm above grass; hourly mean               | degree_celsius        |
| {term}`temperature_air_min_0_05m`                  | tre005hn      | Air temperature at 5 cm above grass; hourly minimum            | degree_celsius        |
| {term}`temperature_soil_mean_0_05m`                | tso005hs      | Soil temperature at 5 cm depth; hourly current value           | degree_celsius        |
| {term}`temperature_soil_mean_0_1m`                 | tso010hs      | Soil temperature at 10 cm depth; hourly current value          | degree_celsius        |
| {term}`temperature_soil_mean_0_2m`                 | tso020hs      | Soil temperature at 20 cm depth; hourly current value          | degree_celsius        |
| {term}`humidity`                                   | ure200h0      | Relative air humidity 2 m above ground; hourly mean            | percent               |
| {term}`temperature_dew_point_mean_2m`              | tde200h0      | Dew point 2 m above ground; hourly mean                        | degree_celsius        |

