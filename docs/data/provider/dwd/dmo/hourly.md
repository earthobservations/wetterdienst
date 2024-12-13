# hourly

## metadata

| property      | value                                                                                     |
|---------------|-------------------------------------------------------------------------------------------|
| original name | missing                                                                                   |
| url           | [here](https://www.dwd.de/DE/leistungen/met_verfahren_ptp_dmo/met_verfahren_ptp_dmo.html) |

## Datasets

### Small

#### Metadata

| property | value                                                                                                |
|----------|------------------------------------------------------------------------------------------------------|
| name | small                                                                                                |
| original name | icon-eu                                                                                              |
| description | Local forecast of 40 parameters for worldwide stations, 24 times a day with a lead-time of 240 hours |
| description file | [here](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)                                 |
| url | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon-eu/)                                 |

#### Parameters

| name | original name | description | origin unit | SI unit | constraints |
|------|---------------|-------------|-------------|---------|-------------|
| cloud_base_convective | h_bsc | Cloud base of convective clouds | m | m | :math:`\geq{0}` |
| cloud_cover_above_7km | nh | High cloud cover (>7 km) | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_below_500ft | n05 | Cloud cover below 500 ft. | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_below_1000ft | n1 | Low cloud cover (lower than 2 km) | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_below_7km | nlm | Cloud cover low and mid level clouds below 7000 m | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_between_2km_to_7km | nm | Midlevel cloud cover (2-7 km) | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_effective | neff | Effective cloud cover | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_total | n | Total cloud cover | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| precipitation_height_significant_weather_last_1h | rr1c | Total precipitation during the last hour consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_significant_weather_last_3h | rr3c | Total precipitation during the last 3 hours consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| pressure_air_site_reduced | pppp | Surface pressure, reduced | :math:`Pa` | :math:`Pa` | :math:`\geq{0}` |
| probability_fog_last_1h | wwm | Probability for fog within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_fog_last_6h | wwm6 | Probability for fog within the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_fog_last_12h | wwmh | Probability for fog within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_0mm_last_12h | rh00 | Probability of precipitation > 0.0mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_2mm_last_6h | r602 | Probability of precipitation > 0.2mm during the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_2mm_last_12h | rh02 | Probability of precipitation > 0.2mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_2mm_last_24h | rd02 | Probability of precipitation > 0.2mm during the last 24 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_1mm_last_12h | rh10 | Probability of precipitation > 1.0mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_5mm_last_6h | r650 | Probability of precipitation > 5.0mm during the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_5mm_last_12h | rh50 | Probability of precipitation > 5.0mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_5mm_last_24h | rd50 | Probability of precipitation > 5.0mm during the last 24 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_wind_gust_ge_25kn_last_12h | fxh25 | Probability of wind gusts >= 25kn within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_wind_gust_ge_40kn_last_12h | fxh40 | Probability of wind gusts >= 40kn within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_wind_gust_ge_55kn_last_12h | fxh55 | Probability of wind gusts >= 55kn within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| radiation_global | rad1h | Global Irradiance | :math:`kJ / m^2` | :math:`J / m^2` | :math:`\geq{0}` |
| sunshine_duration | sund1 | Sunshine duration during the last Hour | :math:`s` | :math:`s` | :math:`\geq{0}` |
| temperature_air_max_2m | tx | Maximum temperature - within the last 12 hours | :math:`K` | :math:`K` | none |
| temperature_air_mean_0_05m | t5cm | Temperature 5cm above surface | :math:`K` | :math:`K` | none |
| temperature_air_mean_2m | ttt | Temperature 2m above surface | :math:`K` | :math:`K` | none |
| temperature_air_min_2m | tn | Minimum temperature - within the last 12 hours | :math:`K` | :math:`K` | none |
| temperature_dew_point_mean_2m | td | Dewpoint 2m above surface | :math:`K` | :math:`K` | none |
| visibility_range | vv | Visibility | :math:`m` | :math:`m` | :math:`\geq{0}` |
| water_equivalent_snow_depth_new_last_1h | rrs1c | Snow-Rain-Equivalent during the last hour | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| water_equivalent_snow_depth_new_last_3h | rrs3c | Snow-Rain-Equivalent during the last 3 hours | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| weather_last_6h | w1w2 | Past weather during the last 6 hours | :math:`-` | :math:`-` | none |
| weather_significant | ww | Significant Weather | :math:`-` | :math:`-` | none |
| wind_direction | dd | Wind direction | :math:`°` | :math:`°` | :math:`\geq{0}, \leq{360}` |
| wind_gust_max_last_1h | fx1 | Maximum wind gust within the last hour | :math:`m / s` | :math:`m / s` | :math:`\geq{0}` |
| wind_gust_max_last_3h | fx3 | Maximum wind gust within the last 3 hours | :math:`m / s` | :math:`m / s` | :math:`\geq{0}` |
| wind_gust_max_last_12h | fxh | Maximum wind gust within the last 12 hours | :math:`m / s` | :math:`m / s` | :math:`\geq{0}` |
| wind_speed | ff | Wind speed | :math:`m / s` | :math:`m / s` | :math:`\geq{0}` |

### Large

#### Metadata

| property | value                                                                                                |
|----------|------------------------------------------------------------------------------------------------------|
| name | large                                                                                                |
| original name | icon                                                                                                 |
| description | Local forecast of 115 parameters for worldwide stations, 4 times a day with a lead-time of 240 hours |
| description file | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon/)                                    |
| url | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon/)                                    |

#### Parameters

| name | original name | description | origin unit | SI unit | constraints |
| ------ | -------------- | ----------- | ----------- | ------- | ----------- |
| cloud_cover_above_7km | nh | High cloud cover (>7 km) | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_below_500ft | n05 | Cloud cover below 500 ft. | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_below_1000ft | n1 | Low cloud cover (lower than 2 km) | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_between_2km_to_7km | nm | Midlevel cloud cover (2-7 km) | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_effective | neff | Effective cloud cover | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| cloud_cover_total | n | Total cloud cover | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| error_absolute_pressure_air_site | e_ppp | Absolute error surface pressure | :math:`Pa` | :math:`Pa` | none |
| error_absolute_temperature_air_mean_2m | e_ttt | Absolute error temperature 2m above surface | :math:`K` | :math:`K` | none |
| error_absolute_temperature_dew_point_mean_2m | e_td | Absolute error dew point 2m above surface | :math:`K` | :math:`K` | none |
| error_absolute_wind_direction | e_dd | Absolute error wind direction | :math:`°` | :math:`°` | none |
| error_absolute_wind_speed | e_ff | Absolute error wind speed 10m above surface | :math:`m / s` | :math:`m / s` | none |
| evapotranspiration_potential_last_24h | pevap | Potential evapotranspiration within the last 24 hours | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_duration | drr1 | Duration of precipitation within the last hour | :math:`s` | :math:`s` | :math:`\geq{0}` |
| precipitation_height_last_1h | rr1 | Total precipitation during the last hour | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_last_3h | rr3 | Total precipitation during the last 3 hours | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_last_6h | rr6 | Total precipitation during the last 6 hours | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_last_12h | rrh | Total precipitation during the last 12 hours | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_last_24h | rrd | Total precipitation during the last 24 hours | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_liquid_significant_weather_last_1h | rrl1c | Total liquid precipitation during the last hour consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_significant_weather_last_1h | rr1c | Total precipitation during the last hour consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_significant_weather_last_3h | rr3c | Total precipitation during the last 3 hours consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_significant_weather_last_6h | rr6c | Total precipitation during the last 6 hours consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_significant_weather_last_12h | rrhc | Total precipitation during the last 12 hours consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| precipitation_height_significant_weather_last_24h | rrdc | Total precipitation during the last 24 hours consistent with significant weather | :math:`kg / m^2` | :math:`kg / m^2` | :math:`\geq{0}` |
| pressure_air_site_reduced | pppp | Surface pressure, reduced | :math:`Pa` | :math:`Pa` | :math:`\geq{0}` |
| probability_drizzle_last_1h | wwz | Probability: Occurrence of drizzle within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_drizzle_last_6h | wwz6 | Probability: Occurrence of drizzle within the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_drizzle_last_12h | wwzh | Probability: Occurrence of drizzle within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_fog_last_1h | wwm | Probability for fog within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_fog_last_6h | wwm6 | Probability for fog within the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_fog_last_12h | wwmh | Probability for fog within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_fog_last_24h | wwmd | Probability for fog within the last 24 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_convective_last_1h | wwc | Probability: Occurrence of convective precipitation within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_convective_last_6h | wwc6 | Probability: Occurrence of convective precipitation within the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_convective_last_12h | wwch | Probability: Occurrence of convective precipitation within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_freezing_last_1h | wwf | Probability: Occurrence of freezing rain within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_freezing_last_6h | wwf6 | Probability: Occurrence of freezing rain within the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_freezing_last_12h | wwfh | Probability: Occurrence of freezing rain within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_0mm_last_6h | r600 | Probability of precipitation > 0.0mm during the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_0mm_last_12h | rh00 | Probability of precipitation > 0.0mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_0mm_last_24h | rd00 | Probability of precipitation > 0.0mm during the last 24 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_1mm_last_1h | r101 | Probability of precipitation > 0.1 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_2mm_last_1h | r102 | Probability of precipitation > 0.2 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_2mm_last_6h | r602 | Probability of precipitation > 0.2mm during the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_2mm_last_12h | rh02 | Probability of precipitation > 0.2mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_2mm_last_24h | rd02 | Probability of precipitation > 0.2mm during the last 24 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_3mm_last_1h | r103 | Probability of precipitation > 0.3 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_5mm_last_1h | r105 | Probability of precipitation > 0.5 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_0_7mm_last_1h | r107 | Probability of precipitation > 0.7 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_1mm_last_1h | r110 | Probability of precipitation > 1.0 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_1mm_last_6h | r610 | Probability of precipitation > 1.0mm during the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_1mm_last_12h | rh10 | Probability of precipitation > 1.0mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_1mm_last_24h | rd10 | Probability of precipitation > 1.0mm during the last 24 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_2mm_last_1h | r120 | Probability of precipitation > 2.0mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_3mm_last_1h | r130 | Probability of precipitation > 3.0 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_5mm_last_1h | r150 | Probability of precipitation > 5.0 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_5mm_last_6h | r650 | Probability of precipitation > 5.0mm during the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_5mm_last_12h | rh50 | Probability of precipitation > 5.0mm during the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_5mm_last_24h | rd50 | Probability of precipitation > 5.0mm during the last 24 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_10mm_last_1h | rr1o1 | Probability of precipitation > 10.0 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_15mm_last_1h | rr1w1 | Probability of precipitation > 15.0 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_height_gt_25mm_last_1h | rr1u1 | Probability of precipitation > 25.0 mm during the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_last_1h | wwp | Probability: Occurrence of precipitation within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_last_6h | wwp6 | Probability: Occurrence of precipitation within the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_last_12h | wwph | Probability: Occurrence of precipitation within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_liquid_last_1h | wwl | Probability: Occurrence of liquid precipitation within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_liquid_last_6h | wwl6 | Probability: Occurrence of liquid precipitation within the last 6 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_liquid_last_12h | wwlh | Probability: Occurrence of liquid precipitation within the last 12 hours | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_solid_last_1h | wws | Probability: Occurrence of solid precipitation within the last hour | :math:`\%` | :math:`\%` | :math:`\geq{0}, \leq{100}` |
| probability_precipitation_solid_last_6h | wws6 | 

probability_precipitation_solid_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wws
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of solid precipitation within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_solid_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wws6
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of solid precipitation within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_solid_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwsh
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of solid precipitation within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_stratiform_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwd
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of stratiform precipitation within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_stratiform_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwd6
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of stratiform precipitation within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_stratiform_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwdh
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of stratiform precipitation within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_radiation_global_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrad1
   * - description file
     - `dmo dataset description`_
   * - description
     - Global irradiance within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_sunshine_duration_relative_gt_0pct_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - psd00
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: relative sunshine duration > 0 % within 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_sunshine_duration_relative_gt_30pct_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - psd30
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: relative sunshine duration > 30 % within 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_sunshine_duration_relative_gt_60pct_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - psd60
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: relative sunshine duration > 60 % within 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_thunder_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwt
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of thunderstorms within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_thunder_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwt6
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of thunderstorms within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_thunder_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwth
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of thunderstorms within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_thunder_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwtd
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Occurrence of thunderstorms within the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_visibility_below_1000m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - vv10
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability: Visibility below 1000m
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_wind_gust_ge_25kn_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx625
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability of wind gusts >= 25kn within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_wind_gust_ge_25kn_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fxh25
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability of wind gusts >= 25kn within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_wind_gust_ge_40kn_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx640
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability of wind gusts >= 40kn within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_wind_gust_ge_40kn_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fxh40
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability of wind gusts >= 40kn within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_wind_gust_ge_55kn_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx655
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability of wind gusts >= 55kn within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_wind_gust_ge_55kn_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fxh55
   * - description file
     - `dmo dataset description`_
   * - description
     - Probability of wind gusts >= 55kn within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

radiation_global
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rad1h
   * - description file
     - `dmo dataset description`_
   * - description
     - Global Irradiance
   * - origin unit
     - :math:`kJ / m^2`
   * - SI unit
     - :math:`J / m^2`
   * - constraints
     - :math:`\geq{0}`

radiation_global_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rads3
   * - description file
     - `dmo dataset description`_
   * - description
     - Short wave radiation balance during the last 3 hours
   * - origin unit
     - :math:`kJ / m^2`
   * - SI unit
     - :math:`J / m^2`
   * - constraints
     - :math:`\geq{0}`

radiation_sky_long_wave_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - radl3
   * - description file
     - `dmo dataset description`_
   * - description
     - Long wave radiation balance during the last 3 hours
   * - origin unit
     - :math:`kJ / m^2`
   * - SI unit
     - :math:`J / m^2`
   * - constraints
     - :math:`\geq{0}`

sunshine_duration
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sund1
   * - description file
     - `dmo dataset description`_
   * - description
     - Sunshine duration during the last Hour
   * - origin unit
     - :math:`s`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

sunshine_duration_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sund3
   * - description file
     - `dmo dataset description`_
   * - description
     - Sunshine duration during the last 3 hours
   * - origin unit
     - :math:`s`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

sunshine_duration_relative_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rsund
   * - description file
     - `dmo dataset description`_
   * - description
     - Relative sunshine duration within the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

sunshine_duration_yesterday
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sund
   * - description file
     - `dmo dataset description`_
   * - description
     - Yesterdays total sunshine duration
   * - origin unit
     - :math:`s`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

temperature_air_max_2m
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tx
   * - description file
     - `dmo dataset description`_
   * - description
     - Maximum temperature - within the last 12 hours
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_mean_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - t5cm
   * - description file
     - `dmo dataset description`_
   * - description
     - Temperature 5cm above surface
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ttt
   * - description file
     - `dmo dataset description`_
   * - description
     - Temperature 2m above surface
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_mean_2m_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tm
   * - description file
     - `dmo dataset description`_
   * - description
     - Mean temperature during the last 24 hours
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none


temperature_air_min_0_05m_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tg
   * - description file
     - `dmo dataset description`_
   * - description
     - Minimum surface temperature at 5cm within the last 12 hours
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_min_2m
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tn
   * - description file
     - `dmo dataset description`_
   * - description
     - Minimum temperature - within the last 12 hours
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_dew_point_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - td
   * - description file
     - `dmo dataset description`_
   * - description
     - Dewpoint 2m above surface
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

visibility_range
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - vv
   * - description file
     - `dmo dataset description`_
   * - description
     - Visibility
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

water_equivalent_snow_depth_new_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrs1c
   * - description file
     - `dmo dataset description`_
   * - description
     - Snow-Rain-Equivalent during the last hour
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

water_equivalent_snow_depth_new_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrs3c
   * - description file
     - `dmo dataset description`_
   * - description
     - Snow-Rain-Equivalent during the last 3 hours
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

weather_last_6h
^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - w1w2
   * - description file
     - `dmo dataset description`_
   * - description
     - Past weather during the last 6 hours
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_significant
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ww
   * - description file
     - `dmo dataset description`_
   * - description
     - Significant Weather
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_significant_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ww3
   * - description file
     - `dmo dataset description`_
   * - description
     - Significant Weather
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_significant_optional_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wpc11
   * - description file
     - `dmo dataset description`_
   * - description
     - Optional significant weather (highest priority) during the last hour
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\leq{0}, \geq{-95}`

weather_significant_optional_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wpc31
   * - description file
     - `dmo dataset description`_
   * - description
     - Optional significant weather (highest priority) during the last 3 hours
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\leq{0}, \geq{-95}`

weather_significant_optional_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wpc61
   * - description file
     - `dmo dataset description`_
   * - description
     - Optional significant weather (highest priority) during the last 6 hours
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\leq{0}, \geq{-95}`

weather_significant_optional_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wpch1
   * - description file
     - `dmo dataset description`_
   * - description
     - Optional significant weather (highest priority) during the last 12 hours
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\leq{0}, \geq{-95}`

weather_significant_optional_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wpcd1
   * - description file
     - `dmo dataset description`_
   * - description
     - Optional significant weather (highest priority) during the last 24 hours
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\leq{0}, \geq{-95}`

wind_direction
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dd
   * - description file
     - `dmo dataset description`_
   * - description
     - Wind direction
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_gust_max_last_1h
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx1
   * - description file
     - `dmo dataset description`_
   * - description
     - Maximum wind gust within the last hour
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_last_3h
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx3
   * - description file
     - `dmo dataset description`_
   * - description
     - Maximum wind gust within the last 3 hours
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_last_12h
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fxh
   * - description file
     - `dmo dataset description`_
   * - description
     - Maximum wind gust within the last 12 hours
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_speed
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ff
   * - description file
     - `dmo dataset description`_
   * - description
     - Wind speed
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`
