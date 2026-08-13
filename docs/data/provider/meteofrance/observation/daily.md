# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | quot |

## datasets

### core

#### metadata

| property      | value |
|---------------|-------|
| name          | core |
| original name | RR-T-Vent |
| grouped       | True |
| periods       | historical, recent |

#### parameters

| name                            | original name | description                                           | unit             |
|---------------------------------|---------------|-------------------------------------------------------|------------------|
| {term}`precipitation_height`    | RR            | Depth of precipitation collected over the period.     | millimeter       |
| {term}`temperature_air_min_2m`  | TN            | Minimum air temperature at 2 m above ground.          | degree_celsius   |
| {term}`temperature_air_max_2m`  | TX            | Maximum air temperature at 2 m above ground.          | degree_celsius   |
| {term}`temperature_air_mean_2m` | TM            | Mean air temperature at 2 m above ground.             | degree_celsius   |
| {term}`wind_speed`              | FFM           | Mean speed of the wind over the period.               | meter_per_second |
| {term}`wind_gust_max`           | FXI           | Speed of the strongest gust of the period.            | meter_per_second |
| {term}`wind_direction_gust_max` | DXI           | Direction the strongest gust of the period blew from. | degree           |

### others

#### metadata

| property      | value |
|---------------|-------|
| name          | others |
| original name | autres-parametres |
| grouped       | True |
| periods       | historical, recent |

#### parameters

| name                           | original name | description                                                                                   | unit                        |
|--------------------------------|---------------|-----------------------------------------------------------------------------------------------|-----------------------------|
| {term}`pressure_air_sea_level` | PMERM         | Air pressure reduced to mean sea level, so that stations at different heights compare.        | hectopascal                 |
| {term}`pressure_vapor`         | TSVM          | Partial pressure of water vapour in the air.                                                  | hectopascal                 |
| {term}`sunshine_duration`      | INST          | Length of time the sun shone unobstructed.                                                    | minute                      |
| {term}`radiation_global`       | GLOT          | Global radiation received on a horizontal surface, accumulated as energy over the interval.   | joule_per_square_centimeter |
| {term}`humidity`               | UM            | Relative humidity of the air, the fraction of the moisture it could hold at that temperature. | percent                     |
| {term}`snow_depth`             | NEIGETOT06    | Depth of the snow lying on the ground.                                                        | centimeter                  |
| {term}`snow_depth_new`         | HNEIGEF       | Depth of snow that fell during the period.                                                    | centimeter                  |

