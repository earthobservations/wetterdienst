# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | hourly |

## datasets

### data

#### metadata

| property      | value |
|---------------|-------|
| name          | data  |
| original name | data  |

#### parameters

| name                            | original name    | description                                                                                                                                                               | unit  |
|---------------------------------|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|
| {term}`temperature_air_mean_2m` | temperatura      | Air temperature recorded at 1.5 m height, hourly mean.                                                                                                                    | °C    |
| {term}`humidity_relative`       | humidade         | Relative humidity of the air, the fraction of the moisture it could hold at that temperature.                                                                             | %     |
| {term}`pressure_air_sea_level`  | pressao          | Air pressure reduced to mean sea level, so that stations at different heights compare.                                                                                    | hPa   |
| {term}`wind_speed`              | intensidadeVento | Speed of the wind where the source states no statistic or a reading at one moment; the stated mean over the interval is `wind_speed_mean`.                                | m/s   |
| {term}`wind_direction`          | idDireccVento    | Direction the wind is blowing from, clockwise from true north, where the source states no statistic or a reading at one moment; the stated mean is `wind_direction_mean`. | °     |
| {term}`precipitation_amount`    | precAcumulada    | Depth of precipitation collected over the period.                                                                                                                         | mm    |
| {term}`radiation_global`        | radiacao         | Global radiation received on a horizontal surface, accumulated as energy over the interval.                                                                               | kJ/m² |
