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

| name                   | original name | unit type     | unit |
|------------------------|---------------|---------------|------|
| precipitation_height   | prcp_amt      | precipitation | mm   |
| precipitation_duration | prcp_dur      | time          | min  |

### weather

#### metadata

| property      | value                 |
|---------------|-----------------------|
| name          | weather               |
| original name | uk-hourly-weather-obs |

#### parameters

| name                          | original name    | unit type     | unit |
|-------------------------------|------------------|---------------|------|
| wind_direction                | wind_direction   | angle         | °    |
| wind_speed                    | wind_speed       | speed         | kn   |
| wind_gust_max                 | q10mnt_mxgst_spd | speed         | kn   |
| visibility_range              | visibility       | length_medium | m    |
| pressure_air_sea_level        | msl_pressure     | pressure      | hPa  |
| pressure_air_site             | stn_pres         | pressure      | hPa  |
| temperature_air_mean_2m       | air_temperature  | temperature   | °C   |
| temperature_dew_point_mean_2m | dewpoint         | temperature   | °C   |
| humidity                      | rltv_hum         | fraction      | %    |
| sunshine_duration             | wmo_hr_sun_dur   | time          | h    |
| snow_depth                    | snow_depth       | length_short  | cm   |
| cloud_cover_total             | cld_ttl_amt_id   | fraction      | 1/8  |
| weather                       | prst_wx_id       | dimensionless | -    |

### wind

#### metadata

| property      | value            |
|---------------|------------------|
| name          | wind             |
| original name | uk-mean-wind-obs |

#### parameters

| name                    | original name   | unit type | unit |
|-------------------------|-----------------|-----------|------|
| wind_direction          | mean_wind_dir   | angle     | °    |
| wind_speed              | mean_wind_speed | speed     | kn   |
| wind_direction_gust_max | max_gust_dir    | angle     | °    |
| wind_gust_max           | max_gust_speed  | speed     | kn   |

### radiation

#### metadata

| property      | value            |
|---------------|------------------|
| name          | radiation        |
| original name | uk-radiation-obs |

#### parameters

| name                             | original name | unit type       | unit  |
|----------------------------------|---------------|-----------------|-------|
| radiation_global                 | glbl_irad_amt | energy_per_area | kJ/m² |
| radiation_sky_short_wave_diffuse | difu_irad_amt | energy_per_area | kJ/m² |
| radiation_sky_short_wave_direct  | direct_irad   | energy_per_area | kJ/m² |

### soil_temperature

#### metadata

| property      | value                   |
|---------------|-------------------------|
| name          | soil_temperature        |
| original name | uk-soil-temperature-obs |

#### parameters

| name                        | original name    | unit type   | unit |
|-----------------------------|------------------|-------------|------|
| temperature_soil_mean_0_05m | q5cm_soil_temp   | temperature | °C   |
| temperature_soil_mean_0_1m  | q10cm_soil_temp  | temperature | °C   |
| temperature_soil_mean_0_2m  | q20cm_soil_temp  | temperature | °C   |
| temperature_soil_mean_0_5m  | q50cm_soil_temp  | temperature | °C   |
| temperature_soil_mean_1m    | q100cm_soil_temp | temperature | °C   |
