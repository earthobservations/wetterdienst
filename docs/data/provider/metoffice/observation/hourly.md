# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | hourly |

## datasets

### rain

#### metadata

| property      | value              |
|---------------|--------------------|
| name          | rain               |
| original name | uk-hourly-rain-obs |

#### parameters

| name                           | original name | description                                       | unit |
|--------------------------------|---------------|---------------------------------------------------|------|
| {term}`precipitation_height` | prcp_amt | Precipitation amount, reported to the nearest 0.1 mm. | mm |
| {term}`precipitation_duration` | prcp_dur | Precipitation duration over less than 24 hours, minutes. | min |

### weather

#### metadata

| property      | value                 |
|---------------|-----------------------|
| name          | weather               |
| original name | uk-hourly-weather-obs |

#### parameters

| name                                  | original name    | description                                                                                   | unit |
|---------------------------------------|------------------|-----------------------------------------------------------------------------------------------|------|
| {term}`wind_direction` | wind_direction | Wind direction, that from which the wind blows, in degrees true. An east wind is 090, a south wind 180. | ° |
| {term}`wind_speed` | wind_speed | Wind speed, knots. | kn |
| {term}`wind_gust_max` | q10mnt_mxgst_spd | Maximum gust speed over 10 minutes, knots. | kn |
| {term}`visibility_range` | visibility | Visibility, decametres. | m |
| {term}`pressure_air_sea_level` | msl_pressure | Mean sea level air pressure, to the nearest 0.1 hPa. | hPa |
| {term}`pressure_air_site` | stn_pres | Station air pressure, as measured at station level. No correction for altitude is applied. | hPa |
| {term}`temperature_air_mean_2m` | air_temperature | Air temperature, to the nearest 0.1 deg C. | °C |
| {term}`temperature_dew_point_mean_2m` | dewpoint | Dewpoint temperature: the temperature to which the air must be cooled to produce saturation with respect to water at its existing pressure and humidity. | °C |
| {term}`humidity` | rltv_hum | Calculated relative humidity. | % |
| {term}`sunshine_duration` | wmo_hr_sun_dur | Readings from the newer automatic sun sensor, which has replaced the Campbell Stokes recorder. | h |
| {term}`snow_depth` | snow_depth | Snow depth, cm. | cm |
| {term}`cloud_cover_total` | cld_ttl_amt_id | Total cloud amount code. | 1/8 |
| {term}`weather` | prst_wx_id | Present weather code. | - |

### wind

#### metadata

| property      | value            |
|---------------|------------------|
| name          | wind             |
| original name | uk-mean-wind-obs |

#### parameters

| name                            | original name   | description                                                    | unit |
|---------------------------------|-----------------|----------------------------------------------------------------|------|
| {term}`wind_direction` | mean_wind_dir | Mean wind direction, that from which the wind blows, in degrees true. An east wind is 090, a south wind 180. | ° |
| {term}`wind_speed` | mean_wind_speed | Mean wind speed, knots. | kn |
| {term}`wind_direction_gust_max` | max_gust_dir | Direction of the maximum gust, degrees true. | ° |
| {term}`wind_gust_max` | max_gust_speed | Speed of the maximum gust, knots. | kn |

### radiation

#### metadata

| property      | value            |
|---------------|------------------|
| name          | radiation        |
| original name | uk-radiation-obs |

#### parameters

| name                                     | original name | description                                                                                 | unit  |
|------------------------------------------|---------------|---------------------------------------------------------------------------------------------|-------|
| {term}`radiation_global` | glbl_irad_amt | Global solar irradiation amount, kJ per square metre over the observation period. | kJ/m² |
| {term}`radiation_sky_short_wave_diffuse` | difu_irad_amt | Diffuse solar irradiation amount, kJ per square metre over the observation period. | kJ/m² |
| {term}`radiation_sky_short_wave_direct` | direct_irad | Direct irradiation amount, kJ per square metre over the observation period. | kJ/m² |

### soil_temperature

#### metadata

| property      | value                   |
|---------------|-------------------------|
| name          | soil_temperature        |
| original name | uk-soil-temperature-obs |

#### parameters

| name                                | original name    | description                            | unit |
|-------------------------------------|------------------|----------------------------------------|------|
| {term}`temperature_soil_mean_0_05m` | q5cm_soil_temp | 5 cm soil temperature, to the nearest 0.1 deg C. | °C |
| {term}`temperature_soil_mean_0_1m` | q10cm_soil_temp | 10 cm soil temperature, to the nearest 0.1 deg C. | °C |
| {term}`temperature_soil_mean_0_2m` | q20cm_soil_temp | 20 cm soil temperature, to the nearest 0.1 deg C. | °C |
| {term}`temperature_soil_mean_0_5m` | q50cm_soil_temp | 50 cm soil temperature, to the nearest 0.1 deg C. | °C |
| {term}`temperature_soil_mean_1m` | q100cm_soil_temp | 100 cm soil temperature, to the nearest 0.1 deg C. | °C |
