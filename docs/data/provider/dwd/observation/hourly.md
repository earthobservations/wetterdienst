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

| name                        | original name | description              | unit | constraints                            |
|-----------------------------|---------------|--------------------------|------|----------------------------------------|
| {term}`quality` | qn_8 | Quality flag. | -             | - |
| {term}`cloud_cover_total` | v_n | Total cloud cover. | 1/8 | >=0,<=8 |
| {term}`cloud_cover_total_measurement_method` | v_n_i | Index how measurement is taken, P = by human person,I = by instrument. Returned as 1 for P and 2 for I. | - | ∈ {1, 2} |
| {term}`cloud_type_layer1` | v_s1_cs | Cloud type of 1. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1} |
| {term}`cloud_height_layer1` | v_s1_hhs | Lower boundary height of 1.layer. | m | >=0 |
| {term}`cloud_cover_layer1` | v_s1_ns | Cloud cover in the first layer. | 1/8 | >=0,<=8 |
| {term}`cloud_type_layer2` | v_s2_cs | Cloud type of 2. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1} |
| {term}`cloud_height_layer2` | v_s2_hhs | Lower boundary height of 2.layer. | m | >=0 |
| {term}`cloud_cover_layer2` | v_s2_ns | Cloud cover in the second layer. | 1/8 | >=0,<=8 |
| {term}`cloud_type_layer3` | v_s3_cs | Cloud type of 3. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1} |
| {term}`cloud_height_layer3` | v_s3_hhs | Lower boundary height of 3.layer. | m | >=0 |
| {term}`cloud_cover_layer3` | v_s3_ns | Cloud cover in the third layer. | 1/8 | >=0,<=8 |
| {term}`cloud_type_layer4` | v_s4_cs | Cloud type of 4. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1} |
| {term}`cloud_height_layer4` | v_s4_hhs | Lower boundary height of 4.layer. | m | >=0 |
| {term}`cloud_cover_layer4` | v_s4_ns | Cloud cover in the fourth layer. | 1/8 | >=0,<=8 |

Codes (cloud_type_layer):

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

| name                            | original name | description                    | unit | constraints                         |
|---------------------------------|---------------|--------------------------------|------|-------------------------------------|
| {term}`quality` | qn_8 | Quality flag. | -             | - |
| {term}`cloud_cover_total_measurement_method` | v_n_i | Index how measurement is taken, P = by human person,I = by instrument. Returned as 1 for P and 2 for I. | - | ∈ {1, 2} |
| {term}`cloud_cover_total` | v_n | Total cloud cover. | 1/8 | >=0,<=8 |

Codes (cloud_cover_total_measurement_method):

| value | source letter | meaning      |
|-------|---------------|--------------|
| 1     | P             | human person |
| 2     | I             | instrument   |

### dew_point

#### metadata

| property      | value                                                                                                                                                                                                                                      |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | dew_point                                                                                                                                                                                                                                  |
| original name | dew_point                                                                                                                                                                                                                                  |
| description   | Hourly station observations of air and dew point temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/DESCRIPTION_obsgermany_climate_hourly_dew_point_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/)                                                                                                                                     |

#### parameters

| name                                  | original name | description           | unit | constraints |
|---------------------------------------|---------------|-----------------------|------|-------------|
| {term}`quality` | qn_8 | Quality flag. | -             | - |
| {term}`temperature_air_2m`      | tt | Air temperature. | °C | - |
| {term}`temperature_dew_point_2m`      | td | Dew point temperature. | °C | - |

### moisture

#### metadata

| property      | value                                                                                                                                                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | moisture                                                                                                                                                                                                                       |
| original name | moisture                                                                                                                                                                                                                       |
| description   | Hourly station observations of moisture parameters for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/moisture/DESCRIPTION_obsgermany_climate_hourly_moisture_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/moisture/)                                                                                                                          |

#### parameters

| name                                  | original name | description                        | unit | constraints |
|---------------------------------------|---------------|------------------------------------|------|-------------|
| {term}`quality` | qn_4 | Quality flag. | -             | - |
| {term}`humidity_absolute` | absf_std | Computed hourly value of absolute humidity. | g/m³ | >=0 |
| {term}`pressure_vapor` | vp_std | Computed hourly value of vapour pressure. | hPa | >=0 |
| {term}`temperature_wet_2m`      | tf_std | Computed hourly value of wet bulb temperature. | °C | - |
| {term}`pressure_air_site` | p_std | Hourly value of barometric pressure. | hPa | >=0 |
| {term}`temperature_air_2m`      | tt_std | Air temperatur in 2m above ground. | °C | - |
| {term}`humidity_relative` | rf_std | Relative humidity. | % | >=0,<=100 |
| {term}`temperature_dew_point_2m`      | td_std | Dew point temperature in 2m above ground. | °C | - |

### precipitation

#### metadata

| property      | value                                                                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                                                                                                                                      |
| original name | precipitation                                                                                                                                                                                                                      |
| description   | Hourly station observations of precipitation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/DESCRIPTION_obsgermany_climate_hourly_precipitation_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/)                                                                                                                         |

#### parameters

| name                         | original name | description           | unit | constraints                  |
|------------------------------|---------------|-----------------------|------|------------------------------|
| {term}`precipitation_amount` | r1 | Precipitation height during the previous hour. | mm | >=0 |
| {term}`precipitation_index` | rs_ind | Precipitation indicator; 0 = no; 1 = yes. | - | ∈ {0, 1} |
| {term}`precipitation_form` | wrtr | Precipitation form; 0 = no precipitation; 1 = rain only (in historical data before 01.01.1979); 4 = form of precipitation unascertainable and depositional precipitation, automatic ascertainment; 6 = liquid precipitation, automatic ascertainment; 7 = solid precipitation, automatic ascertainment; 8 = liquid and solid precipitation, automatic ascertainment; 9 = missing value, form of precipitation unascertainable, automatic ascertainment. The files also hold 2 and 3, which the current sheet does not define. | - | ∈ {0, 1, 2, 3, 4, 6, 7, 8, 9} |

Codes (precipitation_indicator):

| code | meaning          |
|------|------------------|
| 0    | no precipitation |
| 1    | precipitation    |

Codes (precipitation_form):

| code | meaning                                                                                                                                                                                         |
|------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0    | no precipitation, for automatic stations this corresponds to WMO code 10                                                                                                                        |
| 1    | rain only (in historical data before 01.01.1979); the files also hold it after that (station 01048, 4 rows in 2001), where an earlier version of this page read "precipitation height only due to deposition (dew or frost)" |
| 2    | not defined by the current sheet; an earlier version of this page read "precipitation height only due to liquid deposition". In the files of station 01048 (2001 to 2021) it stands at 0.0 to 0.2 mm, mostly at night |
| 3    | not defined by the current sheet; an earlier version of this page read "precipitation height only due to solid precipitation". In the files of station 01048 (2002 to 2010) it stands at 0.0 to 0.2 mm, from October to February |
| 4    | form of precipitation unknown although precipitation was reported; falling and deposited precipitation cannot be told apart by automatic measurement (the English sheet: "form of precipitation unascertainable and depositional precipitation, automatic ascertainment") |
| 6    | liquid precipitation, automatic ascertainment, corresponds to WMO code 11                                                                                                                       |
| 7    | solid precipitation, automatic ascertainment, corresponds to WMO code 12                                                                                                                        |
| 8    | liquid and solid precipitation, automatic ascertainment, corresponds to WMO code 13                                                                                                             |
| 9    | missing value, form of precipitation unascertainable, automatic ascertainment, corresponds to WMO code 15; returned as 9, not as null                                                           |

### pressure

#### metadata

| property      | value                                                                                                                                                                                                               |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | pressure                                                                                                                                                                                                            |
| original name | pressure                                                                                                                                                                                                            |
| description   | Hourly station observations of pressure for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/DESCRIPTION_obsgermany_climate_hourly_pressure_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/)                                                                                                               |

#### parameters

| name                           | original name | description             | unit | constraints |
|--------------------------------|---------------|-------------------------|------|-------------|
| {term}`pressure_air_sea_level` | p | Barometric pressure at sea level NN. | hPa | >=0 |
| {term}`pressure_air_site` | p0 | Barometric pressure at station height. | hPa | >=0 |

### solar

#### metadata

| property      | value                                                                                                                                                                                                                                                               |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | solar                                                                                                                                                                                                                                                               |
| original name | solar                                                                                                                                                                                                                                                               |
| description   | Hourly station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/)                                                                                                                                                                  |

#### parameters

| name                                     | original name | description                               | unit  | constraints |
|------------------------------------------|---------------|-------------------------------------------|-------|-------------|
| {term}`radiation_sky_long_wave` | atmo_lberg | Hourly sum of longwave downward radiation. | J/cm² | >=0 |
| {term}`radiation_sky_short_wave_diffuse` | fd_lberg | Hourly sum of diffuse solar radiation. | J/cm² | >=0 |
| {term}`radiation_global` | fg_lberg | The solar incoming radiation includes the direct and the diffuse part of the solar radiation with respect to the horizontal plane. It is sometimes also referred to as shortwave, including the solar spectrum up to 2.8 micron, as opposed to longwave , which refers to the thermal radiation of the atmosphere. | J/cm² | >=0 |
| {term}`sunshine_duration` | sd_lberg | Hourly sum of sunshine duration. | min | >=0 |
| {term}`sun_zenith_angle` | zenit | Solar zenith angle at mid of interval. The solar zenith angle is between 0-180 and is defined as: ZENIT= 90 - solar_height. | ° | >=0,<=180 |
| {term}`true_local_time_offset` | mess_datum_woz | Local true solar time, published as a whole timestamp and returned as its distance from the timestamp of the record: the longitude correction plus the equation of time. | min | - |

### sun

#### metadata

| property      | value                                                                                                                                                                                                              |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | sun                                                                                                                                                                                                                |
| original name | sun                                                                                                                                                                                                                |
| description   | Hourly station observations of sunshine duration for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/DESCRIPTION_obsgermany_climate_hourly_sun_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/)                                                                                                                   |

#### parameters

| name                      | original name | description              | unit | constraints |
|---------------------------|---------------|--------------------------|------|-------------|
| {term}`sunshine_duration` | sd_so | Hourly sunshine duration. | min | >=0 |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                                     |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                                                           |
| original name | air_temperature                                                                                                                                                                                                                                           |
| description   | Hourly station observations of 2 m air temperature and humidity for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/DESCRIPTION_obsgermany_climate_hourly_air_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/)                                                                                                                                              |

#### parameters

| name                            | original name | description          | unit | constraints |
|---------------------------------|---------------|----------------------|------|-------------|
| {term}`temperature_air_2m`      | tt_tu | Air temperature 2 m above ground. | °C | - |
| {term}`humidity_relative` | rf_tu | Relative humidity. | % | >=0,<=100 |

### temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_soil                                                                                                                                                                                                                               |
| original name | soil_temperature                                                                                                                                                                                                                               |
| description   | Hourly station observations of of soil temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/DESCRIPTION_obsgermany_climate_hourly_soil_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/)                                                                                                                                  |

#### parameters

| name                                | original name | description                      | unit | constraints |
|-------------------------------------|---------------|----------------------------------|------|-------------|
| {term}`temperature_soil_0_02m`      | v_te002 | Soil temperature in 2 cm depth. | °C | - |
| {term}`temperature_soil_0_05m`      | v_te005 | Soil temperature in 5 cm depth. | °C | - |
| {term}`temperature_soil_0_1m`      | v_te010 | Soil temperature in 10 cm depth. | °C | - |
| {term}`temperature_soil_0_2m`      | v_te020 | Soil temperature in 20 cm depth. | °C | - |
| {term}`temperature_soil_0_5m`      | v_te050 | Soil temperature in 50 cm depth. | °C | - |
| {term}`temperature_soil_1m`      | v_te100 | Soil temperature in 100 cm depth. | °C | - |

### urban_precipitation

#### metadata

| property      | value                                                                                                                                                                                                                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_precipitation                                                                                                                                                                                                                                                                             |
| original name | precipitation (climate_urban)                                                                                                                                                                                                                                                                   |
| description   | Recent hourly precipitation, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/recent/DESCRIPTION_obsgermany_climate_urban_hourly_precipitation_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/)                                                                                                                                                                                |

#### parameters

| name                         | original name      | description          | unit | constraints |
|------------------------------|--------------------|----------------------|------|-------------|
| {term}`precipitation_amount` | niederschlagshoehe | Precipitation height, the sum of the six 10-minute intervals of the previous hour (at UTC 11 the sum of the precipitation during UTC10-UTC11). | mm | >=0 |

### urban_pressure

#### metadata

| property      | value                                                                                                                                                                                                                                                                            |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_pressure                                                                                                                                                                                                                                                                   |
| original name | pressure (climate_urban)                                                                                                                                                                                                                                                         |
| description   | Recent hourly pressure, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/recent/DESCRIPTION_obsgermany_climate_urban_hourly_pressure_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/)                                                                                                                                                                      |

#### parameters

| name                           | original name           | description                        | unit | constraints |
|--------------------------------|-------------------------|------------------------------------|------|-------------|
| {term}`pressure_air_sea_level` | luftdruck_nn            | Air pressure reduced to sea level. | hPa  | >=0         |
| {term}`pressure_air_site`      | luftdruck_stationshoehe | Pressure at station height, following the SYNOP conventions: the hour x corresponds to the measurement from 10 min before (at UTC 11 the value from UTC 10:50). | hPa  | >=0         |

### urban_temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                 |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_air                                                                                                                                                                                                                                                                                 |
| original name | air_temperature (climate_urban)                                                                                                                                                                                                                                                                       |
| description   | Recent hourly air temperature and humidity, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_tu_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/)                                                                                                                                                                                    |

#### parameters

| name                            | original name  | description          | unit | constraints |
|---------------------------------|----------------|----------------------|------|-------------|
| {term}`temperature_air_2m`      | lufttemperatur | 2m air temperature, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | °C   | -           |
| {term}`humidity_relative`       | rel_feuchte    | 2m relative humidity, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | %    | >=0,<=100   |

### urban_temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                    |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_soil                                                                                                                                                                                                                                                                                   |
| original name | soil_temperature (climate_urban)                                                                                                                                                                                                                                                                         |
| description   | Recent hourly soil temperature, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_soil_temperature_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/)                                                                                                                                                                                      |

#### parameters

| name                                | original name | description                      | unit | constraints |
|-------------------------------------|---------------|----------------------------------|------|-------------|
| {term}`temperature_soil_0_05m`      | erdbt_005 | Soil temperature in 5 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | °C | - |
| {term}`temperature_soil_0_1m`      | erdbt_010 | Soil temperature in 10 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | °C | - |
| {term}`temperature_soil_0_2m`      | erdbt_020 | Soil temperature in 20 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | °C | - |
| {term}`temperature_soil_0_5m`      | erdbt_050 | Soil temperature in 50 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | °C | - |
| {term}`temperature_soil_1m`      | erdbt_100 | Soil temperature in 100 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | °C | - |

### urban_sun

#### metadata

| property      | value                                                                                                                                                                                                                                                                           |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_sun                                                                                                                                                                                                                                                                       |
| original name | sun (climate_urban)                                                                                                                                                                                                                                                             |
| description   | Recent hourly sunshine duration, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/recent/DESCRIPTION_obsgermany_climate_urban_hourly_sun_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/)                                                                                                                                                                          |

#### parameters

| name                      | original name     | description       | unit | constraints |
|---------------------------|-------------------|-------------------|------|-------------|
| {term}`sunshine_duration` | sonnenscheindauer | Sunshine duration, the sum of the six 10-minute intervals of the previous hour (at UTC 11 the sum of the sunshine during UTC10-UTC11). | min | >=0 |

### urban_wind

#### metadata

| property      | value                                                                                                                                                                                                                                                                                    |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_wind                                                                                                                                                                                                                                                                               |
| original name | wind (climate_urban)                                                                                                                                                                                                                                                                     |
| description   | Recent hourly wind speed and direction, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/recent/DESCRIPTION_obsgermany_climate_urban_hourly_wind_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/)                                                                                                                                                                                  |

#### parameters

| name                   | original name       | description         | unit | constraints |
|------------------------|---------------------|---------------------|------|-------------|
| {term}`wind_speed` | windgeschwindigkeit | Mean wind speed, the average of the six 10-minute intervals of the previous hour (at UTC 11 the average during UTC10-UTC11). DWD's sheet: measured at 368 m on Berlin's television tower (the other urban stations have their own sensor heights). | m/s | >=0 |
| {term}`wind_direction` | windrichtung | Mean wind direction, the average of the six 10-minute intervals of the previous hour (at UTC 11 the average during UTC10-UTC11). DWD's sheet: measured at 368 m on Berlin's television tower (the other urban stations have their own sensor heights). | ° | >=0,<=360 |

### visibility

#### metadata

| property      | value                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | visibility                                                                                                                                                                                                                |
| original name | visibility                                                                                                                                                                                                                |
| description   | Hourly station observations of visibility for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/DESCRIPTION_obsgermany_climate_hourly_visibility_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/)                                                                                                                   |

#### parameters

| name                           | original name | description                    | unit | constraints |
|--------------------------------|---------------|--------------------------------|------|-------------|
| {term}`visibility_measurement_method` | v_vv_i | Visibility index, noting how the measurement is taken,P=by human person,I=by an instrument. Returned as 1 for P and 2 for I. | - | ∈ {1, 2} |
| {term}`visibility` | v_vv | Visibility range. | m | >=0 |

Codes (visibility_measurement_method):

| value | source letter | meaning         |
|-------|---------------|-----------------|
| 1     | P             | by human person |
| 2     | I             | by instrument   |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                              |
| original name | weather_phenomena                                                                                                                                                                                                                              |
| description   | Hourly station observations of weather phenomena for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/DESCRIPTION_obsgermany_climate_hourly_weather_phenomena_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/)                                                                                                                                 |

#### parameters

| name                 | original name | description                       | unit | constraints |
|----------------------|---------------|-----------------------------------|------|-------------|
| {term}`weather` | ww | Weather code of current condition. | - | - |

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

| name                   | original name | description         | unit | constraints |
|------------------------|---------------|---------------------|------|-------------|
| {term}`wind_speed` | f | Mean wind speed. | m/s | >=0 |
| {term}`wind_direction` | d | Mean wind direction. The source's 0 (a calm or variable wind) is null. | ° | >=0,<=360 |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                                                                    |
| original name | extreme_wind                                                                                                                                                                                                                                    |
| description   | Hourly maximum value from station observations of windspeed for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/extreme_wind/DESCRIPTION_obsgermany_climate_hourly_extreme_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/extreme_wind/)                                                                                                                                       |

#### parameters

| name                  | original name | description                      | unit | constraints |
|-----------------------|---------------|----------------------------------|------|-------------|
| {term}`wind_gust_max` | fx_911 | Wind speed, wind gust: the highest wind peak of the last hour. | m/s | >=0 |

### wind_synoptic

#### metadata

| property      | value                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_synoptic                                                                                                                                                                                                                                |
| original name | wind_synop                                                                                                                                                                                                                                   |
| description   | Hourly station observations of wind speed and wind direction for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/DESCRIPTION_obsgermany_climate_hourly_wind_synop_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/)                                                                                                                                      |

#### parameters

| name                   | original name | description         | unit | constraints |
|------------------------|---------------|---------------------|------|-------------|
| {term}`wind_speed_last_10min` | ff | 10-minute mean of the wind speed (DWD: "10-Min-Mittel der Windgeschwindigkeit"). | m/s | >=0 |
| {term}`wind_direction` | dd | Wind direction (DWD: "Windrichtung uml.,windstill DD=00"). The source's 0 (a calm or variable wind) is null. | ° | >=0,<=360 |
