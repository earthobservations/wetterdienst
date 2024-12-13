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
     - `NOAA NWS Observation Data`_

.. _NOAA NWS Observation Data: https://www.weather.gov/documentation/services-web-api

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
     - hourly
   * - url
     - `NOAA NWS Observation Data`_
   * - description file
     - missing, see `NOAA NWS Observation Data`_ for related information
   * - description
     - Historical hourly station observations (temperature, pressure, precipitation, etc.) for the US

Parameters
----------

humidity
^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - relativehumidity
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - relative humidity
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

precipitation_height
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - precipitationlasthour
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - precipitation height of last hour
   * - origin unit
     - :math:`mm`
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
     - precipitationlast3hours
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - precipitation height of last three hours
   * - origin unit
     - :math:`mm`
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
     - precipitationlast6hours
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - precipitation height of last six hours
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

pressure_air_sh
^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - barometricpressure
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - air pressure at station height
   * - origin unit
     - :math:`Pa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

pressure_air_sl
^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sealevelpressure
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - air pressure at sea level
   * - origin unit
     - :math:`Pa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

temperature_air_max_2m_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - maxtemperaturelast24hours
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - maximum air temperature in the last 24 hours
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - temperature
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - Average air temperature in 2m
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_air_min_2m_last_24h
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - mintemperaturelast24hours
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - minimum air temperature in the last 24 hours
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_dew_point_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dewpoint
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - Average dew point temperature in 2m
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

temperature_wind_chill
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - windchill
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - wind chill temperature calculated by NWS (https://www.weather.gov/gjt/windchill)
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - :math:`None`

visibility_range
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - visibility
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - visibility range
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

wind_direction
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - winddirection
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - wind direction
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
     - windgust
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - maximum wind gust
   * - origin unit
     - :math:`km / h`
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
     - windspeed
   * - description file
     - `NOAA NWS Observation Data`_
   * - description
     - wind speed
   * - origin unit
     - :math:`km / h`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`
