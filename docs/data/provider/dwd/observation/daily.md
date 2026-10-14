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
| {term}`quality_wind` | qn_3 | Quality level of the following columns. | -             | - |
| {term}`wind_gust_max` | fx | Daily maximum of windgust. | m/s | >=0 |
| {term}`wind_speed` | fm | Daily mean of wind velocity. | m/s | >=0 |
| {term}`quality_general` | qn_4 | Quality level of the following columns. | -             | - |
| {term}`precipitation_amount` | rsk | Daily precipitation height. | mm | >=0 |
| {term}`precipitation_form` | rskf | Precipitation form. | - | >=0 |
| {term}`sunshine_duration` | sdk | Daily sunshine duration. | h | >=0 |
| {term}`snow_depth` | shk_tag | Daily snow depth. | cm | >=0 |
| {term}`cloud_cover_total` | nm | Daily mean of cloud cover: the arithmetic mean of at least 21 hourly values, in earlier periods the mean of the observation terms (3 terms at most stations, 4 or 8 at some). | 1/8 | >=0,<=8 |
| {term}`pressure_vapor` | vpm | Daily mean of vapor pressure: the arithmetic mean of at least 21 hourly values, in earlier periods the mean of the observation terms (3 terms at most stations, 4 or 8 at some). | hPa | >=0 |
| {term}`pressure_air_site` | pm | Daily mean of pressure: the arithmetic mean of at least 21 hourly values, in earlier periods the mean of the observation terms (3 terms at most stations, 4 or 8 at some). | hPa | >=0 |
| {term}`temperature_air_mean_2m` | tmk | Daily mean of temperature: the arithmetic mean of at least 21 hourly values, in earlier periods the mean of the observation terms (3 terms at most stations, TT1 to TT3: TMK=(TT1+TT2+(TT3*2))/4; 4 or 8 at some). | °C | - |
| {term}`humidity_relative` | upm | Daily mean of relative humidity: the arithmetic mean of at least 21 hourly values, in earlier periods the mean of the observation terms (3 terms at most stations, 4 or 8 at some). | % | >=0,<=100 |
| {term}`temperature_air_max_2m` | txk | Daily maximum of temperature at 2 m height. | °C | - |
| {term}`temperature_air_min_2m` | tnk | Daily minimum of temperature at 2m height. | °C | - |
| {term}`temperature_air_min_0_05m` | tgk | Daily minimum of air temperature at 5 cm above ground. | °C | - |

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
| {term}`quality` | qn_6 | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`precipitation_amount` | rs | Daily precipitation height. | mm | >=0 |
| {term}`precipitation_form` | rsf | Precipitation form. | - | >=0 |
| {term}`snow_depth` | sh_tag | Height of snow pack. | cm | >=0 |
| {term}`snow_depth_new` | nsh_tag | Fresh snow depth. | cm | >=0 |

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
| {term}`quality` | qn_592 | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`radiation_sky_long_wave` | atmo_strahl | Daily sum of longwave downward radiation. | J/cm² | >=0 |
| {term}`radiation_sky_short_wave_diffuse` | fd_strahl | Daily sum of diffuse solar radiation. | J/cm² | >=0 |
| {term}`radiation_global` | fg_strahl | Daily sum of solar incoming radiation. | J/cm² | >=0 |
| {term}`sunshine_duration` | sd_strahl | Daily sum of sunshine duration. | h | >=0 |

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
| {term}`quality` | qn_2 | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`temperature_soil_mean_0_02m` | v_te002m | Daily soil temperature in 2 cm depth. | °C | - |
| {term}`temperature_soil_mean_0_05m` | v_te005m | Daily soil temperature in 5 cm depth. | °C | - |
| {term}`temperature_soil_mean_0_1m` | v_te010m | Daily soil temperature in 10 cm depth. | °C | - |
| {term}`temperature_soil_mean_0_2m` | v_te020m | Daily soil temperature in 20 cm depth. | °C | - |
| {term}`temperature_soil_mean_0_5m` | v_te050m | Daily soil temperature in 50 cm depth. | °C | - |

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
| {term}`snow_depth_sampled` | ash_6 | Height of the sampled snow pack. | cm | >=0 |
| {term}`snow_depth` | sh_tag | Height of the snow pack. | cm | >=0 |
| {term}`water_equivalent_snow_depth` | wash_6 | Water equivalent of the total snow pack. | mm | >=0 |
| {term}`water_equivalent_snow_depth_sampled` | waas_6 | Water equivalent of the sampled snow pack. | mm | >=0 |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                                                                                  |
| original name | weather_phenomena                                                                                                                                                                                                                                                                                  |
| description   | Daily weather events fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, hoar frost, graupel and hail at stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/weather_phenomena/)                                                                                                                                                                                      |

#### parameters

| name                                           | original name | description                                                     | unit | constraints |
|------------------------------------------------|---------------|-----------------------------------------------------------------|------|-------------|
| {term}`count_weather_type_fog` | nebel | Weather event: fog during the day (DWD: "Wetterereignis: Nebel im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_thunder` | gewitter | Weather event: thunderstorm during the day (DWD: "Wetterereignis: Gewitter im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_storm_strong_wind` | sturm_6 | Weather event: storm of at least 6 Bft during the day (DWD: "Wetterereignis: Sturm>=6 Bft im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_storm_stormier_wind` | sturm_8 | Weather event: storm of at least 8 Bft during the day (DWD: "Wetterereignis: Sturm>=8 Bft im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_dew` | tau | Weather event: dew during the day (DWD: "Wetterereignis: Tau im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_glaze` | glatteis | Weather event: glaze ice during the day (DWD: "Wetterereignis: Glatteis im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_hoar_frost` | reif | Weather event: hoar frost during the day (DWD: "Wetterereignis: Reif im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_graupel` | graupel | Weather event: graupel during the day (DWD: "Wetterereignis: Graupel im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_hail` | hagel | Weather event: hail during the day (DWD: "Wetterereignis: Hagel im Verlauf des Tages"). | - | >=0 |

### weather_phenomena_more

#### metadata

| property      | value                                                                                                                                                                                                                                             |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena_more                                                                                                                                                                                                                            |
| original name | more_weather_phenomena                                                                                                                                                                                                                            |
| description   | Daily (additional) weather events graupel, hail, fog and thunder at stations of Germany (details missing, parameter descriptions [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_weather_phenomena/)                                                                                                                                |

#### parameters

| name                               | original name | description                                       | unit | constraints |
|------------------------------------|---------------|---------------------------------------------------|------|-------------|
| {term}`count_weather_type_graupel` | rr_graupel | Weather event of the precipitation network: graupel during the day (DWD: "Wetterereignis_RR: Graupel im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_hail` | rr_hagel | Weather event of the precipitation network: hail during the day (DWD: "Wetterereignis_RR: Hagel im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_fog` | rr_nebel | Weather event of the precipitation network: fog during the day (DWD: "Wetterereignis_RR: Nebel im Verlauf des Tages"). | - | >=0 |
| {term}`count_weather_type_thunder` | rr_gewitter | Weather event of the precipitation network: thunderstorm during the day (DWD: "Wetterereignis_RR: Gewitter im Verlauf des Tages"). | - | >=0 |
