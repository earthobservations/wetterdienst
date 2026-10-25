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

| name                                | original name    | description                                                                                                                                                               | unit  |
|-------------------------------------|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|
| {term}`temperature_air_mean_2m`     | temperatura      | Air temperature recorded at 1.5 m height, hourly mean.                                                                                                                    | °C    |
| {term}`humidity_relative_mean`      | humidade         | Relative humidity of the air recorded at 1.5 m height, hourly mean.                                                                                                       | %     |
| {term}`pressure_air_sea_level_mean` | pressao          | Atmospheric pressure reduced to mean sea level (NMM), hourly mean.                                                                                                        | hPa   |
| {term}`wind_speed`                  | intensidadeVento | Wind speed recorded at 10 m height. The source states no statistic and no period.                                                                                         | m/s   |
| {term}`wind_direction`              | idDireccVento    | Class of the predominant wind direction recorded at 10 m height ("classe do rumo do vento"): 0 no direction, 1 or 9 north, 2 north-east, 3 east, 4 south-east, 5 south, 6 south-west, 7 west, 8 north-west, returned as degrees (45 to 360, north being 360 as for every provider, never 0). The code 0 (sem rumo) is returned as null, whether the wind blows or not. The source states no period. | °     |
| {term}`precipitation_amount`        | precAcumulada    | Precipitation recorded at 1.5 m height, accumulated over the hour (the source's valor acumulado da hora).                                                                 | mm    |
| {term}`radiation_global`            | radiacao         | Solar radiation (radiação solar) in kJ/m². The source states neither a period nor that it is global or on a horizontal surface; the daily course suggests an energy accumulated over the hour, though the highest values exceed what one hour delivers at the top of the atmosphere. | kJ/m² |
