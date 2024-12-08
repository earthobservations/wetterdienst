Daily
#####

Metadata
********

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - daily
   * - url
     - `NOAA GHCN Data`_

.. _NOAA GHCN Data: https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/

Datasets
********

Data
====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - daily
   * - url
     - `NOAA GHCN Data`_
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Historical daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany

.. _NOAA GHCN dataset description: https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/doc/GHCND_documentation.pdf

Parameters
----------

cloud_cover_total_midnight_to_midnight
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - acmc
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Average cloudiness midnight to midnight from 30-second ceilometer data (percent)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_total_midnight_to_midnight_manual
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - acmh
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Average cloudiness midnight to midnight from manual observation (percent)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_total_sunrise_to_sunset
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - acsc
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Average cloudiness sunrise to sunset from 30-second ceilometer data (percent)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

cloud_cover_total_sunrise_to_sunset_manual
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - acsh
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Average cloudiness sunrise to sunset from manual observation (percent)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

count_days_multiday_evaporation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - daev
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Number of days included in the multiday evaporation total (MDEV)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_days_multiday_precipitation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dapr
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Number of days included in the multiday precipitation total (MDPR)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_days_multiday_precipitation_height_gt_0mm
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dwpr
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Number of days with non-zero precipitation included in multiday precipitation total (MDPR)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_days_multiday_snow_depth_new
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dasf
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Number of days included in the multiday snowfall total (MDSF)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_days_multiday_temperature_air_max_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - datx
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Number of days included in the multiday maximum temperature (MDTX)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_days_multiday_temperature_air_min_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - datn
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Number of days included in the multiday minimum temperature (MDTN)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_days_multiday_wind_movement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dawm
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Number of days included in the multiday wind movement (MDWM)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

distance_river_gauge_height
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - gaht
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Difference between river and gauge height (cm or inches as per user preference)
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

evaporation_height
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - evap
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Evaporation of water from evaporation pan (mm or inches as per user preference, or hundredths of inches on Daily
       Form pdf file)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

evaporation_height_multiday
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mdev
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Multiday evaporation total (mm or inches as per user preference; use with DAEV)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

frozen_ground_layer_base
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - frgb
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Base of frozen ground layer (cm or inches as per user preference)
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

frozen_ground_layer_thickness
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - frth
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Thickness of frozen ground layer (cm or inches as per user preference)
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

frozen_ground_layer_top
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - frgt
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Top of frozen ground layer (cm or inches as per user preference)
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

ice_on_water_thickness
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - thic
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Thickness of ice on water (inches or mm as per user preference)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

precipitation_height
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - prcp
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Precipitation (mm or inches as per user preference, inches to hundredths on Daily Form pdf file)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_height_multiday
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mdpr
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Multiday precipitation total (mm or inches as per user preference; use with DAPR and DWPR, if available)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

snow_depth
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - snwd
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Snow depth (mm or inches as per user preference, inches on Daily Form pdf file)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

snow_depth_new
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - snow
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Snowfall (mm or inches as per user preference, inches to tenths on Daily Form pdf file)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

snow_depth_new_multiday
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mdsf
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Multiday snowfall total (mm or inches as per user preference)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

sunshine_duration
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tsun
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Daily total sunshine (minutes)
   * - origin unit
     - :math:`min`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

sunshine_duration_relative
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - psun
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Daily percent of possible sunshine (percent)
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

temperature_air_2m
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tobs
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Temperature at the time of observation  (Fahrenheit or Celsius as per user preference)
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_max_2m
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tmax
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum  temperature  (Fahrenheit or  Celsius  as per  user  preference, Fahrenheit  to  tenths on Daily Form pdf
       file
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_max_2m_multiday
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mdtx
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Multiday maximum temperature (Fahrenheit or Celsius as per user preference ; use with DATX)
   * - origin unit
     - :math:`°C`
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
     - tmin
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - mean temperature calculated from tmean = (temperature_air_max_2m + temperature_air_min_2m) / 2
   * - origin unit
     - :math:`°C`
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
     - tmin
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum  temperature  (Fahrenheit  or  Celsius  as per  user  preference, Fahrenheit  to  tenths  on Daily Form
       pdf file
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_min_2m_multiday
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mdtn
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Multiday minimum temperature (Fahrenheit or Celsius as per user preference ; use with DATN)
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_ground_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx31
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_ground ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_ground_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx32
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_ground ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_ground_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx33
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_ground ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_ground_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx34
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_ground ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_ground_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx35
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_ground ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_ground_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx36
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_ground ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_ground_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx37
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_ground ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_ground_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn31
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_ground ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_ground_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn32
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_ground ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_ground_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn33
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_ground ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_ground_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn34
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_ground ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_ground_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn35
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_ground ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_ground_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn36
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_ground ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_ground_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn37
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_ground ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_muck_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx81
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_muck ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_muck_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx82
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_muck ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_muck_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx83
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_muck ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_muck_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx84
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_muck ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_muck_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx85
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_muck ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_muck_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx86
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_muck ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_bare_muck_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx87
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of bare_muck ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_muck_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn81
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_muck ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_muck_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn82
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_muck ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_muck_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn83
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_muck ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_muck_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn84
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_muck ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_muck_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn85
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_muck ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_muck_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn86
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_muck ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_bare_muck_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn87
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of bare_muck ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_brome_grass_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx41
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of brome_grass ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_brome_grass_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx42
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of brome_grass ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_brome_grass_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx43
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of brome_grass ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_brome_grass_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx44
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of brome_grass ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_brome_grass_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx45
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of brome_grass ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_brome_grass_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx46
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of brome_grass ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_brome_grass_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx47
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of brome_grass ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_brome_grass_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn41
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of brome_grass ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_brome_grass_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn42
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of brome_grass ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_brome_grass_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn43
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of brome_grass ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_brome_grass_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn44
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of brome_grass ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_brome_grass_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn45
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of brome_grass ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_brome_grass_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn46
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of brome_grass ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_brome_grass_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn47
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of brome_grass ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_fallow_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx21
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of fallow ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_fallow_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx22
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of fallow ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_fallow_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx23
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of fallow ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_fallow_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx24
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of fallow ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_fallow_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx25
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of fallow ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_fallow_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx26
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of fallow ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_fallow_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx27
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of fallow ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_fallow_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn21
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of fallow ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_fallow_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn22
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of fallow ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_fallow_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn23
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of fallow ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_fallow_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn24
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of fallow ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_fallow_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn25
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of fallow ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_fallow_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn26
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of fallow ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_fallow_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn27
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of fallow ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx11
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx12
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx13
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx14
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx15
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx16
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx17
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn11
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn12
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn13
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn14
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn15
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn16
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn17
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_muck_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx71
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass_muck ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_muck_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx72
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass_muck ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_muck_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx73
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass_muck ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_muck_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx74
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass_muck ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_muck_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx75
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass_muck ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_muck_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx76
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass_muck ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_grass_muck_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx77
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of grass_muck ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_muck_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn71
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass_muck ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_muck_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn72
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass_muck ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_muck_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn73
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass_muck ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_muck_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn74
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass_muck ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_muck_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn75
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass_muck ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_muck_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn76
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass_muck ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_grass_muck_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn77
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of grass_muck ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_sod_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx51
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of sod ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_sod_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx52
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of sod ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_sod_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx53
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of sod ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_sod_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx54
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of sod ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_sod_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx55
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of sod ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_sod_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx56
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of sod ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_sod_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx57
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of sod ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_sod_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn51
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of sod ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_sod_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn52
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of sod ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_sod_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn53
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of sod ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_sod_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn54
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of sod ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_sod_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn55
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of sod ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_sod_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn56
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of sod ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_sod_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn57
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of sod ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_straw_mulch_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx61
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of straw_mulch ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_straw_mulch_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx62
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of straw_mulch ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_straw_mulch_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx63
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of straw_mulch ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_straw_mulch_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx64
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of straw_mulch ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_straw_mulch_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx65
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of straw_mulch ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_straw_mulch_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx66
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of straw_mulch ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_straw_mulch_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx67
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of straw_mulch ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_straw_mulch_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn61
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of straw_mulch ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_straw_mulch_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn62
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of straw_mulch ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_straw_mulch_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn63
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of straw_mulch ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_straw_mulch_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn64
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of straw_mulch ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_straw_mulch_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn65
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of straw_mulch ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_straw_mulch_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn66
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of straw_mulch ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_straw_mulch_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn67
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of straw_mulch ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_unknown_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx01
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of unknown ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_unknown_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx02
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of unknown ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_unknown_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx03
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of unknown ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_unknown_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx04
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of unknown ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_unknown_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx05
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of unknown ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_unknown_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx06
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of unknown ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_max_unknown_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sx07
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Maximum soil temperature of unknown ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_unknown_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn01
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of unknown ground at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_unknown_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn02
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of unknown ground at 10cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_unknown_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn03
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of unknown ground at 20cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_unknown_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn04
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of unknown ground at 50cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_unknown_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn05
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of unknown ground at 100cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_unknown_1_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn06
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of unknown ground at 150cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_min_unknown_1_8m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sn07
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Minimum soil temperature of unknown ground at 180cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_water_evaporation_pan_max
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mxpn
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Daily maximum temperature of water in an evaporation pan  (Fahrenheit or Celsius as per user preference)
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_water_evaporation_pan_min
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mnpn
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Daily minimum temperature of water in an evaporation pan (Fahrenheit or Celsius as per user preference)
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

time_wind_gust_max
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pgtm
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Peak gust time (hours and minutes, i.e., HHMM)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

time_wind_gust_max_1mile_or_1min
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fmtm
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Time of fastest mile or fastest 1-minute wind (hours and minutes, i.e., HHMM)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

water_equivalent_snow_depth
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wesd
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Water equivalent of snow on the ground (inches or mm as per user preference)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

water_equivalent_snow_depth_new
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wesf
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Water equivalent of snowfall (inches or mm as per user preference)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

water_equivalent_snow_depth_new
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wesf
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Water equivalent of snowfall (inches or mm as per user preference)
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

weather_type_blowing_drifting_snow
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt09
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Blowing or drifting snow
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_blowing_spray
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt12
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Blowing spray
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_drizzle
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt14
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Drizzle
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_dust_ash_sand
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt07
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Dust, volcanic ash, blowing dust, blowing sand, or blowing obstruction
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_fog
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt01
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Fog, ice fog, or freezing fog (may include heavy fog)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_freezing_drizzle
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt15
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Freezing drizzle
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_freezing_rain
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt17
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Freezing rain
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_glaze_rime
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt06
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Glaze or rime
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_ground_fog
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt21
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Ground fog
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_hail
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt05
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Hail (may include small hail)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_heavy_fog
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt02
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Heavy fog or heaving freezing fog (not always distinguished from fog)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_high_damaging_winds
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt11
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - High or damaging winds
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_ice_fog_freezing_fog
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt22
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Ice fog or freezing fog
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_ice_sleet_snow_hail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt04
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Ice pellets, sleet, snow pellets, or small hail
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_mist
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt13
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Mist
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_precipitation_unknown_source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt19
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Unknown source of precipitation
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_rain
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt16
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Rain (may include freezing rain, drizzle, and freezing drizzle)
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_smoke_haze
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt08
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Smoke or haze
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_snow_pellets_snow_grains_ice_crystals
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt18
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Snow, snow pellets, snow grains, or ice crystals
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_thunder
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt03
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Thunder
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_tornado_waterspout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wt10
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Tornado, waterspout, or funnel cloud
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_vicinity_dust_ash_sand
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wv07
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Ash, dust, sand, or other blowing obstruction in the Vicinity
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_vicinity_fog_any
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wv01
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Fog, ice fog, or freezing fog (may include heavy fog) in the Vicinity
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_vicinity_rain_snow_shower
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wv20
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Rain or snow shower in the Vicinity
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_vicinity_snow_ice_crystals
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wv18
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Snow or ice crystals in the Vicinity
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

weather_type_vicinity_thunder
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wv03
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Thunder in the Vicinity
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

wind_direction_gust_max
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wdfg
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Direction of peak wind gust (degrees)
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_direction_gust_max_1mile
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wdfm
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Fastest mile wind direction (degrees)
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_direction_gust_max_1min
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wdf1
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Direction of fastest 1-minute wind (degrees)
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_direction_gust_max_2min
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wdf2
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Direction of fastest 2-minute wind (degrees)
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_direction_gust_max_5sec
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wdf5
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Direction of fastest 5-second wind (degrees)
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_direction_gust_max_instant
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wdfi
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Direction of highest instantaneous wind (degrees)
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_gust_max
^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wsfg
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Peak guest wind speed (miles per hour or  meters per second as per user preference)
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_1mile
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wsfm
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Fastest mile wind speed (miles per hour or  meters per second as per user preference)
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_instant
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wsfi
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Highest instantaneous wind speed (miles per hour or  meters per second as per user preference)
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_1min
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wsf1
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Fastest 1-minute wind speed (miles per hour or  meters per second as per user preference)
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_2min
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wsf2
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Fastest 2-minute wind speed (miles per hour or  meters per second as per user preference)
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_5sec
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wsf5
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Fastest 5-second wind speed (miles per hour or  meters per second as per user preference)
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_movement_24h
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wdmv
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - 24-hour wind movement (km or miles as per user preference, miles on Daily Form pdf file)
   * - origin unit
     - :math:`km`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

wind_movement_multiday
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mdwm
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Multiday wind movement (miles or km as per user preference)
   * - origin unit
     - :math:`km`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

wind_speed
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - awnd
   * - description file
     - `NOAA GHCN dataset description`_
   * - description
     - Average daily wind speed (meters per second or miles per hour as per user preference)
       pdf file
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`
