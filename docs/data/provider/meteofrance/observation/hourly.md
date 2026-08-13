# hourly

## metadata

| property      | value |
|---------------|-------|
| name          | hourly |
| original name | horaires |

## datasets

### core

#### metadata

| property      | value |
|---------------|-------|
| name          | core |
| original name | core |
| grouped       | True |
| periods       | historical, recent |

#### parameters

| name                            | original name | description                                                    | unit             |
|---------------------------------|---------------|----------------------------------------------------------------|------------------|
| {term}`precipitation_height`    | RR1           | Depth of precipitation collected over the period.              | millimeter       |
| {term}`temperature_air_min_2m`  | TN            | Minimum air temperature at 2 m above ground.                   | degree_celsius   |
| {term}`temperature_air_max_2m`  | TX            | Maximum air temperature at 2 m above ground.                   | degree_celsius   |
| {term}`temperature_air_mean_2m` | T             | Mean air temperature at 2 m above ground.                      | degree_celsius   |
| {term}`wind_speed`              | FF            | Mean speed of the wind over the period.                        | meter_per_second |
| {term}`wind_direction`          | DD            | Direction the wind is blowing from, clockwise from true north. | degree           |
| {term}`wind_gust_max`           | FXY           | Speed of the strongest gust of the period.                     | meter_per_second |
| {term}`wind_direction_gust_max` | DXY           | Direction the strongest gust of the period blew from.          | degree           |

### others

#### metadata

| property      | value |
|---------------|-------|
| name          | others |
| original name | others |
| grouped       | True |
| periods       | historical, recent |

#### parameters

| name                                  | original name | description                                                                                   | unit                        |
|---------------------------------------|---------------|-----------------------------------------------------------------------------------------------|-----------------------------|
| {term}`temperature_dew_point_mean_2m` | TD            | Dew point at 2 m above ground, the temperature at which the air would become saturated.       | degree_celsius              |
| {term}`humidity`                      | U             | Relative humidity of the air, the fraction of the moisture it could hold at that temperature. | percent                     |
| {term}`pressure_air_sea_level`        | PMER          | Air pressure reduced to mean sea level, so that stations at different heights compare.        | hectopascal                 |
| {term}`pressure_air_site`             | PSTAT         | Air pressure as measured at station height.                                                   | hectopascal                 |
| {term}`cloud_cover_total`             | N             | Fraction of the sky covered by cloud of any kind.                                             | one_eighth                  |
| {term}`visibility_range`              | VV            | Horizontal distance at which an object can still be made out.                                 | meter                       |
| {term}`radiation_global`              | GLO           | Global radiation received on a horizontal surface, accumulated as energy over the interval.   | joule_per_square_centimeter |
| {term}`sunshine_duration`             | INS           | Length of time the sun shone unobstructed.                                                    | minute                      |
