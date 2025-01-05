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

| name                        | original name | description                                             | unit type     | unit | constraints |
|-----------------------------|---------------|---------------------------------------------------------|---------------|------|-------------|
| cloud_cover_total           | ja_n          | annual mean of cloud cover                              | fraction      | 1/8  | >=0,<=8     |
| temperature_air_mean_2m     | ja_tt         | annual mean of daily temperature means in 2m height     | temperature   | °C   | -           |
| temperature_air_max_2m_mean | ja_tx         | annual mean of daily temperature maxima in 2m height    | temperature   | °C   | -           |
| temperature_air_min_2m_mean | ja_tn         | annual mean of daily temperature minima in 2m height    | temperature   | °C   | -           |
| sunshine_duration           | ja_sd_s       | annual sum of sunshine duration                         | time          | h    | >=0         |
| wind_force_beaufort         | ja_fk         | annual mean of daily wind speed                         | wind_scale    | Bft  | >=0         |
| temperature_air_max_2m      | ja_mx_tx      | annual maximum of daily temperature maxima in 2m height | temperature   | °C   | -           |
| wind_gust_max               | ja_mx_fx      | annual maximum of daily wind speed                      | wind_scale    | Bft  | >=0         |
| temperature_air_min_2m      | ja_mx_tn      | annual minimum of daily temperature minima in 2m height | temperature   | °C   | -           |
| precipitation_height        | ja_rr         | annual sum of precipitation height                      | precipitation | mm   | >=0         |
| precipitation_height_max    | ja_mx_rs      | annual maximum of daily precipitation height            | precipitation | mm   | >=0         |

### precipitation_more

#### metadata

| property      | value                                                                                                                                                                                                        |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation_more                                                                                                                                                                                           |
| original name | more_precip                                                                                                                                                                                                  |
| description   | Historical annual precipitation observations for Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/more_precip/)                                                                                                     |

#### parameters

| name                     | original name | description                              | unit type     | unit          | constraints |
|--------------------------|---------------|------------------------------------------|---------------|---------------|-------------|
| snow_depth_new           | ja_nsh        | annual sum of daily fresh snow           | length_short  | cm            | >=0         |
| precipitation_height     | ja_rr         | annual sum of daily precipitation height | precipitation | mm            | >=0         |
| snow_depth               | ja_sh_s       | annual sum of daily height of snow pack  | length_short  | cm            | >=0         |
| precipitation_height_max | ja_mx_rs      | annual max of daily precipitation height | precipitation | mm            | >=0         |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                                                                                  |
| original name | weather_phenomena                                                                                                                                                                                                                                                                                  |
| description   | Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/weather_phenomena/)                                                                                                                                                                                     |

#### parameters

| name                                   | original name | description                                                     | unit type     | unit | constraints |
|----------------------------------------|---------------|-----------------------------------------------------------------|---------------|------|-------------|
| count_weather_type_fog                 | ja_nebel      | count of days with fog of stations in Germany                   | dimensionless | -    | >=0         |
| count_weather_type_thunder             | ja_gewitter   | count of days with thunder of stations in Germany               | dimensionless | -    | >=0         |
| count_weather_type_storm_strong_wind   | ja_sturm_6    | count of days with storm (strong wind) of stations in Germany   | dimensionless | -    | >=0         |
| count_weather_type_storm_stormier_wind | ja_sturm_8    | count of days with storm (stormier wind) of stations in Germany | dimensionless | -    | >=0         |
| count_weather_type_dew                 | ja_tau        | count of days with dew of stations in Germany                   | dimensionless | -    | >=0         |
| count_weather_type_glaze               | ja_glatteis   | count of days with glaze of stations in Germany                 | dimensionless | -    | >=0         |
| count_weather_type_sleet               | ja_graupel    | count of days with sleet of stations in Germany                 | dimensionless | -    | >=0         |
| count_weather_type_hail                | ja_hagel      | count of days with hail of stations in Germany                  | dimensionless | -    | >=0         |
