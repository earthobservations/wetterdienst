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

| name              | original name | description       | unit type     | unit          | constraints |
|-------------------|---------------|-------------------|---------------|---------------|-------------|
| cloud_cover_total | n_ter         | total cloud cover | fraction      | 1/8           | >=0,<=8     |
| cloud_density     | cd_ter        | cloud density     | dimensionless | -             |             |

### moisture

#### metadata

| property      | value                                                                                                                                                                                                                                                                                 |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | moisture                                                                                                                                                                                                                                                                              |
| original name | moisture                                                                                                                                                                                                                                                                              |
| description   | Recent subdaily vapor pressure, mean temperature in 2m height, mean temperature in 5cm height and humidity of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/moisture/)                                                                                                                                                                               |

#### parameters

| name                       | original name | description         | unit type   | unit          | constraints |
|----------------------------|---------------|---------------------|-------------|---------------|-------------|
| pressure_vapor             | vp_ter        | vapor pressure      | pressure    | hPa           | >=0         |
| temperature_air_mean_0_05m | e_tf_ter      | 5cm air temperature | temperature | °C            |             |
| temperature_air_mean_2m    | tf_ter        | 2m air temperature  | temperature | °C            |             |
| humidity                   | rf_ter        | humidity            | fraction    | %             | >=0,<=100   |

### pressure

#### metadata

| property      | value                                                                                                                                                                                                  |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | pressure                                                                                                                                                                                               |
| original name | pressure                                                                                                                                                                                               |
| description   | Recent air pressure at site of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/pressure/)                                                                                                |

#### parameters

| name              | original name | description          | unit type | unit          | constraints |
|-------------------|---------------|----------------------|-----------|---------------|-------------|
| pressure_air_site | pp_ter        | air pressure of site | pressure  | hPa           | >=0         |

### soil

#### metadata

| property      | value                                                                                                                                                                                                           |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | soil                                                                                                                                                                                                            |
| original name | soil                                                                                                                                                                                                            |
| description   | Recent soil temperature in 5cm depth of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/soil/)                                                                                                             |

#### parameters

| name                        | original name | description          | unit type   | unit          | constraints |
|-----------------------------|---------------|----------------------|-------------|---------------|-------------|
| temperature_soil_mean_0_05m | ek_ter        | soil temperature 5cm | temperature | °C            | -           |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                   |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                         |
| original name | air_temperature                                                                                                                                                                                                         |
| description   | Recent subdaily air temperature and humidity of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/air_temperature/)                                                                                                          |

#### parameters

| name                    | original name | description          | unit type   | unit          | constraints |
|-------------------------|---------------|----------------------|-------------|---------------|-------------|
| temperature_air_mean_2m | tt_ter        | 2m air temperature   | temperature | °C            |             |
| humidity                | rf_ter        | 2m relative humidity | fraction    | %             | >=0,<=100   |

### visibility

#### metadata

| property      | value                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | visibility                                                                                                                                                                                         |
| original name | visibility                                                                                                                                                                                         |
| description   | Recent visibility range of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/visibility/)                                                                                          |

#### parameters

| name             | original name | description      | unit type     | unit          | constraints |
|------------------|---------------|------------------|---------------|---------------|-------------|
| visibility_range | vk_ter        | visibility range | length_medium | m             | >=0         |

### wind

#### metadata

| property      | value                                                                                                                                                                                                                      |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind                                                                                                                                                                                                                       |
| original name | wind                                                                                                                                                                                                                       |
| description   | Recent wind direction and wind force (beaufort) of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/wind/)                                                                                                                        |

#### parameters

| name                | original name | description           | unit type  | unit          | constraints |
|---------------------|---------------|-----------------------|------------|---------------|-------------|
| wind_direction      | dk_ter        | wind direction        | angle      | °             | >=0,<=360   |
| wind_force_beaufort | fk_ter        | wind force (beaufort) | wind_scale | Bft           | >=0         |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                            |
| original name | extreme_wind                                                                                                                                                                                            |
| description   | Recent subdaily extreme wind of stations in Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/extreme_wind/)                                                                                             |

#### parameters

| name                  | original name | description      | unit type | unit          | constraints |
|-----------------------|---------------|------------------|-----------|---------------|-------------|
| wind_gust_max_last_3h | fx_911_3      | wind gust max 3h | speed     | m/s           | >=0         |
| wind_gust_max_last_6h | fx_911_6      | wind gust max 6h | speed     | m/s           | >=0         |
