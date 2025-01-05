# hourly

## metadata

| property      | value                                                                                        |
|---------------|----------------------------------------------------------------------------------------------|
| name          | hourly                                                                                       |
| original name | hourly                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/) |

## datasets

### cloud_type

#### metadata

| property      | value                                                                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | cloud_type                                                                                                                                                                                                                                                                |
| original name | cloud_type                                                                                                                                                                                                                                                                |
| description   | Hourly station observations of cloud cover, cloud type and cloud height in up to 4 layers for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloud_type/DESCRIPTION_obsgermany_climate_hourly_cloud_type_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloud_type/)                                                                                                                                                                   |

#### parameters

| name                | original name | description              | unit type     | unit | constraints                            |
|---------------------|---------------|--------------------------|---------------|------|----------------------------------------|
| cloud_cover_total   | v_n           | total cloud cover        | fraction      | 1/8  | >=0,<=8                                |
| cloud_type_layer1   | v_s1_cs       | cloud type of 1st layer  | dimensionless | -    | ∈ \[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1\] |
| cloud_height_layer1 | v_s1_hhs      | height of 1st layer      | length_medium | m    | >=0                                    |
| cloud_cover_layer1  | v_s1_ns       | cloud cover of 1st layer | fraction      | 1/8  | >=0,<=8                                |
| cloud_type_layer2   | v_s2_cs       | cloud type of 2nd layer  | dimensionless | -    | ∈ \[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1\] |
| cloud_height_layer2 | v_s2_hhs      | height of 2nd layer      | length_medium | m    | >=0                                    |
| cloud_cover_layer2  | v_s2_ns       | cloud cover of 2nd layer | fraction      | 1/8  | >=0,<=8                                |
| cloud_type_layer3   | v_s3_cs       | cloud type of 3rd layer  | dimensionless | -    | ∈ \[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1\] |
| cloud_height_layer3 | v_s3_hhs      | height of 3rd layer      | length_medium | m    | >=0                                    |
| cloud_cover_layer3  | v_s3_ns       | cloud cover of 3rd layer | fraction      | 1/8  | >=0,<=8                                |
| cloud_type_layer4   | v_s4_cs       | cloud type of 4th layer  | dimensionless | -    | ∈ \[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1\] |
| cloud_height_layer4 | v_s4_hhs      | height of 4th layer      | length_medium | m    | >=0                                    |
| cloud_cover_layer4  | v_s4_ns       | cloud cover of 4th layer | fraction      | 1/8  | >=0,<=8                                |

Code (cloud_type_layer):

| code | cloud type    |
|------|---------------|
| 0    | cirrus        |
| 1    | cirrocumulus  |
| 2    | cirrostratus  |
| 3    | altocumulus   |
| 4    | altostratus   |
| 5    | nimbostratus  |
| 6    | stratocumulus |
| 7    | stratus       |
| 8    | cumulus       |
| 9    | cumulonimbus  |
| -1   | automated     |

### cloudiness

#### metadata

| property      | value                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | cloudiness                                                                                                                                                                                                                |
| original name | cloudiness                                                                                                                                                                                                                |
| description   | Hourly station observations of cloudiness for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/DESCRIPTION_obsgermany_climate_hourly_cloudiness_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/)                                                                                                                   |

#### parameters

| name                        | original name | description                    | unit type     | unit          | constraints                         |
|-----------------------------|---------------|--------------------------------|---------------|---------------|-------------------------------------|
| cloud_cover_total_indicator | v_n_i         | index how measurement is taken | dimensionless | -             | ∈ \[P, I\]                          |
| cloud_cover_total           | v_n           | total cloud cover              | fraction      | 1/8           | ∈ \[0, 1, 2, 3, 4, 5, 6, 7, 8, -1\] |

Code (cloud_cover_total_indicator):

| code | meaning      |
|------|--------------|
| P    | human person |
| I    | instrument   |

### dew_point

#### metadata

| property      | value                                                                                                                                                                                                                                      |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | dew_point                                                                                                                                                                                                                                  |
| original name | dew_point                                                                                                                                                                                                                                  |
| description   | Hourly station observations of air and dew point temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/DESCRIPTION_obsgermany_climate_hourly_dew_point_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/)                                                                                                                                     |

#### parameters

| name                          | original name | description           | unit type   | unit          | constraints |
|-------------------------------|---------------|-----------------------|-------------|---------------|-------------|
| temperature_air_mean_2m       | tt            | air temperature       | temperature | °C            | -           |
| temperature_dew_point_mean_2m | td            | dew point temperature | temperature | °C            | -           |

### moisture

#### metadata

| property      | value                                                                                                                                                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | moisture                                                                                                                                                                                                                       |
| original name | moisture                                                                                                                                                                                                                       |
| description   | Hourly station observations of moisture parameters for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/moisture/DESCRIPTION_obsgermany_climate_hourly_moisture_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/moisture/)                                                                                                                          |

#### parameters

| name                          | original name | description                        | unit type     | unit          | constraints |
|-------------------------------|---------------|------------------------------------|---------------|---------------|-------------|
| humidity_absolute             | absf_std      | absolute humidity                  | dimensionless | -             | >=0,<=100   |
| pressure_vapor                | vp_std        | vapor pressure                     | pressure      | hPa           | >=0         |
| temperature_wet_mean_2m       | tf_std        | wet temperature                    | temperature   | °C            | -           |
| pressure_air_site             | p_std         | air pressure at site level         | pressure      | hPa           | >=0         |
| temperature_air_mean_2m       | tt_std        | air temperature at 2m height       | temperature   | °C            | -           |
| humidity                      | rf_std        | humidity                           | fraction      | %             | >=0,<=100   |
| temperature_dew_point_mean_2m | td_std        | dew point temperature at 2m height | temperature   | °C            | -           |

### precipitation

#### metadata

| property      | value                                                                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                                                                                                                                      |
| original name | precipitation                                                                                                                                                                                                                      |
| description   | Hourly station observations of precipitation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/DESCRIPTION_obsgermany_climate_hourly_precipitation_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/)                                                                                                                         |

#### parameters

| name                    | original name | description           | unit type     | unit          | constraints                  |
|-------------------------|---------------|-----------------------|---------------|---------------|------------------------------|
| precipitation_height    | r1            | hourly precipitation  | precipitation | mm            | >=0                          |
| precipitation_indicator | rs_ind        | precipitation index   | dimensionless | -             | ∈ \[0, 1\]                   |
| precipitation_form      | wrtr          | form of precipitation | dimensionless | -             | ∈ \[0, 1, 2, 3, 6, 7, 8, 9\] |

Code (precipitation_indicator):

| code | meaning          |
|------|------------------|
| 0    | no precipitation |
| 1    | precipitation    |

Code (precipitation_form):

| code | meaning                                                                                                                                                                      |
|------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0    | no fallen precipitation or too little deposition (e.g., dew or frost) to form a precipitation height larger than 0.0, for automatic stations this corresponds to WMO code 10 |
| 1    | precipitation height only due to deposition (dew or frost) or if it cannot decided how large the part from deposition is                                                     |
| 2    | precipitation height only due to liquid deposition                                                                                                                           |
| 3    | precipitation height only due to solid precipitation                                                                                                                         |
| 6    | precipitation height due to fallen liquid precipitation, may also include deposition of any kind, or automatic stations this corresponds to WMO code 11                      |
| 7    | precipitation height due to fallen solid precipitation, may also include deposition of any kind, for automatic stations this corresponds to WMO code 12                      |
| 8    | fallen precipitation in liquid and solid form, for automatic stations this corresponds to WMO code 13                                                                        |
| 9    | no precipitation measurement, form of precipitation cannot be determined, for automatic stations this corresponds to WMO code 15                                             |

### pressure

#### metadata

| property      | value                                                                                                                                                                                                               |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | pressure                                                                                                                                                                                                            |
| original name | pressure                                                                                                                                                                                                            |
| description   | Hourly station observations of pressure for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/DESCRIPTION_obsgermany_climate_hourly_pressure_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/)                                                                                                               |

#### parameters

| name                   | original name | description             | unit type | unit          | constraints |
|------------------------|---------------|-------------------------|-----------|---------------|-------------|
| pressure_air_sea_level | p             | mean sea level pressure | pressure  | hPa           | >=0         |
| pressure_air_site      | p0            | mean sea level pressure | pressure  | hPa           | >=0         |

### solar

#### metadata

| property      | value                                                                                                                                                                                                                                                               |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | solar                                                                                                                                                                                                                                                               |
| original name | solar                                                                                                                                                                                                                                                               |
| description   | Hourly station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/)                                                                                                                                                                  |

#### parameters

| name                             | original name | description                               | unit type       | unit          | constraints |
|----------------------------------|---------------|-------------------------------------------|-----------------|---------------|-------------|
| radiation_sky_long_wave          | atmo_lberg    | hourly sum of longwave downward radiation | energy_per_area | J/cm²         | >=0         |
| radiation_sky_short_wave_diffuse | fd_lberg      | hourly sum of diffuse solar radiation     | energy_per_area | J/cm²         | >=0         |
| radiation_global                 | fg_lberg      | hourly sum of solar incoming radiation    | energy_per_area | J/cm²         | >=0         |
| sunshine_duration                | sd_lberg      | hourly sum of sunshine duration           | time            | min           | >=0         |
| sun_zenith_angle                 | zenit         | solar zenith angle at mid of interval     | angle           | °             | >=0,<=180   |

### sun

#### metadata

| property      | value                                                                                                                                                                                                              |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | sun                                                                                                                                                                                                                |
| original name | sun                                                                                                                                                                                                                |
| description   | Hourly station observations of sunshine duration for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/DESCRIPTION_obsgermany_climate_hourly_sun_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/)                                                                                                                   |

#### parameters

| name              | original name | description              | unit type | unit          | constraints |
|-------------------|---------------|--------------------------|-----------|---------------|-------------|
| sunshine_duration | sd_so         | hourly sunshine duration | time      | min           | >=0         |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                                     |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                                                           |
| original name | air_temperature                                                                                                                                                                                                                                           |
| description   | Hourly station observations of 2 m air temperature and humidity for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/DESCRIPTION_obsgermany_climate_hourly_air_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/)                                                                                                                                              |

#### parameters

| name                    | original name | description          | unit type   | unit          | constraints |
|-------------------------|---------------|----------------------|-------------|---------------|-------------|
| temperature_air_mean_2m | tt_tu         | 2m air temperature   | temperature | °C            | -           |
| humidity                | rf_tu         | 2m relative humidity | fraction    | %             | >=0,<=100   |

### temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_soil                                                                                                                                                                                                                               |
| original name | soil_temperature                                                                                                                                                                                                                               |
| description   | Hourly station observations of of soil temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/DESCRIPTION_obsgermany_climate_hourly_soil_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/)                                                                                                                                  |

#### parameters

| name                        | original name | description                      | unit type   | unit          | constraints |
|-----------------------------|---------------|----------------------------------|-------------|---------------|-------------|
| temperature_soil_mean_0_02m | v_te002       | soil temperature in 2 cm depth   | temperature | °C            | -           |
| temperature_soil_mean_0_05m | v_te005       | soil temperature in 5 cm depth   | temperature | °C            | -           |
| temperature_soil_mean_0_1m  | v_te010       | soil temperature in 10 cm depth  | temperature | °C            | -           |
| temperature_soil_mean_0_2m  | v_te020       | soil temperature in 20 cm depth  | temperature | °C            | -           |
| temperature_soil_mean_0_5m  | v_te050       | soil temperature in 50 cm depth  | temperature | °C            | -           |
| temperature_soil_mean_1m    | v_te100       | soil temperature in 100 cm depth | temperature | °C            | -           |

### urban_precipitation

#### metadata

| property      | value                                                                                                                                                                                                                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_precipitation                                                                                                                                                                                                                                                                             |
| original name | precipitation (climate_urban)                                                                                                                                                                                                                                                                   |
| description   | Recent hourly precipitation, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/recent/DESCRIPTION_obsgermany_climate_urban_hourly_precipitation_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/)                                                                                                                                                                                |

#### parameters

| name                 | original name      | description          | unit type     | unit          | constraints |
|----------------------|--------------------|----------------------|---------------|---------------|-------------|
| precipitation_height | niederschlagshoehe | precipitation height | precipitation | mm            | >=0         |

### urban_pressure

#### metadata

| property      | value                                                                                                                                                                                                                                                                            |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_pressure                                                                                                                                                                                                                                                                   |
| original name | pressure (climate_urban)                                                                                                                                                                                                                                                         |
| description   | Recent hourly pressure, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/recent/DESCRIPTION_obsgermany_climate_urban_hourly_pressure_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/)                                                                                                                                                                      |

#### parameters

| name              | original name           | description                | unit type | unit          | constraints |
|-------------------|-------------------------|----------------------------|-----------|---------------|-------------|
| pressure_air_site | luftdruck_stationshoehe | pressure at station height | pressure  | hPa           | >=0         |

### urban_temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                 |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_air                                                                                                                                                                                                                                                                                 |
| original name | air_temperature (climate_urban)                                                                                                                                                                                                                                                                       |
| description   | Recent hourly air temperature and humidity, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_tu_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/)                                                                                                                                                                                    |

#### parameters

| name                    | original name  | description          | unit type   | unit | constraints |
|-------------------------|----------------|----------------------|-------------|------|-------------|
| temperature_air_mean_2m | lufttemperatur | 2m air temperature   | temperature | °C   | -           |
| humidity                | rel_feuchte    | 2m relative humidity | fraction    | %    | >=0,<=100   |

### urban_temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                    |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_soil                                                                                                                                                                                                                                                                                   |
| original name | soil_temperature (climate_urban)                                                                                                                                                                                                                                                                         |
| description   | Recent hourly soil temperature, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_soil_temperature_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/)                                                                                                                                                                                      |

#### parameters

| name                        | original name | description                      | unit type   | unit | constraints |
|-----------------------------|---------------|----------------------------------|-------------|------|-------------|
| temperature_soil_mean_0_05m | erdbt_005     | soil temperature in 5 cm depth   | temperature | °C   | -           |
| temperature_soil_mean_0_1m  | erdbt_010     | soil temperature in 10 cm depth  | temperature | °C   | -           |
| temperature_soil_mean_0_2m  | erdbt_020     | soil temperature in 20 cm depth  | temperature | °C   | -           |
| temperature_soil_mean_0_5m  | erdbt_050     | soil temperature in 50 cm depth  | temperature | °C   | -           |
| temperature_soil_mean_1m    | erdbt_100     | soil temperature in 100 cm depth | temperature | °C   | -           |

### urban_sun

#### metadata

| property      | value                                                                                                                                                                                                                                                                           |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_sun                                                                                                                                                                                                                                                                       |
| original name | sun (climate_urban)                                                                                                                                                                                                                                                             |
| description   | Recent hourly sunshine duration, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/recent/DESCRIPTION_obsgermany_climate_urban_hourly_sun_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/)                                                                                                                                                                          |

#### parameters

| name              | original name     | description       | unit type | unit | constraints |
|-------------------|-------------------|-------------------|-----------|------|-------------|
| sunshine_duration | sonnenscheindauer | sunshine duration | time      | min  | >=0         |

### urban_wind

#### metadata

| property      | value                                                                                                                                                                                                                                                                                    |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_wind                                                                                                                                                                                                                                                                               |
| original name | wind (climate_urban)                                                                                                                                                                                                                                                                     |
| description   | Recent hourly wind speed and direction, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/recent/DESCRIPTION_obsgermany_climate_urban_hourly_wind_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/)                                                                                                                                                                                  |

#### parameters

| name           | original name       | description         | unit type | unit | constraints |
|----------------|---------------------|---------------------|-----------|------|-------------|
| wind_speed     | windgeschwindigkeit | mean wind speed     | speed     | m/s  | >=0         |
| wind_direction | windrichtung        | mean wind direction | angle     | °    | >=0,<=360   |

### visibility

#### metadata

| property      | value                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | visibility                                                                                                                                                                                                                |
| original name | visibility                                                                                                                                                                                                                |
| description   | Hourly station observations of visibility for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/DESCRIPTION_obsgermany_climate_hourly_visibility_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/)                                                                                                                   |

#### parameters

| name                       | original name | description                    | unit type     | unit          | constraints |
|----------------------------|---------------|--------------------------------|---------------|---------------|-------------|
| visibility_range_indicator | v_vv_i        | index how measurement is taken | dimensionless | -             | ∈ \[P, I\]  |
| visibility_range           | v_vv          | visibility                     | length_medium | m             | >=0         |

Code (visibility_range_indicator):

| code | meaning         |
|------|-----------------|
| P    | by human person |
| I    | by instrument   |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                              |
| original name | weather_phenomena                                                                                                                                                                                                                              |
| description   | Hourly station observations of weather phenomena for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/DESCRIPTION_obsgermany_climate_hourly_weather_phenomena_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/)                                                                                                                                 |

#### parameters

| name         | original name | description                       | unit type     | unit | constraints |
|--------------|---------------|-----------------------------------|---------------|------|-------------|
| weather      | ww            | weather code of current condition | dimensionless | -    | -           |
| weather_text | ww_text       | weather text of current condition | dimensionless | -    | -           |

weather codes and descriptions: [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/historical/Wetter_Beschreibung.txt)

### wind

#### metadata

| property      | value                                                                                                                                                                                                                                            |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind                                                                                                                                                                                                                                             |
| original name | wind                                                                                                                                                                                                                                             |
| description   | Hourly mean value from station observations of wind speed and wind direction for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/DESCRIPTION_obsgermany_climate_hourly_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/)                                                                                                                                                |

#### parameters

| name           | original name | description         | unit type | unit | constraints |
|----------------|---------------|---------------------|-----------|------|-------------|
| wind_speed     | f             | mean wind speed     | speed     | m/s  | >=0         |
| wind_direction | d             | mean wind direction | angle     | °    | >=0,<=360   |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                                                                    |
| original name | extreme_wind                                                                                                                                                                                                                                    |
| description   | Hourly maximum value from station observations of windspeed for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/extreme_wind/DESCRIPTION_obsgermany_climate_hourly_extreme_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/extreme_wind/)                                                                                                                                       |

#### parameters

| name          | original name | description                      | unit type | unit | constraints |
|---------------|---------------|----------------------------------|-----------|------|-------------|
| wind_gust_max | fx_911        | maximum wind speed in 10m height | speed     | m/s  | >=0         |

### wind_synoptic

#### metadata

| property      | value                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_synoptic                                                                                                                                                                                                                                |
| original name | wind_synop                                                                                                                                                                                                                                   |
| description   | Hourly station observations of wind speed and wind direction for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/DESCRIPTION_obsgermany_climate_hourly_wind_synop_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/)                                                                                                                                      |

#### parameters

| name           | original name | description         | unit type | unit | constraints |
|----------------|---------------|---------------------|-----------|------|-------------|
| wind_speed     | ff            | mean wind speed     | speed     | m/s  | >=0         |
| wind_direction | dd            | mean wind direction | angle     | °    | >=0,<=360   |
