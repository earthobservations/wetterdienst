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

| name                           | original name | description                                          | unit | constraints |
|--------------------------------|---------------|------------------------------------------------------|------|-------------|
| {term}`precipitation_duration` | rws_dau_10 | Duration of precipitation during the previous 10 minutes. | min | >=0 |
| {term}`precipitation_height` | rws_10 | Sum of the precipitation height of the previous 10 minutes. | mm | >=0 |
| {term}`precipitation_index` | rws_ind_10 | Indicator of precipitation; if QN = 1 then: 0 = no precipitation, permanent sensor installed; 1 = precipitation, permanent sensor installed; 2 = no precipitation, heating in operation, permanent sensor installed; 3 = precipitation, heating in operation, permanent sensor installed; if QN > 1 then: 0 = no precipitation; 1 = precipitation. | - | ∈ \[0,1,3\] |

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

| name                                     | original name | description                              | unit  | constraints |
|------------------------------------------|---------------|------------------------------------------|-------|-------------|
| {term}`radiation_sky_short_wave_diffuse` | ds_10 | Sum of diffuse sky radiation during the previous 10 minutes. | J/cm² | >=0 |
| {term}`radiation_global` | gs_10 | Sum of global radiation during the previous 10 minutes. | J/cm² | >=0 |
| {term}`sunshine_duration` | sd_10 | Sum of sunshine duration during the previous 10 minutes. | h | >=0 |
| {term}`radiation_sky_long_wave` | ls_10 | Sum of longwave radiation during the previous 10 minutes. | J/cm² | >=0 |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                                                |
| original name | air_temperature                                                                                                                                                                                                                                |
| description   | 10-minute station observations of air temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/DESCRIPTION_obsgermany_climate_10min_air_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/)                                                                                                                               |

#### parameters

| name                                  | original name | description                                                                                                                         | unit | constraints |
|---------------------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`pressure_air_site` | pp_10 | Air pressure at station altitude. | hPa | >=0 |
| {term}`temperature_air_mean_2m` | tt_10 | Air temperature 2 m above ground, instant. | °C | - |
| {term}`temperature_air_mean_0_05m` | tm5_10 | Air temperature 5 cm above ground, instant. | °C | - |
| {term}`humidity` | rf_10 | Relative humidity 2 m above ground. | % | >=0,<=100 |
| {term}`temperature_dew_point_mean_2m` | td_10 | Dew point. The dew point temperature is calculated from the air temperature 2 m above ground and the relative humidity measurement. | °C | - |

### temperature_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                                       |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_extreme                                                                                                                                                                                                                                         |
| original name | extreme_temperature                                                                                                                                                                                                                                         |
| description   | 10-minute station observations of extreme temperatures for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/DESCRIPTION_obsgermany_climate_10min_extreme_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/)                                                                                                                                        |

#### parameters

| name                              | original name | description                                                         | unit | constraints |
|-----------------------------------|---------------|---------------------------------------------------------------------|------|-------------|
| {term}`temperature_air_max_2m` | tx_10 | Maximum of air temperature at 2 m height during the last 10 minutes. | °C | - |
| {term}`temperature_air_max_0_05m` | tx5_10 | Maximum of air temperature at 5 cm height during the last 10 minutes. | °C | - |
| {term}`temperature_air_min_2m` | tn_10 | Minimum of air temperature at 2 m height during the last 10 minutes. | °C | - |
| {term}`temperature_air_min_0_05m` | tn5_10 | Minimum of air temperature at 5 cm height during the last 10 minutes. | °C | - |

### wind

#### metadata

| property      | value                                                                                                                                                                                                         |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind                                                                                                                                                                                                          |
| original name | wind                                                                                                                                                                                                          |
| description   | 10-minute station observations of wind for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/DESCRIPTION_obsgermany_climate_10min_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/)                                                                                                         |

#### parameters

| name                   | original name | description                                       | unit | constraints |
|------------------------|---------------|---------------------------------------------------|------|-------------|
| {term}`wind_speed` | ff_10 | Mean wind speed during the previous 10 minutes. | m/s | >=0 |
| {term}`wind_direction` | dd_10 | Mean wind direction during the previous 10 minutes. | ° | >=0,<=360 |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                 |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                                                          |
| original name | extreme_wind                                                                                                                                                                                                                          |
| description   | 10-minute station observations of extreme wind for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/DESCRIPTION_obsgermany_climate_10min_extreme_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/)                                                                                                                         |

#### parameters

| name                                | original name | description                                                                                                                                                                                                                                                     | unit | constraints |
|-------------------------------------|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`wind_gust_max` | fx_10 | Maximum wind gust during the previous 10 minutes. The instrument samples the instantaneous wind speed every 0.25 seconds and writes out the maximum of each 3 second period; the highest occurring within the interval is reported. | m/s | >=0 |
| {term}`wind_speed_min` | fnx_10 | Minimum 10-minute mean wind speed. The 10-minute interval is moved in 10 s steps over the previous 20 minutes. | m/s | >=0 |
| {term}`wind_speed_rolling_mean_max` | fmx_10 | Maximum of the wind speed from the 1 minute mean values of the 3-second maxima of the previous 10 minutes. | m/s | >=0 |
| {term}`wind_direction_gust_max` | dx_10 | Wind direction of the maximum wind speed during the previous 10 minutes. | ° | >=0,<=360 |

### urban_precipitation

#### metadata

| property      | value                                                                                                                                                                                                                    |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_precipitation                                                                                                                                                                                                      |
| original name | precipitation (climate_urban)                                                                                                                                                                                            |
| description   | Recent 10-minute precipitation, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/precipitation/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/precipitation/)                                                                                                     |

#### parameters

| name                         | original name | description                                 | unit | constraints |
|------------------------------|---------------|---------------------------------------------|------|-------------|
| {term}`precipitation_height` | rr_st_10 | Precipitation height of the last 10 minutes. | mm | >=0 |

### urban_pressure

#### metadata

| property      | value                                                                                                                                                                                                          |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_pressure                                                                                                                                                                                                 |
| original name | pressure (climate_urban)                                                                                                                                                                                       |
| description   | Recent 10-minute pressure, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/pressure/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/pressure/)                                                                                                |

#### parameters

| name                           | original name | description                   | unit | constraints |
|--------------------------------|---------------|-------------------------------|------|-------------|
| {term}`pressure_air_sea_level` | pp_st_10 | Pressure reduced to sea level. | hPa | >=0 |
| {term}`pressure_air_site` | p0_st_10 | Pressure at station height. | hPa | >=0 |

### urban_solar

#### metadata

| property      | value                                                                                                                                                                                                                           |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_solar                                                                                                                                                                                                                     |
| original name | solar (climate_urban)                                                                                                                                                                                                           |
| description   | Recent 10-minute solar radiation and sunshine, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/solar/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/solar/)                                                                                                                    |

#### parameters

| name                      | original name | description                              | unit  | constraints |
|---------------------------|---------------|------------------------------------------|-------|-------------|
| {term}`radiation_global`  | fg_st_10      | 10min-sum of global (incoming) radiation | J/cm² | >=0         |
| {term}`sunshine_duration` | sd_st_10      | 10min-sum of sunshine duration           | min   | >=0         |

### urban_temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                     |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_air                                                                                                                                                                                                                     |
| original name | air_temperature (climate_urban)                                                                                                                                                                                                           |
| description   | Recent 10-minute air temperature and humidity, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/air_temperature/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/air_temperature/)                                                                                                                    |

#### parameters

| name                                | original name | description                      | unit | constraints |
|-------------------------------------|---------------|----------------------------------|------|-------------|
| {term}`temperature_air_mean_2m` | tt_st_10 | Air temperature at 2m height. | °C | - |
| {term}`humidity` | rf_st_10 | Relative humidity at 2m height. | % | >=0,<=100 |
| {term}`temperature_radiant_mean_2m` | strahl_st_10 | Radiant temperature at 2m height. | °C | - |
| {term}`temperature_air_mean_0_05m` | tt5_st_10 | Air temperature at 5cm height. | °C | - |

### urban_temperature_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                     |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_extreme                                                                                                                                                                                                                 |
| original name | extreme_temperature (climate_urban)                                                                                                                                                                                                       |
| description   | Recent 10-minute extreme air temperatures, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/extreme_temperature/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/extreme_temperature/)                                                                                                                |

#### parameters

| name                              | original name | description                           | unit | constraints |
|-----------------------------------|---------------|---------------------------------------|------|-------------|
| {term}`temperature_air_max_2m` | tx_st_10 | Maximum air temperature at 2m height. | °C | - |
| {term}`temperature_air_min_2m` | tn_st_10 | Minimum air temperature at 2m height. | °C | - |
| {term}`temperature_air_min_0_05m` | tn5_st_10 | Minimum air temperature at 5cm height. | °C | - |

### urban_temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_soil                                                                                                                                                                                                         |
| original name | soil_temperature (climate_urban)                                                                                                                                                                                               |
| description   | Recent 10-minute soil temperature, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/soil_temperature/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/soil_temperature/)                                                                                                        |

#### parameters

| name                               | original name | description                      | unit | constraints |
|------------------------------------|---------------|----------------------------------|------|-------------|
| {term}`temperature_soil_mean_0_1m` | te_st_01m_10 | Soil temperature in 10 cm depth. | °C | - |
| {term}`temperature_soil_mean_0_2m` | te_st_02m_10 | Soil temperature in 20 cm depth. | °C | - |
| {term}`temperature_soil_mean_0_5m` | te_st_05m_10 | Soil temperature in 50 cm depth. | °C | - |
| {term}`temperature_soil_mean_1m` | te_st_10m_10 | Soil temperature in 100 cm depth. | °C | - |

### urban_wind

#### metadata

| property      | value                                                                                                                                                                                                                      |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_wind                                                                                                                                                                                                                 |
| original name | wind (climate_urban)                                                                                                                                                                                                       |
| description   | Recent 10-minute wind speed and direction, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/wind/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/wind/)                                                                                                                |

#### parameters

| name                   | original name | description                                    | unit | constraints |
|------------------------|---------------|------------------------------------------------|------|-------------|
| {term}`wind_speed` | ff_st_10 | Mean wind speed during the last 10 minutes. | m/s | >=0 |
| {term}`wind_direction` | dd_st_10 | Mean wind direction during the last 10 minutes. | ° | >=0,<=360 |

### urban_wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                                  |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_wind_extreme                                                                                                                                                                                                     |
| original name | extreme_wind (climate_urban)                                                                                                                                                                                           |
| description   | Recent 10-minute extreme wind, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/extreme_wind/)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/10_minutes/extreme_wind/)                                                                                                    |

#### parameters

| name                  | original name | description                              | unit | constraints |
|-----------------------|---------------|------------------------------------------|------|-------------|
| {term}`wind_gust_max` | fx_st_10 | Maximum wind gust of the last 10 minutes. | m/s | >=0 |

