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

| property         | value                                                                                                |
|------------------|------------------------------------------------------------------------------------------------------|
| name             | icon_eu                                                                                              |
| original name    | icon-eu                                                                                              |
| description      | Local forecast of 40 parameters for worldwide stations, 24 times a day with a lead-time of 240 hours |
| description file | [here](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)                                 |
| access           | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon-eu/)                                 |

#### parameters

| name                                               | original name | description                                                                     | unit type       | unit          | constraints |
|----------------------------------------------------|---------------|---------------------------------------------------------------------------------|-----------------|---------------|-------------|
| cloud_base_convective                              | h_bsc         | Cloud base of convective clouds                                                 | length_medium   | m             | >=0         |
| cloud_cover_above_7km                              | nh            | High cloud cover (>7 km)                                                        | fraction        | %             | >=0,<=100   |
| cloud_cover_below_500ft                            | n05           | Cloud cover below 500 ft.                                                       | fraction        | %             | >=0,<=100   |
| cloud_cover_below_1000ft                           | n1            | Low cloud cover (lower than 2 km)                                               | fraction        | %             | >=0,<=100   |
| cloud_cover_below_7km                              | nlm           | Cloud cover low and mid level clouds below 7000 m                               | fraction        | %             | >=0,<=100   |
| cloud_cover_between_2km_to_7km                     | nm            | Midlevel cloud cover (2-7 km)                                                   | fraction        | %             | >=0,<=100   |
| cloud_cover_effective                              | neff          | Effective cloud cover                                                           | fraction        | %             | >=0,<=100   |
| cloud_cover_total                                  | n             | Total cloud cover                                                               | fraction        | %             | >=0,<=100   |
| precipitation_height_significant_weather_last_1h   | rr1c          | Total precipitation during the last hour consistent with significant weather    | precipitation   | kg/m²         | >=0         |
| precipitation_height_significant_weather_last_3h   | rr3c          | Total precipitation during the last 3 hours consistent with significant weather | precipitation   | kg/m²         | >=0         |
| pressure_air_site_reduced                          | pppp          | Surface pressure, reduced                                                       | pressure        | Pa            | >=0         |
| probability_fog_last_1h                            | wwm           | Probability for fog within the last hour                                        | fraction        | %             | >=0,<=100   |
| probability_fog_last_6h                            | wwm6          | Probability for fog within the last 6 hours                                     | fraction        | %             | >=0,<=100   |
| probability_fog_last_12h                           | wwmh          | Probability for fog within the last 12 hours                                    | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_0_0mm_last_12h | rh00          | Probability of precipitation > 0.0mm during the last 12 hours                   | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_0_2mm_last_6h  | r602          | Probability of precipitation > 0.2mm during the last 6 hours                    | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_0_2mm_last_12h | rh02          | Probability of precipitation > 0.2mm during the last 12 hours                   | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_0_2mm_last_24h | rd02          | Probability of precipitation > 0.2mm during the last 24 hours                   | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_1mm_last_12h   | rh10          | Probability of precipitation > 1.0mm during the last 12 hours                   | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_5mm_last_6h    | r650          | Probability of precipitation > 5.0mm during the last 6 hours                    | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_5mm_last_12h   | rh50          | Probability of precipitation > 5.0mm during the last 12 hours                   | fraction        | %             | >=0,<=100   |
| probability_precipitation_height_gt_5mm_last_24h   | rd50          | Probability of precipitation > 5.0mm during the last 24 hours                   | fraction        | %             | >=0,<=100   |
| probability_wind_gust_ge_25kn_last_12h             | fxh25         | Probability of wind gusts >= 25kn within the last 12 hours                      | fraction        | %             | >=0,<=100   |
| probability_wind_gust_ge_40kn_last_12h             | fxh40         | Probability of wind gusts >= 40kn within the last 12 hours                      | fraction        | %             | >=0,<=100   |
| probability_wind_gust_ge_55kn_last_12h             | fxh55         | Probability of wind gusts >= 55kn within the last 12 hours                      | fraction        | %             | >=0,<=100   |
| radiation_global                                   | rad1h         | Global Irradiance                                                               | energy_per_area | kJ/m²         | >=0         |
| sunshine_duration                                  | sund1         | Sunshine duration during the last Hour                                          | time            | s             | >=0         |
| temperature_air_max_2m                             | tx            | Maximum temperature - within the last 12 hours                                  | temperature     | K             | -           |
| temperature_air_mean_0_05m                         | t5cm          | Temperature 5cm above surface                                                   | temperature     | K             | -           |
| temperature_air_mean_2m                            | ttt           | Temperature 2m above surface                                                    | temperature     | K             | -           |
| temperature_air_min_2m                             | tn            | Minimum temperature - within the last 12 hours                                  | temperature     | K             | -           |
| temperature_dew_point_mean_2m                      | td            | Dewpoint 2m above surface                                                       | temperature     | K             | -           |
| visibility_range                                   | vv            | Visibility                                                                      | length_medium   | length_medium | >=0         |
| water_equivalent_snow_depth_new_last_1h            | rrs1c         | Snow-Rain-Equivalent during the last hour                                       | precipitation   | kg/m²         | >=0         |
| water_equivalent_snow_depth_new_last_3h            | rrs3c         | Snow-Rain-Equivalent during the last 3 hours                                    | precipitation   | kg/m²         | >=0         |
| weather_last_6h                                    | w1w2          | Past weather during the last 6 hours                                            | dimensionless   | -             | -           |
| weather_significant                                | ww            | Significant Weather                                                             | dimensionless   | -             | -           |
| wind_direction                                     | dd            | Wind direction                                                                  | angle           | °             | >=0,<=360   |
| wind_gust_max_last_1h                              | fx1           | Maximum wind gust within the last hour                                          | speed           | m/s           | >=0         |
| wind_gust_max_last_3h                              | fx3           | Maximum wind gust within the last 3 hours                                       | speed           | m/s           | >=0         |
| wind_gust_max_last_12h                             | fxh           | Maximum wind gust within the last 12 hours                                      | speed           | m/s           | >=0         |
| wind_speed                                         | ff            | Wind speed                                                                      | speed           | m/s           | >=0         |

### icon

#### metadata

| property         | value                                                                                                |
|------------------|------------------------------------------------------------------------------------------------------|
| name             | icon                                                                                                 |
| original name    | icon                                                                                                 |
| description      | Local forecast of 115 parameters for worldwide stations, 4 times a day with a lead-time of 240 hours |
| description file | [here](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)                                 |
| access           | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon/)                                    |

#### parameters

| name                                                     | original name | description                                                                         | unit type       | unit  | constraints |
|----------------------------------------------------------|---------------|-------------------------------------------------------------------------------------|-----------------|-------|-------------|
| cloud_cover_above_7km                                    | nh            | High cloud cover (>7 km)                                                            | fraction        | %     | >=0,<=100   |
| cloud_cover_below_500ft                                  | n05           | Cloud cover below 500 ft.                                                           | fraction        | %     | >=0,<=100   |
| cloud_cover_below_1000ft                                 | n1            | Low cloud cover (lower than 2 km)                                                   | fraction        | %     | >=0,<=100   |
| cloud_cover_between_2km_to_7km                           | nm            | Midlevel cloud cover (2-7 km)                                                       | fraction        | %     | >=0,<=100   |
| cloud_cover_effective                                    | neff          | Effective cloud cover                                                               | fraction        | %     | >=0,<=100   |
| cloud_cover_total                                        | n             | Total cloud cover                                                                   | fraction        | %     | >=0,<=100   |
| error_absolute_pressure_air_site                         | e_ppp         | Absolute error surface pressure                                                     | pressure        | Pa    | -           |
| error_absolute_temperature_air_mean_2m                   | e_ttt         | Absolute error temperature 2m above surface                                         | temperature     | K     | -           |
| error_absolute_temperature_dew_point_mean_2m             | e_td          | Absolute error dew point 2m above surface                                           | temperature     | K     | -           |
| error_absolute_wind_direction                            | e_dd          | Absolute error wind direction                                                       | angle           | °     | -           |
| error_absolute_wind_speed                                | e_ff          | Absolute error wind speed 10m above surface                                         | speed           | m/s   | -           |
| evapotranspiration_potential_last_24h                    | pevap         | Potential evapotranspiration within the last 24 hours                               | precipitation   | kg/m² | >=0         |
| precipitation_duration                                   | drr1          | Duration of precipitation within the last hour                                      | time            | s     | >=0         |
| precipitation_height_last_1h                             | rr1           | Total precipitation during the last hour                                            | precipitation   | kg/m² | >=0         |
| precipitation_height_last_3h                             | rr3           | Total precipitation during the last 3 hours                                         | precipitation   | kg/m² | >=0         |
| precipitation_height_last_6h                             | rr6           | Total precipitation during the last 6 hours                                         | precipitation   | kg/m² | >=0         |
| precipitation_height_last_12h                            | rrh           | Total precipitation during the last 12 hours                                        | precipitation   | kg/m² | >=0         |
| precipitation_height_last_24h                            | rrd           | Total precipitation during the last 24 hours                                        | precipitation   | kg/m² | >=0         |
| precipitation_height_liquid_significant_weather_last_1h  | rrl1c         | Total liquid precipitation during the last hour consistent with significant weather | precipitation   | kg/m² | >=0         |
| precipitation_height_significant_weather_last_1h         | rr1c          | Total precipitation during the last hour consistent with significant weather        | precipitation   | kg/m² | >=0         |
| precipitation_height_significant_weather_last_3h         | rr3c          | Total precipitation during the last 3 hours consistent with significant weather     | precipitation   | kg/m² | >=0         |
| precipitation_height_significant_weather_last_6h         | rr6c          | Total precipitation during the last 6 hours consistent with significant weather     | precipitation   | kg/m² | >=0         |
| precipitation_height_significant_weather_last_12h        | rrhc          | Total precipitation during the last 12 hours consistent with significant weather    | precipitation   | kg/m² | >=0         |
| precipitation_height_significant_weather_last_24h        | rrdc          | Total precipitation during the last 24 hours consistent with significant weather    | precipitation   | kg/m² | >=0         |
| pressure_air_site_reduced                                | pppp          | Surface pressure, reduced                                                           | pressure        | Pa    | >=0         |
| probability_drizzle_last_1h                              | wwz           | Probability: Occurrence of drizzle within the last hour                             | fraction        | %     | >=0,<=100   |
| probability_drizzle_last_6h                              | wwz6          | Probability: Occurrence of drizzle within the last 6 hours                          | fraction        | %     | >=0,<=100   |
| probability_drizzle_last_12h                             | wwzh          | Probability: Occurrence of drizzle within the last 12 hours                         | fraction        | %     | >=0,<=100   |
| probability_fog_last_1h                                  | wwm           | Probability for fog within the last hour                                            | fraction        | %     | >=0,<=100   |
| probability_fog_last_6h                                  | wwm6          | Probability for fog within the last 6 hours                                         | fraction        | %     | >=0,<=100   |
| probability_fog_last_12h                                 | wwmh          | Probability for fog within the last 12 hours                                        | fraction        | %     | >=0,<=100   |
| probability_fog_last_24h                                 | wwmd          | Probability for fog within the last 24 hours                                        | fraction        | %     | >=0,<=100   |
| probability_precipitation_convective_last_1h             | wwc           | Probability: Occurrence of convective precipitation within the last hour            | fraction        | %     | >=0,<=100   |
| probability_precipitation_convective_last_6h             | wwc6          | Probability: Occurrence of convective precipitation within the last 6 hours         | fraction        | %     | >=0,<=100   |
| probability_precipitation_convective_last_12h            | wwch          | Probability: Occurrence of convective precipitation within the last 12 hours        | fraction        | %     | >=0,<=100   |
| probability_precipitation_freezing_last_1h               | wwf           | Probability: Occurrence of freezing rain within the last hour                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_freezing_last_6h               | wwf6          | Probability: Occurrence of freezing rain within the last 6 hours                    | fraction        | %     | >=0,<=100   |
| probability_precipitation_freezing_last_12h              | wwfh          | Probability: Occurrence of freezing rain within the last 12 hours                   | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_0mm_last_6h        | r600          | Probability of precipitation > 0.0mm during the last 6 hours                        | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_0mm_last_12h       | rh00          | Probability of precipitation > 0.0mm during the last 12 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_0mm_last_24h       | rd00          | Probability of precipitation > 0.0mm during the last 24 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_1mm_last_1h        | r101          | Probability of precipitation > 0.1 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_2mm_last_1h        | r102          | Probability of precipitation > 0.2 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_2mm_last_6h        | r602          | Probability of precipitation > 0.2mm during the last 6 hours                        | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_2mm_last_12h       | rh02          | Probability of precipitation > 0.2mm during the last 12 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_2mm_last_24h       | rd02          | Probability of precipitation > 0.2mm during the last 24 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_3mm_last_1h        | r103          | Probability of precipitation > 0.3 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_5mm_last_1h        | r105          | Probability of precipitation > 0.5 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_0_7mm_last_1h        | r107          | Probability of precipitation > 0.7 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_1mm_last_1h          | r110          | Probability of precipitation > 1.0 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_1mm_last_6h          | r610          | Probability of precipitation > 1.0mm during the last 6 hours                        | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_1mm_last_12h         | rh10          | Probability of precipitation > 1.0mm during the last 12 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_1mm_last_24h         | rd10          | Probability of precipitation > 1.0mm during the last 24 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_2mm_last_1h          | r120          | Probability of precipitation > 2.0mm during the last hour                           | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_3mm_last_1h          | r130          | Probability of precipitation > 3.0 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_5mm_last_1h          | r150          | Probability of precipitation > 5.0 mm during the last hour                          | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_5mm_last_6h          | r650          | Probability of precipitation > 5.0mm during the last 6 hours                        | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_5mm_last_12h         | rh50          | Probability of precipitation > 5.0mm during the last 12 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_5mm_last_24h         | rd50          | Probability of precipitation > 5.0mm during the last 24 hours                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_10mm_last_1h         | rr1o1         | Probability of precipitation > 10.0 mm during the last hour                         | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_15mm_last_1h         | rr1w1         | Probability of precipitation > 15.0 mm during the last hour                         | fraction        | %     | >=0,<=100   |
| probability_precipitation_height_gt_25mm_last_1h         | rr1u1         | Probability of precipitation > 25.0 mm during the last hour                         | fraction        | %     | >=0,<=100   |
| probability_precipitation_last_1h                        | wwp           | Probability: Occurrence of precipitation within the last hour                       | fraction        | %     | >=0,<=100   |
| probability_precipitation_last_6h                        | wwp6          | Probability: Occurrence of precipitation within the last 6 hours                    | fraction        | %     | >=0,<=100   |
| probability_precipitation_last_12h                       | wwph          | Probability: Occurrence of precipitation within the last 12 hours                   | fraction        | %     | >=0,<=100   |
| probability_precipitation_liquid_last_1h                 | wwl           | Probability: Occurrence of liquid precipitation within the last hour                | fraction        | %     | >=0,<=100   |
| probability_precipitation_liquid_last_6h                 | wwl6          | Probability: Occurrence of liquid precipitation within the last 6 hours             | fraction        | %     | >=0,<=100   |
| probability_precipitation_liquid_last_12h                | wwlh          | Probability: Occurrence of liquid precipitation within the last 12 hours            | fraction        | %     | >=0,<=100   |
| probability_precipitation_solid_last_1h                  | wws           | Probability: Occurrence of solid precipitation within the last hour                 | fraction        | %     | >=0,<=100   |
| probability_precipitation_solid_last_6h                  | wws6          | Probability: Occurrence of solid precipitation within the last 6 hours              | fraction        | %     | >=0,<=100   |
| probability_precipitation_solid_last_12h                 | wwsh          | Probability: Occurrence of solid precipitation within the last 12 hours             | fraction        | %     | >=0,<=100   |
| probability_precipitation_stratiform_last_1h             | wwd           | Probability: Occurrence of stratiform precipitation within the last hour            | fraction        | %     | >=0,<=100   |
| probability_precipitation_stratiform_last_6h             | wwd6          | Probability: Occurrence of stratiform precipitation within the last 6 hours         | fraction        | %     | >=0,<=100   |
| probability_precipitation_stratiform_last_12h            | wwdh          | Probability: Occurrence of stratiform precipitation within the last 12 hours        | fraction        | %     | >=0,<=100   |
| probability_radiation_global_last_1h                     | rrad1         | Global irradiance within the last hour                                              | fraction        | %     | >=0,<=100   |
| probability_sunshine_duration_relative_gt_0pct_last_24h  | psd00         | Probability: relative sunshine duration > 0 % within 24 hours                       | fraction        | %     | >=0,<=100   |
| probability_sunshine_duration_relative_gt_30pct_last_24h | psd30         | Probability: relative sunshine duration > 30 % within 24 hours                      | fraction        | %     | >=0,<=100   |
| probability_sunshine_duration_relative_gt_60pct_last_24h | psd60         | Probability: relative sunshine duration > 60 % within 24 hours                      | fraction        | %     | >=0,<=100   |
| probability_thunder_last_1h                              | wwt           | Probability: Occurrence of thunderstorms within the last hour                       | fraction        | %     | >=0,<=100   |
| probability_thunder_last_6h                              | wwt6          | Probability: Occurrence of thunderstorms within the last 6 hours                    | fraction        | %     | >=0,<=100   |
| probability_thunder_last_12h                             | wwth          | Probability: Occurrence of thunderstorms within the last 12 hours                   | fraction        | %     | >=0,<=100   |
| probability_thunder_last_24h                             | wwtd          | Probability: Occurrence of thunderstorms within the last 24 hours                   | fraction        | %     | >=0,<=100   |
| probability_visibility_below_1000m                       | vv10          | Probability: Visibility below 1000m                                                 | fraction        | %     | >=0,<=100   |
| probability_wind_gust_ge_25kn_last_6h                    | fx625         | Probability of wind gusts >= 25kn within the last 6 hours                           | fraction        | %     | >=0,<=100   |
| probability_wind_gust_ge_25kn_last_12h                   | fxh25         | Probability of wind gusts >= 25kn within the last 12 hours                          | fraction        | %     | >=0,<=100   |
| probability_wind_gust_ge_40kn_last_6h                    | fx640         | Probability of wind gusts >= 40kn within the last 6 hours                           | fraction        | %     | >=0,<=100   |
| probability_wind_gust_ge_40kn_last_12h                   | fxh40         | Probability of wind gusts >= 40kn within the last 12 hours                          | fraction        | %     | >=0,<=100   |
| probability_wind_gust_ge_55kn_last_6h                    | fx655         | Probability of wind gusts >= 55kn within the last 6 hours                           | fraction        | %     | >=0,<=100   |
| probability_wind_gust_ge_55kn_last_12h                   | fxh55         | Probability of wind gusts >= 55kn within the last 12 hours                          | fraction        | %     | >=0,<=100   |
| radiation_global                                         | rad1h         | Global Irradiance                                                                   | energy_per_area | kJ/m² | >=0         |
| radiation_global_last_3h                                 | rads3         | Short wave radiation balance during the last 3 hours                                | energy_per_area | kJ/m² | >=0         |
| radiation_sky_long_wave_last_3h                          | radl3         | Long wave radiation balance during the last 3 hours                                 | energy_per_area | kJ/m² | >=0         |
| sunshine_duration                                        | sund1         | Sunshine duration during the last Hour                                              | time            | s     | >=0         |
| sunshine_duration_last_3h                                | sund3         | Sunshine duration during the last 3 hours                                           | time            | s     | >=0         |
| sunshine_duration_relative_last_24h                      | rsund         | Relative sunshine duration within the last 24 hours                                 | fraction        | %     | >=0,<=100   |
| sunshine_duration_yesterday                              | sund          | Yesterdays total sunshine duration                                                  | time            | s     | >=0         |
| temperature_air_max_2m                                   | tx            | Maximum temperature - within the last 12 hours                                      | temperature     | K     | -           |
| temperature_air_mean_0_05m                               | t5cm          | Temperature 5cm above surface                                                       | temperature     | K     | -           |
| temperature_air_mean_2m                                  | ttt           | Temperature 2m above surface                                                        | temperature     | K     | -           |
| temperature_air_mean_2m_last_24h                         | tm            | Mean temperature during the last 24 hours                                           | temperature     | K     | -           |
| temperature_air_min_0_05m_last_12h                       | tg            | Minimum surface temperature at 5cm within the last 12 hours                         | temperature     | K     | -           |
| temperature_air_min_2m                                   | tn            | Minimum temperature - within the last 12 hours                                      | temperature     | K     | -           |
| temperature_dew_point_mean_2m                            | td            | Dewpoint 2m above surface                                                           | temperature     | K     | -           |
| visibility_range                                         | vv            | Visibility                                                                          | length_medium   | m     | >=0         |
| water_equivalent_snow_depth_new_last_1h                  | rrs1c         | Snow-Rain-Equivalent during the last hour                                           | precipitation   | kg/m² | >=0         |
| water_equivalent_snow_depth_new_last_3h                  | rrs3c         | Snow-Rain-Equivalent during the last 3 hours                                        | precipitation   | kg/m² | >=0         |
| weather_last_6h                                          | w1w2          | Past weather during the last 6 hours                                                | dimensionless   | -     | -           |
| weather_significant                                      | ww            | Significant Weather                                                                 | dimensionless   | -     | -           |
| weather_significant_last_3h                              | ww3           | Significant Weather                                                                 | dimensionless   | -     | -           |
| weather_significant_optional_last_1h                     | wpc11         | Optional significant weather (highest priority) during the last hour                | dimensionless   | -     | >=-95,<=0   |
| weather_significant_optional_last_3h                     | wpc31         | Optional significant weather (highest priority) during the last 3 hours             | dimensionless   | -     | >=-95,<=0   |
| weather_significant_optional_last_6h                     | wpc61         | Optional significant weather (highest priority) during the last 6 hours             | dimensionless   | -     | >=-95,<=0   |
| weather_significant_optional_last_12h                    | wpch1         | Optional significant weather (highest priority) during the last 12 hours            | dimensionless   | -     | >=-95,<=0   |
| weather_significant_optional_last_24h                    | wpcd1         | Optional significant weather (highest priority) during the last 24 hours            | dimensionless   | -     | >=-95,<=0   |
| wind_direction                                           | dd            | Wind direction                                                                      | angle           | °     | >=0,<=360   |
| wind_gust_max_last_1h                                    | fx1           | Maximum wind gust within the last hour                                              | speed           | m/s   | >=0         |
| wind_gust_max_last_3h                                    | fx3           | Maximum wind gust within the last 3 hours                                           | speed           | m/s   | >=0         |
| wind_gust_max_last_12h                                   | fxh           | Maximum wind gust within the last 12 hours                                          | speed           | m/s   | >=0         |
| wind_speed                                               | ff            | Wind speed                                                                          | speed           | m/s   | >=0         |