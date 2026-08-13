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
| {term}`precipitation_height`   | prcp_amt      | Depth of precipitation collected over the period. | mm   |
| {term}`precipitation_duration` | prcp_dur      | Length of time during which precipitation fell.   | min  |

### weather

#### metadata

| property      | value                 |
|---------------|-----------------------|
| name          | weather               |
| original name | uk-hourly-weather-obs |

#### parameters

| name                                  | original name    | description                                                                                   | unit |
|---------------------------------------|------------------|-----------------------------------------------------------------------------------------------|------|
| {term}`wind_direction`                | wind_direction   | Direction the wind is blowing from, clockwise from true north.                                | °    |
| {term}`wind_speed`                    | wind_speed       | Mean speed of the wind over the period.                                                       | kn   |
| {term}`wind_gust_max`                 | q10mnt_mxgst_spd | Speed of the strongest gust of the period.                                                    | kn   |
| {term}`visibility_range`              | visibility       | Horizontal distance at which an object can still be made out.                                 | m    |
| {term}`pressure_air_sea_level`        | msl_pressure     | Air pressure reduced to mean sea level, so that stations at different heights compare.        | hPa  |
| {term}`pressure_air_site`             | stn_pres         | Air pressure as measured at station height.                                                   | hPa  |
| {term}`temperature_air_mean_2m`       | air_temperature  | Mean air temperature at 2 m above ground.                                                     | °C   |
| {term}`temperature_dew_point_mean_2m` | dewpoint         | Dew point at 2 m above ground, the temperature at which the air would become saturated.       | °C   |
| {term}`humidity`                      | rltv_hum         | Relative humidity of the air, the fraction of the moisture it could hold at that temperature. | %    |
| {term}`sunshine_duration`             | wmo_hr_sun_dur   | Length of time the sun shone unobstructed.                                                    | h    |
| {term}`snow_depth`                    | snow_depth       | Depth of the snow lying on the ground.                                                        | cm   |
| {term}`cloud_cover_total`             | cld_ttl_amt_id   | Fraction of the sky covered by cloud of any kind.                                             | 1/8  |
| {term}`weather`                       | prst_wx_id       | Coded present weather at the time of observation.                                             | -    |

### wind

#### metadata

| property      | value            |
|---------------|------------------|
| name          | wind             |
| original name | uk-mean-wind-obs |

#### parameters

| name                            | original name   | description                                                    | unit |
|---------------------------------|-----------------|----------------------------------------------------------------|------|
| {term}`wind_direction`          | mean_wind_dir   | Direction the wind is blowing from, clockwise from true north. | °    |
| {term}`wind_speed`              | mean_wind_speed | Mean speed of the wind over the period.                        | kn   |
| {term}`wind_direction_gust_max` | max_gust_dir    | Direction the strongest gust of the period blew from.          | °    |
| {term}`wind_gust_max`           | max_gust_speed  | Speed of the strongest gust of the period.                     | kn   |

### radiation

#### metadata

| property      | value            |
|---------------|------------------|
| name          | radiation        |
| original name | uk-radiation-obs |

#### parameters

| name                                     | original name | description                                                                                 | unit  |
|------------------------------------------|---------------|---------------------------------------------------------------------------------------------|-------|
| {term}`radiation_global`                 | glbl_irad_amt | Global radiation received on a horizontal surface, accumulated as energy over the interval. | kJ/m² |
| {term}`radiation_sky_short_wave_diffuse` | difu_irad_amt | Diffuse short-wave radiation from the sky, accumulated as energy over the interval.         | kJ/m² |
| {term}`radiation_sky_short_wave_direct`  | direct_irad   | Direct short-wave radiation from the sun, accumulated as energy over the interval.          | kJ/m² |

### soil_temperature

#### metadata

| property      | value                   |
|---------------|-------------------------|
| name          | soil_temperature        |
| original name | uk-soil-temperature-obs |

#### parameters

| name                                | original name    | description                            | unit |
|-------------------------------------|------------------|----------------------------------------|------|
| {term}`temperature_soil_mean_0_05m` | q5cm_soil_temp   | Mean soil temperature at 0.05 m depth. | °C   |
| {term}`temperature_soil_mean_0_1m`  | q10cm_soil_temp  | Mean soil temperature at 0.1 m depth.  | °C   |
| {term}`temperature_soil_mean_0_2m`  | q20cm_soil_temp  | Mean soil temperature at 0.2 m depth.  | °C   |
| {term}`temperature_soil_mean_0_5m`  | q50cm_soil_temp  | Mean soil temperature at 0.5 m depth.  | °C   |
| {term}`temperature_soil_mean_1m`    | q100cm_soil_temp | Mean soil temperature at 1 m depth.    | °C   |
