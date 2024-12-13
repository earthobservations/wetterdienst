Minute_10
#########

Metadata
********

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - 10_minutes
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/>`_

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/>`_
   * - description file
     - `air_temperature dataset description`_
   * - description
     - Historical 10-minute station observations of pressure, air temperature (at 5cm and 2m height), humidity and dew point for Germany

.. _air_temperature dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/historical/DESCRIPTION_obsgermany_climate_10min_tu_historical_en.pdf

Parameters
----------

pressure_air_site
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pp_10
   * - description file
     - `air_temperature dataset description`_
   * - description
     - pressure at station height
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
     - tt_10
   * - description file
     - `air_temperature dataset description`_
   * - description
     - air temperature at 2m height
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_air_mean_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tm5_10
   * - description file
     - `air_temperature dataset description`_
   * - description
     - air temperature at 5cm height
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
     - rf_10
   * - description file
     - `air_temperature dataset description`_
   * - description
     - relative humidity at 2m height
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
     - td_10
   * - description file
     - `air_temperature dataset description`_
   * - description
     - dew point temperature at 2m height, the dew point temperature is calculated from the temperature and relative humidity measurements
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

Temperature_extreme
===================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - extreme_temperature
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/>`_
   * - description file
     - `extreme_temperature dataset description`_
   * - description
     - Historical 10-minute station observations of max/min temperature at 5cm and 2m height above ground for Germany

.. _extreme_temperature dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/historical/DESCRIPTION_obsgermany_climate_10min_tx_historical_en.pdf

Parameters
----------

temperature_air_max_2m
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tx_10
   * - description file
     - `extreme_temperature dataset description`_
   * - description
     - maximum of air temperature at 2m height during the last 10 minutes
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_air_max_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tx5_10
   * - description file
     - `extreme_temperature dataset description`_
   * - description
     - maximum of air temperature at 5cm height during the last 10 minutes
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_air_min_2m
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tx_10
   * - description file
     - `extreme_temperature dataset description`_
   * - description
     - minimum of air temperature at 2m height during the last 10 minutes
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_air_min_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tx5_10
   * - description file
     - `extreme_temperature dataset description`_
   * - description
     - minimum of air temperature at 5cm height during the last 10 minutes
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/>`_
   * - description file
     - `extreme_wind dataset description`_
   * - description
     - Historical 10-minute station observations of max/min - mean wind speed and wind gust for Germany

.. _extreme_wind dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/historical/DESCRIPTION_obsgermany_climate_10min_fx_historical_en.pdf

Parameters
----------

wind_gust_max
^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx_10
   * - description file
     - `extreme_wind dataset description`_
   * - description
     - maximum wind gust of the last 10 minutes, the instrument samples the instantaneous wind velocity every 0.25
       seconds, and writes out the max value of a 3 second period, the highest occuring within the 10min interval is
       given here as the maximum wind gust.
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_speed_min
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fnx_10
   * - description file
     - `extreme_wind dataset description`_
   * - description
     - minimum 10-minute mean wind velocity. The 10-minutes interval is moved in 10s steps over the last 20 minutes
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_speed_rolling_mean_max
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fmx_10
   * - description file
     - `extreme_wind dataset description`_
   * - description
     - maximum 10-minute mean wind velocity. The 10-minutes interval is moved in 10s steps over the last 20 minutes
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_direction_gust_max
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dx_10
   * - description file
     - `extreme_wind dataset description`_
   * - description
     - wind direction of highest wind gust
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/>`_
   * - description file
     - `precipitation dataset description`_
   * - description
     - Historical 10-minute station observations of precipitation for Germany

.. _precipitation dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/historical/DESCRIPTION_obsgermany_climate_10min_precipitation_historical_en.pdf

Parameters
----------

precipitation_duration
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rws_dau_10
   * - description file
     - `precipitation dataset description`_
   * - description
     - duration of precipitation within the last 10 minutes
   * - origin unit
     - :math:`min`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

precipitation_height
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rws_10
   * - description file
     - `precipitation dataset description`_
   * - description
     - precipitation height of the last 10 minutes
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_indicator_wr
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rws_ind_10
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
          * - 3
            - precipitation has fallen and heating of instrument was on

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\in [0, 1, 3]`

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/solar/>`_
   * - description file
     - `solar dataset description`_
   * - description
     - Historical 10-minute station observations of solar incoming radiation, longwave downward radiation and sunshine
       duration for Germany

.. _solar dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/solar/historical/DESCRIPTION_obsgermany_climate_10min_solar_historical_en.pdf

Parameters
----------

radiation_sky_short_wave_diffuse
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ds_10
   * - description file
     - `solar dataset description`_
   * - description
     - 10min-sum of diffuse solar radiation
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
     - gs_10
   * - description file
     - `solar dataset description`_
   * - description
     - 10min-sum of solar incoming radiation
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
     - sd_10
   * - description file
     - `solar dataset description`_
   * - description
     - 10min-sum of sunshine duration
   * - origin unit
     - :math:`h`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

radiation_sky_long_wave
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ls_10
   * - description file
     - `solar dataset description`_
   * - description
     - 10min-sum of longwave downward radiation
   * - origin unit
     - :math:`J / cm^2`
   * - SI unit
     - :math:`J / m^2`
   * - constraints
     - :math:`\geq{0}`

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/>`_
   * - description file
     - `wind dataset description`_
   * - description
     - Historical 10-minute station observations of solar incoming radiation, longwave downward radiation and sunshine
       duration for Germany

.. _wind dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/solar/historical/DESCRIPTION_obsgermany_climate_10min_solar_historical_en.pdf

Parameters
----------

wind_speed
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ff_10
   * - description file
     - `wind dataset description`_
   * - description
     - mean of wind speed during the last 10 minutes
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
     - dd_10
   * - description file
     - `wind dataset description`_
   * - description
     - mean of wind direction during the last 10 minutes
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`
