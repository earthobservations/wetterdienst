Hourly
######

Metadata
********

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - hourly
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/>`_

Datasets
********

Temperature_air
===============

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - air_temperature
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/>`_
   * - description file
     - `air_temperature dataset description`_
   * - description
     - Historical hourly station observations of 2m air temperature and humidity for Germany

.. _air_temperature dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/historical/DESCRIPTION_obsgermany_climate_hourly_tu_historical_en.pdf

Parameters
----------

temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tt_tu
   * - description file
     - `air_temperature dataset description`_
   * - description
     - 2m air temperature
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

humidity
^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rf_tu
   * - description file
     - `air_temperature dataset description`_
   * - description
     - 2m relative humidity
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

Cloud_type
==========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - air_temperature
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloud_type/>`_
   * - description file
     - `cloud_type dataset description`_
   * - description
     - Historical hourly station observations of cloud cover, cloud type and cloud height in up to 4 layers for Germany

.. _cloud_type dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloud_type/historical/DESCRIPTION_obsgermany_climate_hourly_cloud_type_historical_en.pdf

Parameters
----------

cloud_cover_total
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_n
   * - description file
     - `cloud_type dataset description`_
   * - description
     - total cloud cover
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{8}`

cloud_type_layer1
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s1_cs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud type of 1. layer

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - cloud type
          * - 0
            - cirrus
          * - 1
            - cirrocumulus
          * - 2
            - cirrostratus
          * - 3
            - altocumulus
          * - 4
            - altostratus
          * - 5
            - nimbostratus
          * - 6
            - stratocumulus
          * - 7
            - stratus
          * - 8
            - cumulus
          * - 9
            - cumulonimbus
          * - -1
            - automated

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1]`

cloud_height_layer1
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s1_hhs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - height of 1.layer
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

cloud_cover_layer1
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s1_ns
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud cover of 1. layer
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{8}`

cloud_type_layer2
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s2_cs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud type of 2. layer

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - cloud type
          * - 0
            - cirrus
          * - 1
            - cirrocumulus
          * - 2
            - cirrostratus
          * - 3
            - altocumulus
          * - 4
            - altostratus
          * - 5
            - nimbostratus
          * - 6
            - stratocumulus
          * - 7
            - stratus
          * - 8
            - cumulus
          * - 9
            - cumulonimbus
          * - -1
            - automated

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1]`

cloud_height_layer2
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s2_hhs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - height of 2.layer
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

cloud_cover_layer2
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s2_ns
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud cover of 2. layer
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{8}`

cloud_type_layer3
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s3_cs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud type of 3. layer

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - cloud type
          * - 0
            - cirrus
          * - 1
            - cirrocumulus
          * - 2
            - cirrostratus
          * - 3
            - altocumulus
          * - 4
            - altostratus
          * - 5
            - nimbostratus
          * - 6
            - stratocumulus
          * - 7
            - stratus
          * - 8
            - cumulus
          * - 9
            - cumulonimbus
          * - -1
            - automated

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1]`

cloud_height_layer3
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s3_hhs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - height of 3.layer
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

cloud_cover_layer3
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s3_ns
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud cover of 3. layer
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{8}`

cloud_type_layer4
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s4_cs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud type of 4. layer

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - cloud type
          * - 0
            - cirrus
          * - 1
            - cirrocumulus
          * - 2
            - cirrostratus
          * - 3
            - altocumulus
          * - 4
            - altostratus
          * - 5
            - nimbostratus
          * - 6
            - stratocumulus
          * - 7
            - stratus
          * - 8
            - cumulus
          * - 9
            - cumulonimbus
          * - -1
            - automated

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1]`

cloud_height_layer4
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s4_hhs
   * - description file
     - `cloud_type dataset description`_
   * - description
     - height of 4.layer
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

cloud_cover_layer4
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_s4_ns
   * - description file
     - `cloud_type dataset description`_
   * - description
     - cloud cover of 4. layer
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{8}`

Cloudiness
==========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - cloudiness
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/>`_
   * - description file
     - `cloudiness dataset description`_
   * - description
     - Historical hourly station observations of cloudiness for Germany

.. _cloudiness dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/historical/DESCRIPTION_obsgermany_climate_hourly_cloudiness_historical_en.pdf

Parameters
----------

cloud_cover_total_indicator
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_n_i
   * - description file
     - `cloudiness dataset description`_
   * - description
     - index how measurement is taken

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - meaning
          * - P
            - human person
          * - I
            - instrument

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [P, I]`

cloud_cover_total
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_n
   * - description file
     - `cloudiness dataset description`_
   * - description
     - total cloud cover
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\in [0, 1, 2, 3, 4, 5, 6, 7, 8, -1]`, -1: not determined

Dew_point
=========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dew_point
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/>`_
   * - description file
     - `dew_point dataset description`_
   * - description
     - Historical hourly station observations of air and dew point temperature 2 m above ground in °C for Germany

.. _dew_point dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/historical/DESCRIPTION_obsgermany_climate_hourly_dew_point_historical_en.pdf

Parameters
----------

temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tt
   * - description file
     - `dew_point dataset description`_
   * - description
     - air temperature
   * - origin unit
     - :math:`°C`
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
     - `dew_point dataset description`_
   * - description
     - dew point temperature
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

Wind_extreme
============

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - extreme_wind
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/extreme_wind/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Historical hourly station observations of maximum wind speed in 10m height for Germany

Parameters
----------

wind_gust_max
^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx_911
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - maximum wind speed in 10m height
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

Moisture
========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - moisture
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/moisture/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Historical hourly station observations of humidity, absolute humidity, vapor pressure, air pressure,
       wet temperature, air temperature and dew point temperature for Germany


Parameters
----------

humidity_absolute
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - absf_std
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - absolute humidity
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

pressure_vapor
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - vp_std
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - vapor pressure
   * - origin unit
     - :math:`hPa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

temperature_wet_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tf_std
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - wet temperature
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

pressure_air_site
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - p_std
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - air pressure at site level
   * - origin unit
     - :math:`hPa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tt_std
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - air temperature at 2m height
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

humidity
^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rf_std
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - humidity
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

temperature_dew_point_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - td_std
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - dew point temperature at 2m height
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

Precipitation
=============

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - precipitation
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/>`_
   * - description file
     - `precipitation dataset description`_
   * - description
     - Historical hourly station observations of precipitation for Germany

.. _precipitation dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/historical/DESCRIPTION_obsgermany_climate_hourly_precipitation_historical_en.pdf

Parameters
----------

precipitation_height
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - r1
   * - description file
     - `precipitation dataset description`_
   * - description
     - hourly precipitation height
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_indicator
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rs_ind
   * - description file
     - `precipitation dataset description`_
   * - description
     - precipitation index

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - meaning
          * - 0
            - no precipitation
          * - 1
            - precipitation has fallen

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [0, 1]`

precipitation_form
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wrtr
   * - description file
     - `precipitation dataset description`_
   * - description
     - form of precipitation

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - meaning
          * - 0
            - no fallen precipitation or too little deposition (e.g., dew or frost) to form a precipitation height
              larger than 0.0, for automatic stations this corresponds to WMO code 10
          * - 1
            - precipitation height only due to deposition (dew or frost) or if it cannot decided how large the part from
              deposition is
          * - 2
            - precipitation height only due to liquid deposition
          * - 3
            - precipitation height only due to solid precipitation
          * - 6
            - precipitation height due to fallen liquid precipitation, may also include deposition of any kind, or
              automatic stations this corresponds to WMO code 11
          * - 7
            - precipitation height due to fallen solid precipitation, may also include deposition of any kind, for
              automatic stations this corresponds to WMO code 12
          * - 8
            - fallen precipitation in liquid and solid form, for automatic stations this corresponds to WMO code 13
          * - 9
            - no precipitation measurement, form of precipitation cannot be determined, for automatic stations this
              corresponds to WMO code 15

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [0, 1, 2, 3, 6, 7, 8, 9]`

Pressure
========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pressure
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/>`_
   * - description file
     - `pressure dataset description`_
   * - description
     - Historical hourly station observations of pressure for Germany

.. _pressure dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/historical/DESCRIPTION_obsgermany_climate_hourly_pressure_historical_en.pdf

Parameters
----------

pressure_air_sea_level
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - p
   * - description file
     - `pressure dataset description`_
   * - description
     - mean sea level pressure
   * - origin unit
     - :math:`hPa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

pressure_air_site
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - p0
   * - description file
     - `pressure dataset description`_
   * - description
     - mean sea level pressure
   * - origin unit
     - :math:`hPa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

Temperature_soil
================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - soil_temperature
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/>`_
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - Historical hourly station observations of soil temperature station data for Germany

.. _soil_temperature dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/historical/DESCRIPTION_obsgermany_climate_hourly_soil_temperature_historical_en.pdf

Parameters
----------

temperature_soil_mean_0_02m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_te002
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - soil temperature in 2 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_te005
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - soil temperature in 5 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_te010
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - soil temperature in 10 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_te020
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - soil temperature in 20 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_te050
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - soil temperature in 50 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_1m
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_te100
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - soil temperature in 100 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

Solar
=====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - solar
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/>`_
   * - description file
     - `solar dataset description`_
   * - description
     - Hourly station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany

.. _solar dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf

Parameters
----------

radiation_sky_long_wave
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - atmo_lberg
   * - description file
     - `solar dataset description`_
   * - description
     - hourly sum of longwave downward radiation
   * - origin unit
     - :math:`J / cm^2`
   * - SI unit
     - :math:`J / m^2`
   * - constraints
     - :math:`\geq{0}`

radiation_sky_short_wave_diffuse
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fd_lberg
   * - description file
     - `solar dataset description`_
   * - description
     - hourly sum of diffuse solar radiation
   * - origin unit
     - :math:`J / cm^2`
   * - SI unit
     - :math:`J / m^2`
   * - constraints
     - :math:`\geq{0}`

radiation_global
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fg_lberg
   * - description file
     - `solar dataset description`_
   * - description
     - hourly sum of solar incoming radiation
   * - origin unit
     - :math:`J / cm^2`
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
     - sd_lberg
   * - description file
     - `solar dataset description`_
   * - description
     - hourly sum of sunshine duration
   * - origin unit
     - :math:`min`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

sun_zenith_angle
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - zenit
   * - description file
     - `solar dataset description`_
   * - description
     - solar zenith angle at mid of interval
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{180}`

Sun
====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sun
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/>`_
   * - description file
     - `sun dataset description`_
   * - description
     - Historical hourly station observations of sunshine duration for Germany

.. _sun dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/historical/DESCRIPTION_obsgermany_climate_hourly_sun_historical_en.pdf

Parameters
----------

sunshine_duration
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sd_so
   * - description file
     - `sun dataset description`_
   * - description
     - hourly sunshine duration
   * - origin unit
     - :math:`min`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

Visibility
==========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - visibility
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/>`_
   * - description file
     - `visibility dataset description`_
   * - description
     - Historical hourly station observations of visibility for Germany

.. _visibility dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/historical/DESCRIPTION_obsgermany_climate_hourly_visibility_historical_en.pdf

Parameters
----------

visibility_range_indicator
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_vv_i
   * - description file
     - `visibility dataset description`_
   * - description
     - index how measurement is taken

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - meaning
          * - P
            - by human person
          * - I
            - by instrument

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [P, I]`

visibility_range
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_vv
   * - description file
     - `visibility dataset description`_
   * - description
     - visibility
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

Weather_phenomena
=================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - weather_phenomena
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Historical hourly weather phenomena at stations in Germany

Parameters
----------

weather
^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ww
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - weather code of current condition, see `weather codes and descriptions`_
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

.. _weather codes and descriptions: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/historical/Wetter_Beschreibung.txt

weather_text
^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ww_text
   * - description file
     - missing, taken from `DWD parameter listing`_
   * - description
     - weather text of current condition, see `weather codes and descriptions`_
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - none

Wind
====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wind
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/>`_
   * - description file
     - `wind dataset description`_
   * - description
     - Historical hourly station observations of wind speed and wind direction for Germany

.. _wind dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/historical/DESCRIPTION_obsgermany_climate_hourly_wind_historical_en.pdf

Parameters
----------

wind_speed
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - f
   * - description file
     - `wind dataset description`_
   * - description
     - mean wind speed
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_direction
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - d
   * - description file
     - `wind dataset description`_
   * - description
     - mean wind direction
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

Wind_synoptic
=============

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wind_synop
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/>`_
   * - description file
     - `wind_synoptic dataset description`_
   * - description
     - Historical hourly station observations of windspeed and -direction in m/s for Germany

.. _wind_synoptic dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/historical/DESCRIPTION_obsgermany_climate_hourly_wind_synop_historical_en.pdf

Parameters
----------

wind_speed
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ff
   * - description file
     - `wind_synoptic dataset description`_
   * - description
     - mean wind speed
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_direction
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dd
   * - description file
     - `wind_synoptic dataset description`_
   * - description
     - mean wind direction
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

.. note::

    The following **urban datasets** are located at the **climate_urban** directory instead of the **climate**
    directory.

Urban_temperature_air
=====================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - air_temperature (climate_urban)
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/>`_
   * - description file
     - `urban_temperature_air dataset description`_
   * - description
     - Recent hourly air temperature and humidity, observed at urban stations for selected urban areas in Germany

.. _urban_temperature_air dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_tu_recent_en.pdf

Parameters
----------

temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - lufttemperatur
   * - description file
     - `urban_temperature_air dataset description`_
   * - description
     - 2m air temperature
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

humidity
^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rel_feuchte
   * - description file
     - `urban_temperature_air dataset description`_
   * - description
     - 2m relative humidity
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

Urban_precipitation
===================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - precipitation (climate_urban)
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/>`_
   * - description file
     - `urban_precipitation dataset description`_
   * - description
     - Recent hourly precipitation, observed at urban stations for selected urban areas in Germany

.. _urban_precipitation dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/recent/DESCRIPTION_obsgermany_climate_urban_hourly_precipitation_recent_en.pdf

Parameters
----------

precipitation_height
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - niederschlagshoehe
   * - description file
     - `urban_precipitation dataset description`_
   * - description
     - precipitation height
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

Urban_pressure
==============

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pressure (climate_urban)
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/>`_
   * - description file
     - `urban_pressure dataset description`_
   * - description
     - Recent hourly pressure, observed at urban stations for selected urban areas in Germany

.. _urban_pressure dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/recent/DESCRIPTION_obsgermany_climate_urban_hourly_pressure_recent_en.pdf

Parameters
----------

pressure_air_site
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - luftdruck_stationshoehe
   * - description file
     - `urban_pressure dataset description`_
   * - description
     - pressure at station height
   * - origin unit
     - :math:`hPa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

Urban_temperature_soil
======================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - soil_temperature (climate_urban)
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/>`_
   * - description file
     - `urban_temperature_soil dataset description`_
   * - description
     - Recent hourly soil temperature, observed at urban stations for selected urban areas in Germany

.. _urban_temperature_soil dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_soil_temperature_recent_en.pdf

Parameters
----------

temperature_soil_mean_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - erdbt_005
   * - description file
     - `urban_temperature_soil dataset description`_
   * - description
     - soil temperature in 5 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_0_1m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - erdbt_010
   * - description file
     - `urban_temperature_soil dataset description`_
   * - description
     - soil temperature in 10 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_0_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - erdbt_020
   * - description file
     - `urban_temperature_soil dataset description`_
   * - description
     - soil temperature in 20 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_0_5m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - erdbt_050
   * - description file
     - `urban_temperature_soil dataset description`_
   * - description
     - soil temperature in 50 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_soil_mean_1m
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - erdbt_100
   * - description file
     - `urban_temperature_soil dataset description`_
   * - description
     - soil temperature in 100 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

Urban_sun
=========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sun (climate_urban)
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/>`_
   * - description file
     - `urban_sun dataset description`_
   * - description
     - Recent hourly sunshine duration, observed at urban stations for selected urban areas in Germany

.. _urban_sun dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/recent/DESCRIPTION_obsgermany_climate_urban_hourly_sun_recent_en.pdf

Parameters
----------

sunshine_duration
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sonnenscheindauer
   * - description file
     - `urban_sun dataset description`_
   * - description
     - sunshine duration
   * - origin unit
     - :math:`min`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

Urban_wind
==========

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wind (climate_urban)
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/>`_
   * - description file
     - `urban_wind dataset description`_
   * - description
     - Recent hourly wind speed and direction, observed at urban stations for selected urban areas in Germany

.. _urban_wind dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/recent/DESCRIPTION_obsgermany_climate_urban_hourly_wind_recent_en.pdf

Parameters
----------

wind_speed
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - windgeschwindigkeit
   * - description file
     - `urban_wind dataset description`_
   * - description
     - mean windspeed at 368m height
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_direction
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - windrichtung
   * - description file
     - `urban_wind dataset description`_
   * - description
     - mean wind direction at 368m height
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

.. _DWD parameter listing: https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx
