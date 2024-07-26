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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/>`_

Datasets
********

Climate_summary
===============

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - kl
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/>`_
   * - description file
     - `kl dataset description`_
   * - description
     - Historical daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany

.. _kl dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/historical/DESCRIPTION_obsgermany_climate_daily_kl_historical_en.pdf

Parameters
----------

wind_gust_max
^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - fx
   * - description file
     - `kl dataset description`_
   * - description
     - daily maximum of wind gust
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
     - fm
   * - description file
     - `kl dataset description`_
   * - description
     - daily mean of wind speed
   * - origin unit
     - :math:`m / s`
   * - SI unit
     - :math:`m / s`
   * - constraints
     - :math:`\geq{0}`

precipitation_height
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rsk
   * - description file
     - `kl dataset description`_
   * - description
     - daily precipitation height
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_form
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rskf
   * - description file
     - `kl dataset description`_
   * - description
     - precipitation form

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - meaning
          * - 0
            - no precipitation (conventional or automatic measurement), relates to WMO code 10
          * - 1
            - only rain (before 1979)
          * - 4
            - unknown form of recorded precipitation
          * - 6
            - only rain; only liquid precipitation at automatic stations, relates to WMO code 11
          * - 7
            - only snow; only solid precipitation at automatic stations, relates to WMO code 12
          * - 8
            - rain and snow (and/or "Schneeregen"); liquid and solid precipitation at automatic stations, relates to WMO code 13
          * - 9
            - error or missing value or no automatic determination of precipitation form, relates to WMO code 15

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

sunshine_duration
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sdk
   * - description file
     - `kl dataset description`_
   * - description
     - daily sunshine duration
   * - origin unit
     - :math:`h`
   * - SI unit
     - :math:`s`
   * - constraints
     - :math:`\geq{0}`

snow_depth
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - shk_tag
   * - description file
     - `kl dataset description`_
   * - description
     - daily snow depth
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

cloud_cover_total
^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nm
   * - description file
     - `kl dataset description`_
   * - description
     - daily mean of cloud cover
   * - origin unit
     - :math:`1 / 8`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{8}`

pressure_vapor
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - vpm
   * - description file
     - `kl dataset description`_
   * - description
     - daily mean of vapor pressure
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
     - pm
   * - description file
     - `kl dataset description`_
   * - description
     - daily mean of pressure
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
     - tmk
   * - description file
     - `kl dataset description`_
   * - description
     - daily mean of temperature
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
     - upm
   * - description file
     - `kl dataset description`_
   * - description
     - daily mean of relative humidity
   * - origin unit
     - :math:`\%`
   * - SI unit
     - :math:`\%`
   * - constraints
     - :math:`\geq{0}, \leq{100}`

temperature_air_max_2m
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - txk
   * - description file
     - `kl dataset description`_
   * - description
     - daily maximum of temperature at 2m height
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
     - tnk
   * - description file
     - `kl dataset description`_
   * - description
     - daily minimum of temperature at 2m height
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

temperature_air_min_0_05m
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tgk
   * - description file
     - `kl dataset description`_
   * - description
     - daily minimum of air temperature at 5cm above ground
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

Precipitation_more
==================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - more_precip
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/>`_
   * - description file
     - `more_precip dataset description`_
   * - description
     - Historical daily precipitation observations for Germany

.. _more_precip dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/historical/DESCRIPTION_obsgermany_climate_daily_more_precip_historical_en.pdf

Parameters
----------

precipitation_height
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rs
   * - description file
     - `more_precip dataset description`_
   * - description
     - daily precipitation height
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

precipitation_form
^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rsf
   * - description file
     - `more_precip dataset description`_
   * - description
     - precipitation form

       .. list-table::
          :widths: 20 80
          :stub-columns: 1

          * - code
            - meaning
          * - 0
            - no precipitation (conventional or automatic measurement), relates to WMO code 10
          * - 1
            - only rain (before 1979)
          * - 4
            - unknown form of recorded precipitation
          * - 6
            - only rain; only liquid precipitation at automatic stations, relates to WMO code 11
          * - 7
            - only snow; only solid precipitation at automatic stations, relates to WMO code 12
          * - 8
            - rain and snow (and/or "Schneeregen"); liquid and solid precipitation at automatic stations, relates to WMO code 13
          * - 9
            - error or missing value or no automatic determination of precipitation form, relates to WMO code 15

   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

snow_depth
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sh_tag
   * - description file
     - `more_precip dataset description`_
   * - description
     - height of snow pack
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

snow_depth_new
^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nsh_tag
   * - description file
     - `more_precip dataset description`_
   * - description
     - fresh snow depth
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/solar/>`_
   * - description file
     - `solar dataset description`_
   * - description
     - Daily station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany

.. _solar dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/solar/DESCRIPTION_obsgermany_climate_daily_solar_en.pdf

Parameters
----------

radiation_sky_long_wave
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - atmo_strahl
   * - description file
     - `solar dataset description`_
   * - description
     - longwave downward radiation
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
     - fd_strahl
   * - description file
     - `solar dataset description`_
   * - description
     - daily sum of diffuse solar radiation
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
     - fg_strahl
   * - description file
     - `solar dataset description`_
   * - description
     - daily sum of solar incoming radiation
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
     - sd_strahl
   * - description file
     - `solar dataset description`_
   * - description
     - daily sum of sunshine duration
   * - origin unit
     - :math:`h`
   * - SI unit
     - :math:`s`
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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/soil_temperature/>`_
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - Historical daily station observations of soil temperature station data for Germany

.. _soil_temperature dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/soil_temperature/historical/DESCRIPTION_obsgermany_climate_daily_soil_temperature_historical_en.pdf

Parameters
----------

temperature_soil_mean_0_02m
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - v_te002m
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - daily soil temperature in 2 cm depth
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
     - v_te005m
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - daily soil temperature in 5 cm depth
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
     - v_te010m
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - daily soil temperature in 10 cm depth
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
     - v_te020m
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - daily soil temperature in 20 cm depth
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
     - v_te050m
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - daily soil temperature in 50 cm depth
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
     - v_te100m
   * - description file
     - `soil_temperature dataset description`_
   * - description
     - daily soil temperature in 100 cm depth
   * - origin unit
     - :math:`°C`
   * - SI unit
     - :math:`K`
   * - constraints
     - none

Water_equivalent
================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - water_equiv
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/water_equiv/>`_
   * - description file
     - `water_equiv dataset description`_
   * - description
     - Daily station observations of snow height and water equivalent for Germany

.. _water_equiv dataset description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/water_equiv/historical/DESCRIPTION_obsgermany_climate_daily_water_equiv_historical_en.pdf

Parameters
----------

snow_depth_excelled
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - ash_6
   * - description file
     - `water_equiv dataset description`_
   * - description
     - height of snow pack sample
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

snow_depth
^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sh_tag
   * - description file
     - `water_equiv dataset description`_
   * - description
     - total snow depth
   * - origin unit
     - :math:`cm`
   * - SI unit
     - :math:`m`
   * - constraints
     - :math:`\geq{0}`

water_equivalent_snow_depth
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - wash_6
   * - description file
     - `water_equiv dataset description`_
   * - description
     - total snow water equivalent
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
   * - constraints
     - :math:`\geq{0}`

water_equivalent_snow_depth_excelled
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - waas_6
   * - description file
     - `water_equiv dataset description`_
   * - description
     - sampled snow pack water eqivalent
   * - origin unit
     - :math:`mm`
   * - SI unit
     - :math:`kg / m^2`
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
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/weather_phenomena/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, ripe, sleet and
       hail for stations of Germany

.. _DWD parameter listing: https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx

----

Parameters
----------

----

count_weather_type_fog
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - nebel
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with fog of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_thunder
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - gewitter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with thunder of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_storm_strong_wind
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sturm_6
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with storm (strong wind) of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_storm_stormier_wind
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - sturm_8
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with storm (stormier wind) of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_dew
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - tau
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with dew of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_glaze
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - glatteis
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with glaze of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_ripe
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - reif
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with ripe of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_sleet
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - graupel
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with sleet of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_hail
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - hagel
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with hail of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

Weather_phenomena_more
======================

Metadata
--------

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - more_weather_phenomena
   * - url
     - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_weather_phenomena/>`_
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - Counts of (additional) weather phenomena sleet, hail, fog and thunder for stations of Germany

.. _DWD parameter listing: https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx

Parameters
----------

count_weather_type_sleet
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr_graupel
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with sleet of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_hail
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr_hagel
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with hail of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_fog
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr_nebel
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with fog of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`

count_weather_type_thunder
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 80
   :stub-columns: 1

   * - original name
     - rr_gewitter
   * - description file
     - missing, simple descriptions within `DWD parameter listing`_
   * - description
     - count of days with thunder of stations in Germany
   * - origin unit
     - :math:`-`
   * - SI unit
     - :math:`-`
   * - constraints
     - :math:`\geq{0}`
