Subdaily
########

Metadata
********

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - subdaily
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/>`_
   * - resolution
     - measurements at 7am, 2pm, 9pm

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/air_temperature/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent subdaily air temperature and humidity of stations in Germany

.. _DWD parameter listing: https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx

Parameters
----------

temperature_air_mean_2m
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tt_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
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
     - rf_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - 2m relative humidity
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/cloudiness/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent subdaily cloud cover and cloud density of stations in Germany

Parameters
----------

cloud_cover_total
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - n_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - total cloud cover
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{8}`

cloud_density
^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - cd_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - cloud density
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/extreme_wind/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent subdaily extreme wind of stations in Germany

Parameters
----------

wind_gust_max_last_3h
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx_911_3
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - wind speed maximum of last 3 hours
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

wind_gust_max_last_6h
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx_911_6
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - wind speed maximum of last 6 hours
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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/moisture/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent subdaily vapor pressure, mean temperature in 2m height, mean temperature in 5cm height and humidity of
       stations in Germany

Parameters
----------

pressure_vapor
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - vp_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - vapor pressure of stations in Germany
   * - origin unit
     - :math:`hPa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

temperature_air_mean_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - e_tf_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - air temperature at 5cm height of stations in Germany
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
     - tf_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - air temperature at 2m height of stations in Germany
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
     - rf_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - humidity of stations in Germany
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/pressure/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent air pressure at site of stations in Germany
       stations in Germany

Parameters
----------

pressure_air_site
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - pp_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - air pressure of site
   * - origin unit
     - :math:`hPa`
   * - SI unit
     - :math:`Pa`
   * - constraints
     - :math:`\geq{0}`

Soil
====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - soil
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/soil/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent soil temperature in 5cm depth of stations in Germany

Parameters
----------

temperature_soil_mean_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ek_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - soil temperature at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

Soil
====

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - soil
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/soil/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent soil temperature in 5cm depth of stations in Germany

Parameters
----------

temperature_soil_mean_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ek_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - soil temperature at 5cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/visibility/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent visibility range of stations in Germany

Parameters
----------

visibility_range
^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - vk_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - visibility range
   * - origin unit
     - :math:`m`
   * - SI unit
     - :math:`m`
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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/wind/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Recent wind direction and wind force (beaufort) of stations in Germany

Parameters
----------

wind_direction
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - dk_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - wind direction
   * - origin unit
     - :math:`°`
   * - SI unit
     - :math:`°`
   * - constraints
     - :math:`\geq{0}, \leq{360}`

wind_force_beaufort
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fk_ter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - wind force (beaufort)
   * - origin unit
     - :math:`Bft`
   * - SI unit
     - :math:`Bft`
   * - constraints
     - :math:`\geq{0}`
