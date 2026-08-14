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
| {term}`precipitation_height` | RR1 | Precipitation amount over 1 hour. | millimeter |
| {term}`temperature_air_min_2m` | TN | Minimum air temperature under shelter within the hour. | degree_celsius |
| {term}`temperature_air_max_2m` | TX | Maximum air temperature under shelter within the hour. | degree_celsius |
| {term}`temperature_air_mean_2m` | T | Instantaneous air temperature under shelter. | degree_celsius |
| {term}`wind_speed` | FF | Wind force averaged over 10 minutes, measured at 10 m. | meter_per_second |
| {term}`wind_direction` | DD | Direction of FF, on the 360 degree compass. | degree |
| {term}`wind_gust_max` | FXY | Maximum value of FF within the hour. | meter_per_second |
| {term}`wind_direction_gust_max` | DXY | Direction of FXY, on the 360 degree compass. | degree |

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
| {term}`temperature_dew_point_mean_2m` | TD | Dew point temperature. | degree_celsius |
| {term}`humidity` | U | Relative humidity. | percent |
| {term}`pressure_air_sea_level` | PMER | Sea level pressure, only for stations at an altitude of 750 m or less. | hectopascal |
| {term}`pressure_air_site` | PSTAT | Station pressure. | hectopascal |
| {term}`cloud_cover_total` | N | Total cloud amount, in octas. 9 means the sky was invisible through fog or another weather phenomenon. | one_eighth |
| {term}`visibility_range` | VV | Visibility. | meter |
| {term}`radiation_global` | GLO | Hourly global radiation, in UTC hours. | joule_per_square_centimeter |
| {term}`sunshine_duration` | INS | Hourly sunshine duration, in UTC hours. | minute |
