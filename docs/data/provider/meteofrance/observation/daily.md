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
| {term}`precipitation_height` | RR | Precipitation amount over 24 hours, from 06h UTC on day J to 06h UTC on day J+1. The value recorded at J+1 is attributed to day J. | millimeter |
| {term}`temperature_air_min_2m` | TN | Minimum air temperature under shelter. | degree_celsius |
| {term}`temperature_air_max_2m` | TX | Maximum air temperature under shelter. | degree_celsius |
| {term}`temperature_air_mean_2m` | TM | Daily mean of the hourly air temperatures under shelter. | degree_celsius |
| {term}`wind_speed` | FFM | Daily mean of the wind force averaged over 10 minutes, at 10 m. | meter_per_second |
| {term}`wind_gust_max` | FXI | Daily maximum of the hourly maximum instantaneous wind force, at 10 m. | meter_per_second |
| {term}`wind_direction_gust_max` | DXI | Direction of FXI, on the 360 degree compass. | degree |

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
| {term}`pressure_air_sea_level` | PMERM | Daily mean of the hourly sea level pressures. | hectopascal |
| {term}`pressure_vapor` | TSVM | Mean vapour pressure. | hectopascal |
| {term}`sunshine_duration` | INST | Daily sunshine duration. | minute |
| {term}`radiation_global` | GLOT | Daily global radiation. | joule_per_square_centimeter |
| {term}`humidity` | UM | Daily mean of the hourly relative humidities. | percent |
| {term}`snow_depth` | NEIGETOT06 | Total depth of snow on the ground measured at 06h. | centimeter |
| {term}`snow_depth_new` | HNEIGEF | Depth of fresh snow fallen over 24 hours, from 06h UTC on day J to 06h UTC on day J+1, that remains on the ground at 06h UTC. | centimeter |

