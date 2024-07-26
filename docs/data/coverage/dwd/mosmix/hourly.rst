Hourly
######

Metadata
********

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - missing
   * - url
     - `here <https://opendata.dwd.de/weather/local_forecasts/mos/>`_

Datasets
********

Small
=====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mosmix_s
   * - url
     - `here <https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_S/>`_
   * - description file
     - `mosmix dataset description`_ (includes all parameters of mosmix_s and mosmix_l)
   * - description
     - Local forecast of 40 parameters for worldwide stations, 24 times a day with a lead-time of 240 hours

.. _mosmix dataset description: https://opendata.dwd.de/weather/lib/MetElementDefinition.xml

Parameters
----------

cloud_base_convective
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - h_bsc
   * - description file
     - `mosmix dataset description`_
   * - description
     - Cloud base of convective clouds
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

cloud_cover_above_7km
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nh
   * - description file
     - `mosmix dataset description`_
   * - description
     - High cloud cover (>7 km)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_below_500ft
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - n05
   * - description file
     - `mosmix dataset description`_
   * - description
     - Cloud cover below 500 ft.
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_below_1000ft
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nl
   * - description file
     - `mosmix dataset description`_
   * - description
     - Low cloud cover (lower than 2 km)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_below_7km
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nlm
   * - description file
     - `mosmix dataset description`_
   * - description
     - Cloud cover low and mid level clouds below 7000 m
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_between_2km_to_7km
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nm
   * - description file
     - `mosmix dataset description`_
   * - description
     - Midlevel cloud cover (2-7 km)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_effective
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - neff
   * - description file
     - `mosmix dataset description`_
   * - description
     - Effective cloud cover
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_total
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - n
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total cloud cover
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

precipitation_height_significant_weather_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr1c
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last hour consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_significant_weather_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr3c
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 3 hours consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

pressure_air_site_reduced
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pppp
   * - description file
     - `mosmix dataset description`_
   * - description
     - Surface pressure, reduced
   * - origin unit
     - :math:`Pa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

probability_fog_last_1h
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwm
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability for fog within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_fog_last_6h
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwm6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability for fog within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_fog_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwmh
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability for fog within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_0mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh00
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.0mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_2mm_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r602
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.2mm during the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_2mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh02
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.2mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_2mm_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rd02
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.2mm during the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_1mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh10
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 1.0mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_5mm_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r650
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 5.0mm during the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_5mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh50
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 5.0mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_5mm_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rd50
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 5.0mm during the last 24 hours
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
     - `mosmix dataset description`_
   * - description
     - Probability of wind gusts >= 25kn within the last 12 hours
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
     - `mosmix dataset description`_
   * - description
     - Probability of wind gusts >= 40kn within the last 12 hours
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
   * - description
     - Global Irradiance
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
     - `mosmix dataset description`_
   * - description
     - Sunshine duration during the last Hour
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
   * - description
     - Temperature 2m above surface
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
   * - description
     - Significant Weather
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

wind_direction
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dd
   * - description file
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
   * - description
     - Wind speed
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

Large
=====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mosmix_l
   * - url
     - `here <https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/>`_
   * - description file
     - `mosmix dataset description`_ (includes all parameters of mosmix_s and mosmix_l)
   * - description
     - Local forecast of 115 parameters for worldwide stations, 4 times a day with a lead-time of 240 hours

.. _mosmix dataset description: https://opendata.dwd.de/weather/lib/MetElementDefinition.xml

Parameters
----------

cloud_cover_above_7km
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nh
   * - description file
     - `mosmix dataset description`_
   * - description
     - High cloud cover (>7 km)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_below_500ft
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - n05
   * - description file
     - `mosmix dataset description`_
   * - description
     - Cloud cover below 500 ft.
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_below_1000ft
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nl
   * - description file
     - `mosmix dataset description`_
   * - description
     - Low cloud cover (lower than 2 km)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_between_2km_to_7km
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nm
   * - description file
     - `mosmix dataset description`_
   * - description
     - Midlevel cloud cover (2-7 km)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_effective
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - neff
   * - description file
     - `mosmix dataset description`_
   * - description
     - Effective cloud cover
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_total
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - n
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total cloud cover
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

error_absolute_pressure_air_site
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - e_ppp
   * - description file
     - `mosmix dataset description`_
   * - description
     - Absolute error surface pressure
   * - origin unit
     - :math:`Pa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - none

error_absolute_temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - e_ttt
   * - description file
     - `mosmix dataset description`_
   * - description
     - Absolute error temperature 2m above surface
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

error_absolute_temperature_dew_point_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - e_td
   * - description file
     - `mosmix dataset description`_
   * - description
     - Absolute error dew point 2m above surface
   * - origin unit
     - :math:`K`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

error_absolute_wind_direction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - e_dd
   * - description file
     - `mosmix dataset description`_
   * - description
     - Absolute error wind direction
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - none

error_absolute_wind_speed
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - e_ff
   * - description file
     - `mosmix dataset description`_
   * - description
     - Absolute error wind speed 10m above surface
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - none

evapotranspiration_potential_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pevap
   * - description file
     - `mosmix dataset description`_
   * - description
     - Potential evapotranspiration within the last 24 hours
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_duration
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - drr1
   * - description file
     - `mosmix dataset description`_
   * - description
     - Duration of precipitation within the last hour
   * - origin unit
     - :math:`s`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr1
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last hour
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr3
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 3 hours
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 6 hours
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrh
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 12 hours
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrd
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 24 hours
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_liquid_significant_weather_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrl1c
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total liquid precipitation during the last hour consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_significant_weather_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr1c
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last hour consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_significant_weather_last_3h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr3c
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 3 hours consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_significant_weather_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr6c
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 6 hours consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_significant_weather_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrhc
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 12 hours consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_significant_weather_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rrdc
   * - description file
     - `mosmix dataset description`_
   * - description
     - Total precipitation during the last 24 hours consistent with significant weather
   * - origin unit
     - :math:`kg / m^2`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

pressure_air_site_reduced
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pppp
   * - description file
     - `mosmix dataset description`_
   * - description
     - Surface pressure, reduced
   * - origin unit
     - :math:`Pa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

probability_drizzle_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwz
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of drizzle within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_drizzle_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwz6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of drizzle within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_drizzle_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwzh
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of drizzle within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_fog_last_1h
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwm
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability for fog within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_fog_last_6h
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwm6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability for fog within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_fog_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwmh
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability for fog within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_fog_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwmd
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability for fog within the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_convective_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwc
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of convective precipitation within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_convective_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwc6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of convective precipitation within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_convective_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwch
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of convective precipitation within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_freezing_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwf
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of freezing rain within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_freezing_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwf6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of freezing rain within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_freezing_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwfh
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of freezing rain within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_0mm_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r600
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.0mm during the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_0mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh00
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.0mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_0mm_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rd00
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.0mm during the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_1mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r101
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.1 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_2mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r102
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.2 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_2mm_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r602
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.2mm during the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_2mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh02
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.2mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_2mm_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rd02
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.2mm during the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_3mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r103
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.3 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_5mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r105
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.5 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_0_7mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r107
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 0.7 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_1mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r110
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 1.0 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_1mm_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r610
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 1.0 mm during the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_1mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh10
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 1.0mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_1mm_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rd10
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 1.0mm during the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_2mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r120
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 2.0mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_3mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r130
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 3.0 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_5mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r150
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 5.0 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_5mm_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r650
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 5.0mm during the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_5mm_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rh50
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 5.0mm during the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_5mm_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rd50
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 5.0mm during the last 24 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_10mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr1o1
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 10.0 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_15mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr1w1
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 15.0 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_height_gt_25mm_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr1u1
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability of precipitation > 25.0 mm during the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwp
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of precipitation within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwp6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of precipitation within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwph
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of precipitation within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_liquid_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwl
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of liquid precipitation within the last hour
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_liquid_last_6h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwl6
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of liquid precipitation within the last 6 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_liquid_last_12h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wwlh
   * - description file
     - `mosmix dataset description`_
   * - description
     - Probability: Occurrence of liquid precipitation within the last 12 hours
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

probability_precipitation_solid_last_1h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wws
   * - description file
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
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
     - `mosmix dataset description`_
   * - description
     - Wind speed
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`
