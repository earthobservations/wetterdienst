# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | d |

## datasets

### data

#### metadata

| property      | value |
|---------------|-------|
| name          | data |
| original name | ogd-smn |
| grouped       | True |
| periods       | historical, recent |

#### parameters

| name                                                   | original name | description                                                      | unit                  |
|--------------------------------------------------------|---------------|------------------------------------------------------------------|-----------------------|
| {term}`wind_direction`                                 | dkl010d0      | Wind direction; daily mean                                       | degree                |
| {term}`wind_speed`                                     | fkl010d0      | Wind speed scalar; daily mean in m/s                             | meter_per_second      |
| {term}`wind_gust_max`                                  | fkl010d1      | Gust peak (one second); daily maximum in m/s                     | meter_per_second      |
| {term}`precipitation_height`                           | rre150d0      | Precipitation; daily total 6 UTC - 6 UTC following day           | millimeter            |
| {term}`pressure_air_site`                              | prestad0      | Atmospheric pressure at barometric altitude (QFE); daily mean    | hectopascal           |
| {term}`pressure_air_sea_level`                         | pp0qffd0      | Atmospheric pressure reduced to sea level (QFF); daily mean      | hectopascal           |
| {term}`pressure_vapor`                                 | pva200d0      | Vapour pressure 2 m above ground; daily mean                     | hectopascal           |
| {term}`radiation_global_intensity`                     | gre000d0      | Global radiation; daily mean                                     | watt_per_square_meter |
| {term}`radiation_sky_short_wave_diffuse_intensity`     | ods000d0      | Diffuse radiation; daily mean                                    | watt_per_square_meter |
| {term}`radiation_sky_long_wave_intensity`              | oli000d0      | Longwave incoming radiation; daily mean                          | watt_per_square_meter |
| {term}`sunshine_duration`                              | sre000d0      | Sunshine duration; daily total                                   | minute                |
| {term}`snow_depth`                                     | htoautd0      | Snow depth (automatic measurement); morning measurement at 6 UTC | centimeter            |
| {term}`temperature_air_mean_2m`                        | tre200d0      | Air temperature 2 m above ground; daily mean                     | degree_celsius        |
| {term}`temperature_air_min_2m`                         | tre200dn      | Air temperature 2 m above ground; daily minimum                  | degree_celsius        |
| {term}`temperature_air_max_2m`                         | tre200dx      | Air temperature 2 m above ground; daily maximum                  | degree_celsius        |
| {term}`temperature_air_mean_0_05m`                     | tre005d0      | Air temperature at 5 cm above grass; daily mean                  | degree_celsius        |
| {term}`temperature_air_min_0_05m`                      | tre005dn      | Air temperature at 5 cm above grass; daily minimum               | degree_celsius        |
| {term}`temperature_air_max_0_05m`                      | tre005dx      | Air temperature at 5 cm above grass; daily maximum               | degree_celsius        |
| {term}`temperature_soil_mean_0_05m`                    | tso005d0      | Soil temperature at 5 cm depth; daily mean                       | degree_celsius        |
| {term}`temperature_soil_mean_0_1m`                     | tso010d0      | Soil temperature at 10 cm depth; daily mean                      | degree_celsius        |
| {term}`temperature_soil_mean_0_2m`                     | tso020d0      | Soil temperature at 20 cm depth; daily mean                      | degree_celsius        |
| {term}`humidity`                                       | ure200d0      | Relative air humidity 2 m above ground; daily mean               | percent               |
| {term}`evapotranspiration_potential_gras_fao_last_24h` | erefaod0      | Reference evaporation from FAO; daily total                      | millimeter            |

