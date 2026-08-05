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

| name                           | original name | unit |
|--------------------------------|---------------|------|
| {term}`precipitation_height`   | prcp_amt      | mm   |
| {term}`precipitation_duration` | prcp_dur      | min  |

### weather

#### metadata

| property      | value                 |
|---------------|-----------------------|
| name          | weather               |
| original name | uk-hourly-weather-obs |

#### parameters

| name                                  | original name    | unit |
|---------------------------------------|------------------|------|
| {term}`wind_direction`                | wind_direction   | °    |
| {term}`wind_speed`                    | wind_speed       | kn   |
| {term}`wind_gust_max`                 | q10mnt_mxgst_spd | kn   |
| {term}`visibility_range`              | visibility       | m    |
| {term}`pressure_air_sea_level`        | msl_pressure     | hPa  |
| {term}`pressure_air_site`             | stn_pres         | hPa  |
| {term}`temperature_air_mean_2m`       | air_temperature  | °C   |
| {term}`temperature_dew_point_mean_2m` | dewpoint         | °C   |
| {term}`humidity`                      | rltv_hum         | %    |
| {term}`sunshine_duration`             | wmo_hr_sun_dur   | h    |
| {term}`snow_depth`                    | snow_depth       | cm   |
| {term}`cloud_cover_total`             | cld_ttl_amt_id   | 1/8  |
| {term}`weather`                       | prst_wx_id       | -    |

### wind

#### metadata

| property      | value            |
|---------------|------------------|
| name          | wind             |
| original name | uk-mean-wind-obs |

#### parameters

| name                            | original name   | unit |
|---------------------------------|-----------------|------|
| {term}`wind_direction`          | mean_wind_dir   | °    |
| {term}`wind_speed`              | mean_wind_speed | kn   |
| {term}`wind_direction_gust_max` | max_gust_dir    | °    |
| {term}`wind_gust_max`           | max_gust_speed  | kn   |

### radiation

#### metadata

| property      | value            |
|---------------|------------------|
| name          | radiation        |
| original name | uk-radiation-obs |

#### parameters

| name                                     | original name | unit  |
|------------------------------------------|---------------|-------|
| {term}`radiation_global`                 | glbl_irad_amt | kJ/m² |
| {term}`radiation_sky_short_wave_diffuse` | difu_irad_amt | kJ/m² |
| {term}`radiation_sky_short_wave_direct`  | direct_irad   | kJ/m² |

### soil_temperature

#### metadata

| property      | value                   |
|---------------|-------------------------|
| name          | soil_temperature        |
| original name | uk-soil-temperature-obs |

#### parameters

| name                                | original name    | unit |
|-------------------------------------|------------------|------|
| {term}`temperature_soil_mean_0_05m` | q5cm_soil_temp   | °C   |
| {term}`temperature_soil_mean_0_1m`  | q10cm_soil_temp  | °C   |
| {term}`temperature_soil_mean_0_2m`  | q20cm_soil_temp  | °C   |
| {term}`temperature_soil_mean_0_5m`  | q50cm_soil_temp  | °C   |
| {term}`temperature_soil_mean_1m`    | q100cm_soil_temp | °C   |
