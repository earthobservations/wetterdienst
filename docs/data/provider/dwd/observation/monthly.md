# monthly

## metadata

| property      | value                                                                                         |
|---------------|-----------------------------------------------------------------------------------------------|
| name          | monthly                                                                                       |
| original name | monthly                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/) |

## datasets

### climate_indices

#### metadata

| property      | value |
|---------------|-------|
| name          | climate_indices |
| original name | climate_indices/kl |
| description   | Historical monthly counts of tropical nights and of frost, summer, hot and ice days for Germany, derived from the daily climate observations. |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/climate_indices/kl/) |

#### parameters

| name | original name | description | unit | constraints |
|------|---------------|-------------|------|-------------|
| {term}`count_days_tropical_night` | mo_tropennaechte | Monthly number of tropical nights, counted over the day from 00 to 23 hours. | dimensionless | >=0 |
| {term}`count_days_frost` | mo_frosttage | Monthly number of frost days. | dimensionless | >=0 |
| {term}`count_days_summer` | mo_sommertage | Monthly number of summer days. | dimensionless | >=0 |
| {term}`count_days_hot` | mo_heisse_tage | Monthly number of hot days. | dimensionless | >=0 |
| {term}`count_days_ice` | mo_eistage | Monthly number of ice days. | dimensionless | >=0 |
| {term}`quality_general` | qn_4 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

### climate_summary

#### metadata

| property      | value                                                                                                                                                                                                                                                                |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | climate_summary                                                                                                                                                                                                                                                      |
| original name | kl                                                                                                                                                                                                                                                                   |
| description   | Monthly station observations (temperature, precipitation, sunshine duration, wind and cloud cover) for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/kl/DESCRIPTION_obsgermany-climate-monthly-kl_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/kl/)                                                                                                                                                                     |

#### parameters

| name                                | original name | description                                              | unit | constraints |
|-------------------------------------|---------------|----------------------------------------------------------|------|-------------|
| {term}`cloud_cover_total` | mo_n | Monthly mean of cloud cover. | 1/8 | >=0,<=8 |
| {term}`temperature_air_mean_2m` | mo_tt | Monthly mean of the daily mean air temperature 2 m above ground. | °C | - |
| {term}`temperature_air_max_2m_mean` | mo_tx | Monthly mean of daily temperature maxima at 2 m above ground. | °C | - |
| {term}`temperature_air_min_2m_mean` | mo_tn | Monthly mean of daily temperature minima in 2 m above ground. | °C | - |
| {term}`sunshine_duration` | mo_sd_s | Monthly sum of sunshine duration. | h | >=0 |
| {term}`wind_force_beaufort` | mo_fk | Monthly mean of daily wind speed Bft. | Bft | >=0 |
| {term}`temperature_air_max_2m` | mx_tx | Monthly maximum of daily temperature maxima in 2 m above ground. | °C | - |
| {term}`wind_gust_max` | mx_fx | Monthly maximum of daily wind speed. | Bft | >=0 |
| {term}`temperature_air_min_2m` | mx_tn | Monthly minimum of daily temperature minima in 2 m above ground. | °C | - |
| {term}`precipitation_height` | mo_rr | Monthly sum of precipitation height. | mm | >=0 |
| {term}`precipitation_height_max` | mx_rs | Monthly maximum of daily precipitation height. | mm | >=0 |
| {term}`quality_general` | qn_4 | Quality level of the data in the following columns. | dimensionless | - |
| {term}`quality_precipitation` | qn_6 | Quality level of the data in the following columns. | dimensionless | - |

### precipitation_indices

#### metadata

| property      | value |
|---------------|-------|
| name          | precipitation_indices |
| original name | climate_indices/precip |
| description   | Historical monthly counts of days reaching precipitation heights of 0.1 to 20 mm and snow depths of 1 and 5 cm for Germany, derived from the daily precipitation observations. |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/climate_indices/precip/) |

#### parameters

| name | original name | description | unit | constraints |
|------|---------------|-------------|------|-------------|
| {term}`count_days_precipitation_height_ge_0_1mm` | mo_rr_ge_0_1_mm | Monthly number of days with a precipitation height of at least 0.1 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_1mm` | mo_rr_ge_1_0_mm | Monthly number of days with a precipitation height of at least 1.0 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_2_5mm` | mo_rr_ge_2_5_mm | Monthly number of days with a precipitation height of at least 2.5 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_5mm` | mo_rr_ge_5_0_mm | Monthly number of days with a precipitation height of at least 5.0 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_10mm` | mo_rr_ge_10_0_mm | Monthly number of days with a precipitation height of at least 10.0 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_20mm` | mo_rr_ge_20_0_mm | Monthly number of days with a precipitation height of at least 20.0 mm. | dimensionless | >=0 |
| {term}`count_days_snow_depth_ge_1cm` | mo_sh_ge_1_0_cm | Monthly number of days with a snow depth of at least 1.0 cm. | dimensionless | >=0 |
| {term}`count_days_snow_depth_ge_5cm` | mo_sh_ge_5_0_cm | Monthly number of days with a snow depth of at least 5.0 cm. | dimensionless | >=0 |
| {term}`quality` | qn_6 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

### precipitation_more

#### metadata

| property      | value                                                                                                                                                                                                                  |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation_more                                                                                                                                                                                                     |
| original name | more_precip                                                                                                                                                                                                            |
| description   | Monthly precipitation observations for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/more_precip/DESCRIPTION_obsgermany-climate-monthly-more_precip_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/more_precip/)                                                                                                              |

#### parameters

| name                             | original name | description                               | unit | constraints |
|----------------------------------|---------------|-------------------------------------------|------|-------------|
| {term}`snow_depth_new` | mo_nsh | Monthly sum of daily fresh snow. | cm | >=0 |
| {term}`precipitation_height` | mo_rr | Monthly sum of precipitation height. | mm | >=0 |
| {term}`snow_depth` | mo_sh_s | Monthly sum of daily height of snow pack. | cm | >=0 |
| {term}`precipitation_height_max` | mx_rs | Monthly maximum of daily precipitation height. | mm | >=0 |
| {term}`quality` | qn_6 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                                                                                  |
| original name | weather_phenomena                                                                                                                                                                                                                                                                                  |
| description   | Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/weather_phenomena/)                                                                                                                                                                                    |

#### parameters

| name                                           | original name | description                                                     | unit | constraints |
|------------------------------------------------|---------------|-----------------------------------------------------------------|------|-------------|
| {term}`count_weather_type_fog` | mo_nebel | Count of days with fog of stations in Germany. | - | >=0 |
| {term}`count_weather_type_thunder` | mo_gewitter | Count of days with thunder of stations in Germany. | - | >=0 |
| {term}`count_weather_type_storm_strong_wind` | mo_sturm_6 | Count of days with storm (strong wind) of stations in Germany. | - | >=0 |
| {term}`count_weather_type_storm_stormier_wind` | mo_sturm_8 | Count of days with storm (stormier wind) of stations in Germany. | - | >=0 |
| {term}`count_weather_type_dew` | mo_tau | Count of days with dew of stations in Germany. | - | >=0 |
| {term}`count_weather_type_glaze` | mo_glatteis | Count of days with glaze of stations in Germany. | - | >=0 |
| {term}`count_weather_type_sleet` | mo_graupel | Count of days with sleet of stations in Germany. | - | >=0 |
| {term}`count_weather_type_hail` | mo_hagel | Count of days with hail of stations in Germany. | - | >=0 |
| {term}`quality` | qn_4 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |
