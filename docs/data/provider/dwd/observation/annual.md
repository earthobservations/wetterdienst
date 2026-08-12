# annual

## metadata

| property      | value                                                                                        |
|---------------|----------------------------------------------------------------------------------------------|
| name          | annual                                                                                       |
| original name | annual                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/) |

## datasets

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
