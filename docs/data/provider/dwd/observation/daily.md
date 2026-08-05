# daily

## metadata

| property      | value                                                                                       |
|---------------|---------------------------------------------------------------------------------------------|
| name          | daily                                                                                       |
| original name | daily                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/) |

## datasets

### climate_summary

#### metadata

| property      | value                                                                                                                                                                                                                                                    |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | climate_summary                                                                                                                                                                                                                                          |
| original name | kl                                                                                                                                                                                                                                                       |
| description   | Daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/DESCRIPTION_obsgermany-climate-daily-kl_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/)                                                                                                                                                           |

#### parameters

| name                              | original name | description                                          | unit | constraints |
|-----------------------------------|---------------|------------------------------------------------------|------|-------------|
| {term}`wind_gust_max`             | fx            | daily maximum of wind gust                           | m/s  | >=0         |
| {term}`wind_speed`                | fm            | daily mean of wind speed                             | m/s  | >=0         |
| {term}`precipitation_height`      | rsk           | daily precipitation height                           | mm   | >=0         |
| {term}`precipitation_form`        | rskf          | precipitation form                                   | -    | >=0         |
| {term}`sunshine_duration`         | sdk           | daily sunshine duration                              | h    | >=0         |
| {term}`snow_depth`                | shk_tag       | daily snow depth                                     | cm   | >=0         |
| {term}`cloud_cover_total`         | nm            | daily mean of cloud cover                            | 1/8  | >=0,<=8     |
| {term}`pressure_vapor`            | vpm           | daily mean of vapor pressure                         | hPa  | >=0         |
| {term}`pressure_air_site`         | pm            | daily mean of pressure                               | hPa  | >=0         |
| {term}`temperature_air_mean_2m`   | tmk           | daily mean of temperature                            | °C   | -           |
| {term}`humidity`                  | upm           | daily mean of relative humidity                      | %    | >=0,<=100   |
| {term}`temperature_air_max_2m`    | txk           | daily maximum of temperature at 2m height            | °C   | -           |
| {term}`temperature_air_min_2m`    | tnk           | daily minimum of temperature at 2m height            | °C   | -           |
| {term}`temperature_air_min_0_05m` | tgk           | daily minimum of air temperature at 5cm above ground | °C   | -           |

Codes (precipitation_form):

| code | meaning                                                                                                            |
|------|--------------------------------------------------------------------------------------------------------------------|
| 0    | no precipitation (conventional or automatic measurement), relates to WMO code 10                                   |
| 1    | only rain (before 1979)                                                                                            |
| 4    | unknown form of recorded precipitation                                                                             |
| 6    | only rain; only liquid precipitation at automatic stations, relates to WMO code 11                                 |
| 7    | only snow; only solid precipitation at automatic stations, relates to WMO code 12                                  |
| 8    | rain and snow (and/or "Schneeregen"); liquid and solid precipitation at automatic stations, relates to WMO code 13 |
| 9    | error or missing value or no automatic determination of precipitation form, relates to WMO code 15                 |

### precipitation_more

#### metadata

| property      | value                                                                                                                                                                                                            |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation_more                                                                                                                                                                                               |
| original name | more_precip                                                                                                                                                                                                      |
| description   | Daily precipitation observations for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/DESCRIPTION_obsgermany-climate-daily-more_precip_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/)                                                                                                          |

#### parameters

| name                         | original name | description                | unit | constraints |
|------------------------------|---------------|----------------------------|------|-------------|
| {term}`precipitation_height` | rs            | daily precipitation height | mm   | >=0         |
| {term}`precipitation_form`   | rsf           | precipitation form         | -    | >=0         |
| {term}`snow_depth`           | sh_tag        | height of snow pack        | cm   | >=0         |
| {term}`snow_depth_new`       | nsh_tag       | fresh snow depth           | cm   | >=0         |

Codes (precipitation_form):

| code | meaning                                                                    |
|------|----------------------------------------------------------------------------|
| 0    | no precipitation (conventional or automatic measurement)                   |
| 1    | only rain (before 1979)                                                    |
| 4    | unknown form of recorded precipitation                                     |
| 6    | only rain; only liquid precipitation at automatic stations                 |
| 7    | only snow; only solid precipitation at automatic stations                  |
| 8    | rain and snow (and/or "Schneeregen")                                       |
| 9    | error or missing value or no automatic determination of precipitation form |

### solar

#### metadata

| property      | value                                                                                                                                                                                                                                                            |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | solar                                                                                                                                                                                                                                                            |
| original name | solar                                                                                                                                                                                                                                                            |
| description   | Daily station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/solar/DESCRIPTION_obsgermany-climate-daily-solar_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/solar/)                                                                                                                                                                |

#### parameters

| name                                     | original name | description                           | unit  | constraints |
|------------------------------------------|---------------|---------------------------------------|-------|-------------|
| {term}`radiation_sky_long_wave`          | atmo_strahl   | longwave downward radiation           | J/cm² | >=0         |
| {term}`radiation_sky_short_wave_diffuse` | fd_strahl     | daily sum of diffuse solar radiation  | J/cm² | >=0         |
| {term}`radiation_global`                 | fg_strahl     | daily sum of solar incoming radiation | J/cm² | >=0         |
| {term}`sunshine_duration`                | sd_strahl     | daily sum of sunshine duration        | h     | >=0         |

### temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                                                 |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_soil                                                                                                                                                                                                                                      |
| original name | soil_temperature                                                                                                                                                                                                                                      |
| description   | Daily station observations of soil temperature station data for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/soil_temperature/DESCRIPTION_obsgermany-climate-daily-soil_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/soil_temperature/)                                                                                                                                          |

#### parameters

| name                                | original name | description                            | unit | constraints |
|-------------------------------------|---------------|----------------------------------------|------|-------------|
| {term}`temperature_soil_mean_0_02m` | v_te002m      | daily soil temperature in 2 cm depth   | °C   | -           |
| {term}`temperature_soil_mean_0_05m` | v_te005m      | daily soil temperature in 5 cm depth   | °C   | -           |
| {term}`temperature_soil_mean_0_1m`  | v_te010m      | daily soil temperature in 10 cm depth  | °C   | -           |
| {term}`temperature_soil_mean_0_2m`  | v_te020m      | daily soil temperature in 20 cm depth  | °C   | -           |
| {term}`temperature_soil_mean_0_5m`  | v_te050m      | daily soil temperature in 50 cm depth  | °C   | -           |
| {term}`temperature_soil_mean_1m`    | v_te100m      | daily soil temperature in 100 cm depth | °C   | -           |

### water_equivalent

#### metadata

| property      | value                                                                                                                                                                                                                                  |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | water_equivalent                                                                                                                                                                                                                       |
| original name | water_equiv                                                                                                                                                                                                                            |
| description   | Daily observations of snow height and water equivalent for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/water_equiv/DESCRIPTION_f62e277b-00f5-4be8-95a4-0c598d869e5a_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/water_equiv/)                                                                                                                                |

#### parameters

| name                                         | original name | description                        | unit | constraints |
|----------------------------------------------|---------------|------------------------------------|------|-------------|
| {term}`snow_depth_excelled`                  | ash_6         | height of snow pack sample         | cm   | >=0         |
| {term}`snow_depth`                           | sh_tag        | total snow depth                   | cm   | >=0         |
| {term}`water_equivalent_snow_depth`          | wash_6        | total snow water equivalent        | mm   | >=0         |
| {term}`water_equivalent_snow_depth_excelled` | waas_6        | sampled snow pack water equivalent | mm   | >=0         |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                                                                                  |
| original name | weather_phenomena                                                                                                                                                                                                                                                                                  |
| description   | Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/weather_phenomena/)                                                                                                                                                                                      |

#### parameters

| name                                           | original name | description                                                     | unit | constraints |
|------------------------------------------------|---------------|-----------------------------------------------------------------|------|-------------|
| {term}`count_weather_type_fog`                 | nebel         | count of days with fog of stations in Germany                   | -    | >=0         |
| {term}`count_weather_type_thunder`             | gewitter      | count of days with thunder of stations in Germany               | -    | >=0         |
| {term}`count_weather_type_storm_strong_wind`   | sturm_6       | count of days with storm (strong wind) of stations in Germany   | -    | >=0         |
| {term}`count_weather_type_storm_stormier_wind` | sturm_8       | count of days with storm (stormier wind) of stations in Germany | -    | >=0         |
| {term}`count_weather_type_dew`                 | tau           | count of days with dew of stations in Germany                   | -    | >=0         |
| {term}`count_weather_type_glaze`               | glatteis      | count of days with glaze of stations in Germany                 | -    | >=0         |
| {term}`count_weather_type_ripe`                | reif          | count of days with ripe of stations in Germany                  | -    | >=0         |
| {term}`count_weather_type_sleet`               | graupel       | count of days with sleet of stations in Germany                 | -    | >=0         |
| {term}`count_weather_type_hail`                | hagel         | count of days with hail of stations in Germany                  | -    | >=0         |

### weather_phenomena_more

#### metadata

| property      | value                                                                                                                                                                                                                                             |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena_more                                                                                                                                                                                                                            |
| original name | more_weather_phenomena                                                                                                                                                                                                                            |
| description   | Counts of (additional) weather phenomena sleet, hail, fog and thunder for stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_weather_phenomena/)                                                                                                                                |

#### parameters

| name                               | original name | description                                       | unit | constraints |
|------------------------------------|---------------|---------------------------------------------------|------|-------------|
| {term}`count_weather_type_sleet`   | rr_graupel    | count of days with sleet of stations in Germany   | -    | >=0         |
| {term}`count_weather_type_hail`    | rr_hagel      | count of days with hail of stations in Germany    | -    | >=0         |
| {term}`count_weather_type_fog`     | rr_nebel      | count of days with fog of stations in Germany     | -    | >=0         |
| {term}`count_weather_type_thunder` | rr_gewitter   | count of days with thunder of stations in Germany | -    | >=0         |
