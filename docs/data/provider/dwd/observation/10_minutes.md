# 10_minutes

## metadata

| property      | value                                                                                            |
|---------------|--------------------------------------------------------------------------------------------------|
| name          | 10_minutes                                                                                       |
| original name | 10_minutes                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/) |

## datasets

### precipitation

#### metadata

| property      | value                                                                                                                                                                                                                                    |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                                                                                                                                            |
| original name | precipitation                                                                                                                                                                                                                            |
| description   | 10-minute station observations of precipitation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/DESCRIPTION_obsgermany-climate-10min-precipitation_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/)                                                                                                                           |

#### parameters

| name                       | original name | description                                          | unit type     | unit          | constraints |
|----------------------------|---------------|------------------------------------------------------|---------------|---------------|-------------|
| precipitation_duration     | rws_dau_10    | duration of precipitation within the last 10 minutes | time          | min           | >=0         |
| precipitation_height       | rws_10        | precipitation height of the last 10 minutes          | precipitation | mm            | >=0         |
| precipitation_indicator_wr | rws_ind_10    | precipitation index                                  | dimensionless | -             | ∈ \[0,1,3\] |

Codes (precipitation_indicator_wr):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |

### solar

#### metadata

| property      | value                                                                                                                                                                                                                         |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | solar                                                                                                                                                                                                                         |
| original name | solar                                                                                                                                                                                                                         |
| description   | 10-minute station observations of solar and sunshine for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/solar/DESCRIPTION_obsgermany_climate_10min_solar_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/solar/)                                                                                                                        |

#### parameters

| name                             | original name | description                              | unit type       | unit          | constraints |
|----------------------------------|---------------|------------------------------------------|-----------------|---------------|-------------|
| radiation_sky_short_wave_diffuse | ds_10         | 10min-sum of diffuse solar radiation     | energy_per_area | J/cm²         | >=0         |
| radiation_global                 | gs_10         | 10min-sum of solar incoming radiation    | energy_per_area | J/cm²         | >=0         |
| sunshine_duration                | sd_10         | 10min-sum of sunshine duration           | time            | h             | >=0         |
| radiation_sky_long_wave          | ls_10         | 10min-sum of longwave downward radiation | energy_per_area | J/cm²         | >=0         |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                                                |
| original name | air_temperature                                                                                                                                                                                                                                |
| description   | 10-minute station observations of air temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/DESCRIPTION_obsgermany_climate_10min_air_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/)                                                                                                                               |

#### parameters

| name                          | original name | description                                                                                                                         | unit type   | unit          | constraints |
|-------------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------|-------------|---------------|-------------|
| pressure_air_site             | pp_10         | pressure at station height                                                                                                          | pressure    | hPa           | >=0         |
| temperature_air_mean_2m       | tt_10         | air temperature at 2m height                                                                                                        | temperature | °C            | -           |
| temperature_air_mean_0_05m    | tm5_10        | air temperature at 5cm height                                                                                                       | temperature | °C            | -           |
| humidity                      | rf_10         | relative humidity at 2m height                                                                                                      | fraction    | %             | >=0,<=100   |
| temperature_dew_point_mean_2m | td_10         | dew point temperature at 2m height, the dew point temperature is calculated from the temperature and relative humidity measurements | temperature | °C            | -           |

### temperature_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                                       |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_extreme                                                                                                                                                                                                                                         |
| original name | extreme_temperature                                                                                                                                                                                                                                         |
| description   | 10-minute station observations of extreme temperatures for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/DESCRIPTION_obsgermany_climate_10min_extreme_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/)                                                                                                                                        |

#### parameters

| name                      | original name | description                                                         | unit type   | unit          | constraints |
|---------------------------|---------------|---------------------------------------------------------------------|-------------|---------------|-------------|
| temperature_air_max_2m    | tx_10         | maximum of air temperature at 2m height during the last 10 minutes  | temperature | °C            | -           |
| temperature_air_max_0_05m | tx5_10        | maximum of air temperature at 5cm height during the last 10 minutes | temperature | °C            | -           |
| temperature_air_min_2m    | tn_10         | minimum of air temperature at 2m height during the last 10 minutes  | temperature | °C            | -           |
| temperature_air_min_0_05m | tn5_10        | minimum of air temperature at 5cm height during the last 10 minutes | temperature | °C            | -           |

### wind

#### metadata

| property      | value                                                                                                                                                                                                         |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind                                                                                                                                                                                                          |
| original name | wind                                                                                                                                                                                                          |
| description   | 10-minute station observations of wind for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/DESCRIPTION_obsgermany_climate_10min_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/)                                                                                                         |

#### parameters

| name           | original name | description                                       | unit type | unit          | constraints |
|----------------|---------------|---------------------------------------------------|-----------|---------------|-------------|
| wind_speed     | ff_10         | mean of wind speed during the last 10 minutes     | speed     | m/s           | >=0         |
| wind_direction | dd_10         | mean of wind direction during the last 10 minutes | angle     | °             | >=0,<=360   |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                 |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                                                          |
| original name | extreme_wind                                                                                                                                                                                                                          |
| description   | 10-minute station observations of extreme wind for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/DESCRIPTION_obsgermany_climate_10min_extreme_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/)                                                                                                                         |

#### parameters

| name                        | original name | description                                                                                                                                                                                                                                                    | unit type | unit          | constraints |
|-----------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|---------------|-------------|
| wind_gust_max               | fx_10         | maximum wind gust of the last 10 minutes, the instrument samples the instantaneous wind velocity every 0.25 seconds, and writes out the max value of a 3 second period, the highest occuring within the 10min interval is given here as the maximum wind gust. | speed     | m/s           | >=0         |
| wind_speed_min              | fnx_10        | minimum 10-minute mean wind velocity. The 10-minutes interval is moved in 10s steps over the last 20 minutes                                                                                                                                                   | speed     | m/s           | >=0         |
| wind_speed_rolling_mean_max | fmx_10        | maximum 10-minute mean wind velocity. The 10-minutes interval is moved in 10s steps over the last 20 minutes                                                                                                                                                   | speed     | m/s           | >=0         |
| wind_direction_gust_max     | dx_10         | wind direction of highest wind gust                                                                                                                                                                                                                            | angle     | °             | >=0,<=360   |
