# subdaily

## metadata

| property      | value                                                                                          |
|---------------|------------------------------------------------------------------------------------------------|
| name          | subdaily                                                                                       |
| original name | subdaily                                                                                       |
| description   | Three fixed observation times a day: until March 2001 at 07, 14 and 21 (local mean time; from 1987 07:30, 14:30 and 21:30 CET, which the files stamp as 07, 14 and 21), from April 2001 at 06, 12 and 18 UTC (some stations also at 00 UTC; East German stations 1960-1990 at 00, 06, 12 and 18 UTC); the extreme wind at 03, 09, 15 and 21 UTC (3-hour maximum) and 00, 06, 12 and 18 UTC (6-hour maximum). |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/) |

## datasets

### cloudiness

#### metadata

| property      | value                                                                                                                                                                                                                    |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | cloudiness                                                                                                                                                                                                               |
| original name | cloudiness                                                                                                                                                                                                               |
| description   | Subdaily cloud cover and cloud density of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/cloudiness/)                                                                                                                |

#### parameters

| name                      | original name | description       | unit | constraints |
|---------------------------|---------------|-------------------|------|-------------|
| {term}`quality` | qn_4 | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`cloud_cover_total` | n_ter | Total cloud cover. | 1/8 | >=0,<=8 |
| {term}`cloud_density` | cd_ter | Cloud density. | - | - |

### moisture

#### metadata

| property      | value                                                                                                                                                                                                                                                                                 |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | moisture                                                                                                                                                                                                                                                                              |
| original name | moisture                                                                                                                                                                                                                                                                              |
| description   | Subdaily vapor pressure, wet bulb temperature, ice on the wet bulb thermometer and relative humidity of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/moisture/)                                                                                                                                                                               |

#### parameters

| name                               | original name | description         | unit | constraints |
|------------------------------------|---------------|---------------------|------|-------------|
| {term}`quality` | qn_4 | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`pressure_vapor` | vp_ter | Vapor pressure. | hPa | >=0 |
| {term}`temperature_wet_ice_formation` | e_tf_ter | Ice on the wet bulb thermometer. | - | - |
| {term}`temperature_wet_2m`         | tf_ter        | 2m wet bulb temperature | °C | -         |
| {term}`humidity_relative` | rf_ter | 2m relative humidity. | % | >=0,<=100 |

### pressure

#### metadata

| property      | value                                                                                                                                                                                                  |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | pressure                                                                                                                                                                                               |
| original name | pressure                                                                                                                                                                                               |
| description   | Air pressure at site of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/pressure/)                                                                                                |

#### parameters

| name                      | original name | description          | unit | constraints |
|---------------------------|---------------|----------------------|------|-------------|
| {term}`quality` | qn_4 | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`pressure_air_site` | pp_ter | Air pressure of site. | hPa | >=0 |

### soil

#### metadata

| property      | value                                                                                                                                                                                                           |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | soil                                                                                                                                                                                                            |
| original name | soil                                                                                                                                                                                                            |
| description   | Subdaily coded ground state of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/soil/)                                                                                                             |

#### parameters

| name                                | original name | description          | unit | constraints |
|-------------------------------------|---------------|----------------------|------|-------------|
| {term}`quality` | qn_4 | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`soil_state_index` | ek_ter | Coded ground state. | - | - |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                   |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                         |
| original name | air_temperature                                                                                                                                                                                                         |
| description   | Subdaily air temperature and humidity of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/air_temperature/)                                                                                                          |

#### parameters

| name                            | original name | description          | unit | constraints |
|---------------------------------|---------------|----------------------|------|-------------|
| {term}`temperature_air_2m`      | tt_ter        | 2m air temperature   | °C   | -           |
| {term}`humidity_relative`       | rf_ter        | 2m relative humidity | %    | >=0,<=100   |

### visibility

#### metadata

| property      | value                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | visibility                                                                                                                                                                                         |
| original name | visibility                                                                                                                                                                                         |
| description   | Visibility range of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/visibility/)                                                                                          |

#### parameters

| name                     | original name | description      | unit | constraints |
|--------------------------|---------------|------------------|------|-------------|
| {term}`visibility_index` | vk_ter | Coded visibility class. | - | >=0 |

### wind

#### metadata

| property      | value                                                                                                                                                                                                                      |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind                                                                                                                                                                                                                       |
| original name | wind                                                                                                                                                                                                                       |
| description   | Wind direction and wind force (beaufort) of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/wind/)                                                                                                                        |

#### parameters

| name                        | original name | description           | unit | constraints |
|-----------------------------|---------------|-----------------------|------|-------------|
| {term}`wind_direction` | dk_ter | Wind direction. The source gives the point of a 32-point wind rose (32 is north), returned in degrees. The source's 0 beside a wind force of 0 (a calm wind) is null; a 0 beside a wind that blows stays. | ° | >=0,<=360 |
| {term}`wind_force_beaufort` | fk_ter | Wind force (beaufort). | Bft | >=0 |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                            |
| original name | extreme_wind                                                                                                                                                                                            |
| description   | Subdaily extreme wind of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/extreme_wind/)                                                                                             |

#### parameters

| name                          | original name | description      | unit | constraints |
|-------------------------------|---------------|------------------|------|-------------|
| {term}`quality_3` | qn_8_3 | Quality flag for the 3-hourly maximum wind gust reported in the same dataset. | -             | - |
| {term}`wind_gust_max_last_3h` | fx_911_3 | Highest wind peak of the last 3 hours; DWD's list adds "(>12,5 m/s)". | m/s | >=0 |
| {term}`quality_6` | qn_8_6 | Quality flag for the 6-hourly maximum wind gust reported in the same dataset. | -             | - |
| {term}`wind_gust_max_last_6h` | fx_911_6 | Highest wind peak of the last 6 hours; DWD's list adds "(>12,5 m/s)". | m/s | >=0 |
