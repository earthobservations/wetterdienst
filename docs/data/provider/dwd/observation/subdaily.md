# subdaily

## metadata

| property      | value                                                                                          |
|---------------|------------------------------------------------------------------------------------------------|
| name          | subdaily                                                                                       |
| original name | subdaily                                                                                       |
| description   | measurements at 7am, 2pm, 9pm                                                                  |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/) |

## datasets

### cloudiness

#### metadata

| property      | value                                                                                                                                                                                                                    |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | cloudiness                                                                                                                                                                                                               |
| original name | cloudiness                                                                                                                                                                                                               |
| description   | Recent subdaily cloud cover and cloud density of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/cloudiness/)                                                                                                                |

#### parameters

| name                      | original name | description       | unit | constraints |
|---------------------------|---------------|-------------------|------|-------------|
| {term}`cloud_cover_total` | n_ter         | total cloud cover | 1/8  | >=0,<=8     |
| {term}`cloud_density`     | cd_ter        | cloud density     | -    |             |

### moisture

#### metadata

| property      | value                                                                                                                                                                                                                                                                                 |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | moisture                                                                                                                                                                                                                                                                              |
| original name | moisture                                                                                                                                                                                                                                                                              |
| description   | Recent subdaily vapor pressure, mean temperature in 2m height, mean temperature in 5cm height and humidity of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/moisture/)                                                                                                                                                                               |

#### parameters

| name                               | original name | description         | unit | constraints |
|------------------------------------|---------------|---------------------|------|-------------|
| {term}`pressure_vapor`             | vp_ter        | vapor pressure      | hPa  | >=0         |
| {term}`temperature_air_mean_0_05m` | e_tf_ter      | 5cm air temperature | °C   |             |
| {term}`temperature_air_mean_2m`    | tf_ter        | 2m air temperature  | °C   |             |
| {term}`humidity`                   | rf_ter        | humidity            | %    | >=0,<=100   |

### pressure

#### metadata

| property      | value                                                                                                                                                                                                  |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | pressure                                                                                                                                                                                               |
| original name | pressure                                                                                                                                                                                               |
| description   | Recent air pressure at site of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/pressure/)                                                                                                |

#### parameters

| name                      | original name | description          | unit | constraints |
|---------------------------|---------------|----------------------|------|-------------|
| {term}`pressure_air_site` | pp_ter        | air pressure of site | hPa  | >=0         |

### soil

#### metadata

| property      | value                                                                                                                                                                                                           |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | soil                                                                                                                                                                                                            |
| original name | soil                                                                                                                                                                                                            |
| description   | Recent soil temperature in 5cm depth of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/soil/)                                                                                                             |

#### parameters

| name                                | original name | description          | unit | constraints |
|-------------------------------------|---------------|----------------------|------|-------------|
| {term}`temperature_soil_mean_0_05m` | ek_ter        | soil temperature 5cm | °C   | -           |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                   |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                         |
| original name | air_temperature                                                                                                                                                                                                         |
| description   | Recent subdaily air temperature and humidity of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/air_temperature/)                                                                                                          |

#### parameters

| name                            | original name | description          | unit | constraints |
|---------------------------------|---------------|----------------------|------|-------------|
| {term}`temperature_air_mean_2m` | tt_ter        | 2m air temperature   | °C   |             |
| {term}`humidity`                | rf_ter        | 2m relative humidity | %    | >=0,<=100   |

### visibility

#### metadata

| property      | value                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | visibility                                                                                                                                                                                         |
| original name | visibility                                                                                                                                                                                         |
| description   | Recent visibility range of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/visibility/)                                                                                          |

#### parameters

| name                     | original name | description      | unit | constraints |
|--------------------------|---------------|------------------|------|-------------|
| {term}`visibility_range` | vk_ter        | visibility range | m    | >=0         |

### wind

#### metadata

| property      | value                                                                                                                                                                                                                      |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind                                                                                                                                                                                                                       |
| original name | wind                                                                                                                                                                                                                       |
| description   | Recent wind direction and wind force (beaufort) of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/wind/)                                                                                                                        |

#### parameters

| name                        | original name | description           | unit | constraints |
|-----------------------------|---------------|-----------------------|------|-------------|
| {term}`wind_direction`      | dk_ter        | wind direction        | °    | >=0,<=360   |
| {term}`wind_force_beaufort` | fk_ter        | wind force (beaufort) | Bft  | >=0         |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                            |
| original name | extreme_wind                                                                                                                                                                                            |
| description   | Recent subdaily extreme wind of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/extreme_wind/)                                                                                             |

#### parameters

| name                          | original name | description      | unit | constraints |
|-------------------------------|---------------|------------------|------|-------------|
| {term}`wind_gust_max_last_3h` | fx_911_3      | wind gust max 3h | m/s  | >=0         |
| {term}`wind_gust_max_last_6h` | fx_911_6      | wind gust max 6h | m/s  | >=0         |
