# annual

## metadata

| property      | value                                                                                        |
|---------------|----------------------------------------------------------------------------------------------|
| name          | annual                                                                                       |
| original name | annual                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/) |

## datasets

### climate_indices

#### metadata

| property      | value |
|---------------|-------|
| name          | climate_indices |
| original name | climate_indices/kl |
| description   | Historical annual counts of tropical nights and of frost, summer, hot and ice days for Germany, derived from the daily climate observations. |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/climate_indices/kl/) |

#### parameters

| name | original name | description | unit | constraints |
|------|---------------|-------------|------|-------------|
| {term}`count_days_tropical_night` | ja_tropennaechte | Annual number of tropical nights, counted over the day from 00 to 23 hours. | dimensionless | >=0 |
| {term}`count_days_frost` | ja_frosttage | Annual number of frost days. | dimensionless | >=0 |
| {term}`count_days_summer` | ja_sommertage | Annual number of summer days. | dimensionless | >=0 |
| {term}`count_days_hot` | ja_heisse_tage | Annual number of hot days. | dimensionless | >=0 |
| {term}`count_days_ice` | ja_eistage | Annual number of ice days. | dimensionless | >=0 |
| {term}`quality_general` | qn_4 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

### climate_summary

#### metadata

| property      | value                                                                                                                                                                                                                                                                  |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | climate_summary                                                                                                                                                                                                                                                        |
| original name | kl                                                                                                                                                                                                                                                                     |
| description   | Historical annual station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/kl/)                                                                                                                                                                        |

#### parameters

| name                                | original name | description                                             | unit | constraints |
|-------------------------------------|---------------|---------------------------------------------------------|------|-------------|
| {term}`cloud_cover_total` | ja_n | Annual mean of cloud cover. | 1/8 | >=0,<=8 |
| {term}`temperature_air_mean_2m` | ja_tt | Annual mean of daily temperature means in 2m height. | °C | - |
| {term}`temperature_air_max_2m_mean` | ja_tx | Annual mean of daily temperature maxima in 2m height. | °C | - |
| {term}`temperature_air_min_2m_mean` | ja_tn | Annual mean of daily temperature minima in 2m height. | °C | - |
| {term}`sunshine_duration` | ja_sd_s | Annual sum of sunshine duration. | h | >=0 |
| {term}`wind_force_beaufort` | ja_fk | Annual mean of daily wind speed. | Bft | >=0 |
| {term}`temperature_air_max_2m` | ja_mx_tx | Annual maximum of daily temperature maxima in 2m height. | °C | - |
| {term}`wind_gust_max` | ja_mx_fx | Annual maximum of daily wind speed. | Bft | >=0 |
| {term}`temperature_air_min_2m` | ja_mx_tn | Annual minimum of daily temperature minima in 2m height. | °C | - |
| {term}`precipitation_height` | ja_rr | Annual sum of daily precipitation height. | mm | >=0 |
| {term}`precipitation_height_max` | ja_mx_rs | Annual max of daily precipitation height. | mm | >=0 |
| {term}`quality_general` | qn_4 | Quality flag published by the source, applying to the dataset as a whole. | dimensionless | - |
| {term}`quality_precipitation` | qn_6 | Quality flag published by the source for `precipitation` in the same dataset. | dimensionless | - |

### precipitation_indices

#### metadata

| property      | value |
|---------------|-------|
| name          | precipitation_indices |
| original name | climate_indices/precip |
| description   | Historical annual counts of days reaching precipitation heights of 0.1 to 20 mm and snow depths of 1 and 5 cm for Germany, derived from the daily precipitation observations. |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/climate_indices/precip/) |

#### parameters

| name | original name | description | unit | constraints |
|------|---------------|-------------|------|-------------|
| {term}`count_days_precipitation_height_ge_0_1mm` | ja_rr_ge_0_1_mm | Annual number of days with a precipitation height of at least 0.1 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_1mm` | ja_rr_ge_1_0_mm | Annual number of days with a precipitation height of at least 1.0 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_2_5mm` | ja_rr_ge_2_5_mm | Annual number of days with a precipitation height of at least 2.5 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_5mm` | ja_rr_ge_5_0_mm | Annual number of days with a precipitation height of at least 5.0 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_10mm` | ja_rr_ge_10_0_mm | Annual number of days with a precipitation height of at least 10.0 mm. | dimensionless | >=0 |
| {term}`count_days_precipitation_height_ge_20mm` | ja_rr_ge_20_0_mm | Annual number of days with a precipitation height of at least 20.0 mm. | dimensionless | >=0 |
| {term}`count_days_snow_depth_ge_1cm` | ja_sh_ge_1_0_cm | Annual number of days with a snow depth of at least 1.0 cm. | dimensionless | >=0 |
| {term}`count_days_snow_depth_ge_5cm` | ja_sh_ge_5_0_cm | Annual number of days with a snow depth of at least 5.0 cm. | dimensionless | >=0 |
| {term}`quality` | qn_6 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

### precipitation_more

#### metadata

| property      | value                                                                                                                                                                                                        |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation_more                                                                                                                                                                                           |
| original name | more_precip                                                                                                                                                                                                  |
| description   | Historical annual precipitation observations for Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/more_precip/)                                                                                                     |

#### parameters

| name                             | original name | description                              | unit | constraints |
|----------------------------------|---------------|------------------------------------------|------|-------------|
| {term}`snow_depth_new` | ja_nsh | Annual sum of daily fresh snow. | cm | >=0 |
| {term}`precipitation_height` | ja_rr | Annual sum of daily precipitation height. | mm | >=0 |
| {term}`snow_depth` | ja_sh_s | Annual sum of daily height of snow pack. | cm | >=0 |
| {term}`precipitation_height_max` | ja_mx_rs | Annual max of daily precipitation height. | mm | >=0 |
| {term}`quality` | qn_6 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                                                                                  |
| original name | weather_phenomena                                                                                                                                                                                                                                                                                  |
| description   | Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/weather_phenomena/)                                                                                                                                                                                     |

#### parameters

| name                                           | original name | description                                                     | unit | constraints |
|------------------------------------------------|---------------|-----------------------------------------------------------------|------|-------------|
| {term}`count_weather_type_fog` | ja_nebel | Count of days with fog of stations in Germany. | - | >=0 |
| {term}`count_weather_type_thunder` | ja_gewitter | Count of days with thunder of stations in Germany. | - | >=0 |
| {term}`count_weather_type_storm_strong_wind` | ja_sturm_6 | Count of days with storm (strong wind) of stations in Germany. | - | >=0 |
| {term}`count_weather_type_storm_stormier_wind` | ja_sturm_8 | Count of days with storm (stormier wind) of stations in Germany. | - | >=0 |
| {term}`count_weather_type_dew` | ja_tau | Count of days with dew of stations in Germany. | - | >=0 |
| {term}`count_weather_type_glaze` | ja_glatteis | Count of days with glaze of stations in Germany. | - | >=0 |
| {term}`count_weather_type_sleet` | ja_graupel | Count of days with sleet of stations in Germany. | - | >=0 |
| {term}`count_weather_type_hail` | ja_hagel | Count of days with hail of stations in Germany. | - | >=0 |
| {term}`quality` | qn_4 | Quality flag published by the source for the values in the same dataset. | dimensionless | - |
