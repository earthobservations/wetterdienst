# monthly

## metadata

| property      | value                                                                                         |
|---------------|-----------------------------------------------------------------------------------------------|
| name          | monthly                                                                                       |
| original name | monthly                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/) |

## datasets

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
