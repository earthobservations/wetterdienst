# hourly

## metadata

| property      | value                                                                                     |
|---------------|-------------------------------------------------------------------------------------------|
| name          | hourly                                                                                    |
| original name | hourly                                                                                    |
| url           | [here](https://www.dwd.de/DE/leistungen/met_verfahren_ptp_dmo/met_verfahren_ptp_dmo.html) |

## datasets

### icon_eu

#### metadata

| property         | value                                                                                                                                                                                                                                          |
|------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | icon_eu                                                                                                                                                                                                                                        |
| original name    | icon_eu                                                                                                                                                                                                                                        |
| description      | Direct model output of the regional ICON-EU model, extracted at the stations it is published for, a smaller set than the global product's though not a subset of it. Issued twice a day (00 and 12 UTC), hourly out to a lead-time of 78 hours |
| description file | [here](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)                                                                                                                                                                           |
| access           | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon-eu/)                                                                                                                                                                           |

#### parameters

| name                                            | original name | description                                    | unit  | constraints |
|-------------------------------------------------|---------------|------------------------------------------------|-------|-------------|
| {term}`cloud_cover_above_7km`                   | nh            | High cloud cover (>7 km)                       | %     | >=0,<=100   |
| {term}`cloud_cover_below_2km`                   | nl            | Low cloud cover (lower than 2 km).             | %     | >=0,<=100   |
| {term}`cloud_cover_between_2km_and_7km`         | nm            | Midlevel cloud cover (2-7 km)                  | %     | >=0,<=100   |
| {term}`cloud_cover_effective`                   | neff          | Effective cloud cover                          | %     | >=0,<=100   |
| {term}`cloud_cover_total`                       | n             | Total cloud cover                              | %     | >=0,<=100   |
| {term}`precipitation_amount_last_1h`            | rr1           | Total precipitation during the last hour. Direct model output, not clipped at 0: a step can be up to about a tenth of a mm below it and is returned as written. | kg/m² | >=0         |
| {term}`pressure_air_sea_level`                  | pppp          | Surface pressure, reduced                      | Pa    | >=0         |
| {term}`radiation_global`                        | rad1h         | Global Irradiance, as the energy of the last hour: the DMO values are in J/cm2 (the file states no unit; they are about a tenth of the MOSMIX kJ/m2 number for the same hour). Direct model output, not clipped at 0: in the night hours it is often a little below it (mostly above -0.2 J/cm2, at a few stations to about -0.8) and is returned as written.   | J/cm² | >=0         |
| {term}`temperature_air_max_2m_last_12h`                  | tx            | Maximum temperature - within the last 12 hours | K     | -           |
| {term}`temperature_air_0_05m`                   | t5cm          | Temperature 5cm above surface                  | K     | -           |
| {term}`temperature_air_2m`                      | ttt           | Temperature 2m above surface                   | K     | -           |
| {term}`temperature_air_min_2m_last_12h`                  | tn            | Minimum temperature - within the last 12 hours | K     | -           |
| {term}`temperature_dew_point_2m`                | td            | Dewpoint 2m above surface                      | K     | -           |
| {term}`water_equivalent_snow_depth_new_last_1h` | rrs1c         | Snow-Rain-Equivalent during the last hour      | kg/m² | >=0         |
| {term}`weather_last_6h`                         | w1w2          | Past weather during the last 6 hours, as a class of DWD's MOSMIX list (the DMO values fit it): 9 thunderstorm, 8 shower, 7 snow or rain and snow mixed, 6 rain, 5 drizzle, 4 fog, 3 to 0 the effective cloud cover (at least 7/8, 4.6/8 to 6/8, 1/8 to 4.5/8, below 1/8). DWD says of MOSMIX that 0 to 3 are not reliable and mean no thunderstorm, no precipitation and no fog. Given at 00, 06, 12 and 18 UTC. | -     | -           |
| {term}`weather_significant`                     | ww            | Significant Weather, as a code of DWD's MOSMIX list of codes (DWD publishes it as mosmix_element_weather_xls.xlsx; the DMO values fit it): 95 (thunderstorm) has the highest priority, then freezing drizzle and rain, showers, snowfall, rain and snow, drizzle, rain and fog, down to 3 to 0 (cloud development).  | -     | -           |
| {term}`wind_direction`                          | dd            | Wind direction                                 | °     | >=0,<=360   |
| {term}`wind_gust_max_last_3h`                   | fx3           | Maximum wind gust within the last 3 hours      | m/s   | >=0         |
| {term}`wind_speed`                              | ff            | Wind speed                                     | m/s   | >=0         |

### icon

#### metadata

| property         | value                                                                                                                                                                                                   |
|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | icon                                                                                                                                                                                                    |
| original name    | icon                                                                                                                                                                                                    |
| description      | Direct model output of the global ICON model, extracted at worldwide stations. Issued twice a day (00 and 12 UTC) as two runs: hourly out to a lead-time of 78 hours, and 3-hourly from 78 to 168 hours |
| description file | [here](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)                                                                                                                                    |
| access           | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon/)                                                                                                                                       |

#### parameters

| name                                            | original name | description                                          | unit  | constraints |
|-------------------------------------------------|---------------|------------------------------------------------------|-------|-------------|
| {term}`cloud_cover_above_7km`                   | nh            | High cloud cover (>7 km)                             | %     | >=0,<=100   |
| {term}`cloud_cover_below_2km`                   | nl            | Low cloud cover (lower than 2 km).                   | %     | >=0,<=100   |
| {term}`cloud_cover_between_2km_and_7km`         | nm            | Midlevel cloud cover (2-7 km)                        | %     | >=0,<=100   |
| {term}`cloud_cover_effective`                   | neff          | Effective cloud cover                                | %     | >=0,<=100   |
| {term}`cloud_cover_total`                       | n             | Total cloud cover                                    | %     | >=0,<=100   |
| {term}`precipitation_amount_last_1h`            | rr1           | Total precipitation during the last hour. Direct model output, not clipped at 0: a step can be up to about a tenth of a mm below it and is returned as written. | kg/m² | >=0         |
| {term}`precipitation_amount_last_3h`            | rr3           | Total precipitation during the last 3 hours. Direct model output, not clipped at 0: a step can be a few hundredths of a mm below it and is returned as written. | kg/m² | >=0         |
| {term}`pressure_air_sea_level`                  | pppp          | Surface pressure, reduced                            | Pa    | >=0         |
| {term}`radiation_global`                        | rad1h         | Global Irradiance, as the energy of the last hour: the DMO values are in J/cm2 (the file states no unit; they are about a tenth of the MOSMIX kJ/m2 number for the same hour). Direct model output, not clipped at 0: in the night hours it is often a little below it (mostly above -0.2 J/cm2, at a few stations to about -0.8) and is returned as written.   | J/cm² | >=0         |
| {term}`radiation_short_wave_net_last_3h`        | rads3         | Short wave radiation balance during the last 3 hours. Direct model output, not clipped at 0: in the night hours it is often a little below it (to about -0.4 J/cm2) and is returned as written. | J/cm² | -           |
| {term}`radiation_long_wave_net_last_3h`         | radl3         | Long wave radiation balance during the last 3 hours  | kJ/m² | -           |
| {term}`temperature_air_max_2m_last_12h`                  | tx            | Maximum temperature - within the last 12 hours       | K     | -           |
| {term}`temperature_air_0_05m`                   | t5cm          | Temperature 5cm above surface                        | K     | -           |
| {term}`temperature_air_2m`                      | ttt           | Temperature 2m above surface                         | K     | -           |
| {term}`temperature_air_min_2m_last_12h`                  | tn            | Minimum temperature - within the last 12 hours       | K     | -           |
| {term}`temperature_dew_point_2m`                | td            | Dewpoint 2m above surface                            | K     | -           |
| {term}`water_equivalent_snow_depth_new_last_1h` | rrs1c         | Snow-Rain-Equivalent during the last hour            | kg/m² | >=0         |
| {term}`water_equivalent_snow_depth_new_last_3h` | rrs3c         | Snow-Rain-Equivalent during the last 3 hours         | kg/m² | >=0         |
| {term}`weather_last_6h`                         | w1w2          | Past weather during the last 6 hours, as a class of DWD's MOSMIX list (the DMO values fit it): 9 thunderstorm, 8 shower, 7 snow or rain and snow mixed, 6 rain, 5 drizzle, 4 fog, 3 to 0 the effective cloud cover (at least 7/8, 4.6/8 to 6/8, 1/8 to 4.5/8, below 1/8). DWD says of MOSMIX that 0 to 3 are not reliable and mean no thunderstorm, no precipitation and no fog. Given at 00, 06, 12 and 18 UTC. | -     | -           |
| {term}`weather_significant`                     | ww            | Significant Weather, as a code of DWD's MOSMIX list of codes (DWD publishes it as mosmix_element_weather_xls.xlsx; the DMO values fit it): 95 (thunderstorm) has the highest priority, then freezing drizzle and rain, showers, snowfall, rain and snow, drizzle, rain and fog, down to 3 to 0 (cloud development).  | -     | -           |
| {term}`wind_direction`                          | dd            | Wind direction                                       | °     | >=0,<=360   |
| {term}`wind_gust_max_last_3h`                   | fx3           | Maximum wind gust within the last 3 hours            | m/s   | >=0         |
| {term}`wind_speed`                              | ff            | Wind speed                                           | m/s   | >=0         |
