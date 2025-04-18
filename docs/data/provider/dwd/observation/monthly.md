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

| name                        | original name | description                                              | unit type     | unit | constraints |
|-----------------------------|---------------|----------------------------------------------------------|---------------|------|-------------|
| cloud_cover_total           | mo_n          | monthly mean of cloud cover                              | fraction      | 1/8  | >=0,<=8     |
| temperature_air_mean_2m     | mo_tt         | monthly mean of daily temperature means in 2m height     | temperature   | °C   | -           |
| temperature_air_max_2m_mean | mo_tx         | monthly mean of daily temperature maxima in 2m height    | temperature   | °C   | -           |
| temperature_air_min_2m_mean | mo_tn         | monthly mean of daily temperature minima in 2m height    | temperature   | °C   | -           |
| sunshine_duration           | mo_sd_s       | monthly sum of sunshine duration                         | time          | h    | >=0         |
| wind_force_beaufort         | mo_fk         | monthly mean of daily wind speed                         | wind_scale    | Bft  | >=0         |
| temperature_air_max_2m      | mx_tx         | monthly maximum of daily temperature maxima in 2m height | temperature   | °C   | -           |
| wind_gust_max               | mx_fx         | monthly maximum of daily wind speed                      | wind_scale    | Bft  | >=0         |
| temperature_air_min_2m      | mx_tn         | monthly minimum of daily temperature minima in 2m height | temperature   | °C   | -           |
| precipitation_height        | mo_rr         | monthly sum of precipitation height                      | precipitation | mm   | >=0         |
| precipitation_height_max    | mx_rs         | monthly maximum of daily precipitation height            | precipitation | mm   | >=0         |

### precipitation_more

#### metadata

| property      | value                                                                                                                                                                                                                  |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation_more                                                                                                                                                                                                     |
| original name | more_precip                                                                                                                                                                                                            |
| description   | Monthly precipitation observations for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/more_precip/DESCRIPTION_obsgermany-climate-monthly-more_precip_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/more_precip/)                                                                                                              |

#### parameters

| name                     | original name | description                               | unit type     | unit          | constraints |
|--------------------------|---------------|-------------------------------------------|---------------|---------------|-------------|
| snow_depth_new           | mo_nsh        | monthly sum of daily fresh snow           | length_short  | cm            | >=0         |
| precipitation_height     | mo_rr         | monthly sum of daily precipitation height | precipitation | mm            | >=0         |
| snow_depth               | mo_sh_s       | monthly sum of daily height of snow pack  | length_short  | cm            | >=0         |
| precipitation_height_max | mx_rs         | monthly max of daily precipitation height | precipitation | mm            | >=0         |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                                                                                  |
| original name | weather_phenomena                                                                                                                                                                                                                                                                                  |
| description   | Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/weather_phenomena/)                                                                                                                                                                                    |

#### parameters

| name                                   | original name | description                                                     | unit type     | unit | constraints |
|----------------------------------------|---------------|-----------------------------------------------------------------|---------------|------|-------------|
| count_weather_type_fog                 | mo_nebel      | count of days with fog of stations in Germany                   | dimensionless | -    | >=0         |
| count_weather_type_thunder             | mo_gewitter   | count of days with thunder of stations in Germany               | dimensionless | -    | >=0         |
| count_weather_type_storm_strong_wind   | mo_sturm_6    | count of days with storm (strong wind) of stations in Germany   | dimensionless | -    | >=0         |
| count_weather_type_storm_stormier_wind | mo_sturm_8    | count of days with storm (stormier wind) of stations in Germany | dimensionless | -    | >=0         |
| count_weather_type_dew                 | mo_tau        | count of days with dew of stations in Germany                   | dimensionless | -    | >=0         |
| count_weather_type_glaze               | mo_glatteis   | count of days with glaze of stations in Germany                 | dimensionless | -    | >=0         |
| count_weather_type_sleet               | mo_graupel    | count of days with sleet of stations in Germany                 | dimensionless | -    | >=0         |
| count_weather_type_hail                | mo_hagel      | count of days with hail of stations in Germany                  | dimensionless | -    | >=0         |
