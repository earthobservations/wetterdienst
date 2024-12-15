# 10_minutes

## metadata

| property      | value                                                                                          |
|---------------|------------------------------------------------------------------------------------------------|
| name          | 10_minutes                                                                                    |
| original name | 10_minutes                                                                                     |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/) |

## datasets

### temperature_air

#### metadata

| property         | value                                                                                                                                                                       |
|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | temperature_air                                                                                                                                                             |
| original name    | air_temperature                                                                                                                                                             |
| description      | Historical 10-minute station observations of pressure, air temperature (at 5cm and 2m height), humidity and dew point for Germany                                           |
| description file | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/DESCRIPTION_obsgermany_climate_10min_air_temperature_en.pdf) |
| url              | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/)                                                            |

#### parameters

| name                          | original name | description                                                                                                                         | unit       | original unit | constraints                |
|-------------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------|------------|---------------|----------------------------|
| pressure_air_site             | pp_10         | pressure at station height                                                                                                          | :math:`Pa` | :math:`hPa`   | :math:`\geq{0}`            |
| temperature_air_mean_2m       | tt_10         | air temperature at 2m height                                                                                                        | :math:`K`  | :math:`°C`    | :math:`None`               |
| temperature_air_mean_0_05m    | tm5_10        | air temperature at 5cm height                                                                                                       | :math:`K`  | :math:`°C`    | :math:`None`               |
| humidity                      | rf_10         | relative humidity at 2m height                                                                                                      | :math:`\%` | :math:`\%`    | :math:`\geq{0}, \leq{100}` |
| temperature_dew_point_mean_2m | td_10         | dew point temperature at 2m height, the dew point temperature is calculated from the temperature and relative humidity measurements | :math:`K`  | :math:`°C`    | :math:`None`               |

### temperature_extreme

#### metadata

| property         | value                                                                                                                                                                               |
|------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | temperature_extreme                                                                                                                                                                 |
| original name    | extreme_temperature                                                                                                                                                                 |
| description      | Historical 10-minute station observations of max/min temperature at 5cm and 2m height above ground for Germany                                                                      |
| description file | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/DESCRIPTION_obsgermany_climate_10min_extreme_temperature_en.pdf) |
| url              | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_temperature/)                                                                |

#### parameters

| name                      | original name | description                                                         | unit      | original unit | constraints  |
|---------------------------|---------------|---------------------------------------------------------------------|-----------|---------------|--------------|
| temperature_air_max_2m    | tx_10         | maximum of air temperature at 2m height during the last 10 minutes  | :math:`K` | :math:`°C`    | :math:`None` |
| temperature_air_max_0_05m | tx5_10        | maximum of air temperature at 5cm height during the last 10 minutes | :math:`K` | :math:`°C`    | :math:`None` |
| temperature_air_min_2m    | tn_10         | minimum of air temperature at 2m height during the last 10 minutes  | :math:`K` | :math:`°C`    | :math:`None` |
| temperature_air_min_0_05m | tn5_10        | minimum of air temperature at 5cm height during the last 10 minutes | :math:`K` | :math:`°C`    | :math:`None` |

### wind_extreme

#### metadata

| property         | value                                                                                                                                                                 |
|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | wind_extreme                                                                                                                                                          |
| original name    | extreme_wind                                                                                                                                                          |
| description      | Historical 10-minute station observations of max/min - mean wind speed and wind gust for Germany                                                                      |
| description file | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/DESCRIPTION_obsgermany_climate_10min_extreme_wind_en.pdf) |
| url              | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/)                                                         |

#### parameters

| name                        | original name | description                                                                                                                                                                                                                                                    | unit          | original unit | constraints                |
|-----------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|---------------|----------------------------|
| wind_gust_max               | fx_10         | maximum wind gust of the last 10 minutes, the instrument samples the instantaneous wind velocity every 0.25 seconds, and writes out the max value of a 3 second period, the highest occuring within the 10min interval is given here as the maximum wind gust. | :math:`m / s` | :math:`m / s` | :math:`\geq{0}`            |
| wind_speed_min              | fnx_10        | minimum 10-minute mean wind velocity. The 10-minutes interval is moved in 10s steps over the last 20 minutes                                                                                                                                                   | :math:`m / s` | :math:`m / s` | :math:`\geq{0}`            |
| wind_speed_rolling_mean_max | fmx_10        | maximum 10-minute mean wind velocity. The 10-minutes interval is moved in 10s steps over the last 20 minutes                                                                                                                                                   | :math:`m / s` | :math:`m / s` | :math:`\geq{0}`            |
| wind_direction_gust_max     | dx_10         | wind direction of highest wind gust                                                                                                                                                                                                                            | :math:`°`     | :math:`°`     | :math:`\geq{0}, \leq{360}` |

### precipitation

#### metadata

| property         | value                                                                                                                                                                   |
|------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | precipitation                                                                                                                                                           |
| original name    | precipitation                                                                                                                                                           |
| description      | Historical 10-minute station observations of precipitation for Germany                                                                                                  |
| description file | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/DESCRIPTION_obsgermany-climate-10min-precipitation_en.pdf) |
| url              | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/)                                                          |

#### parameters

| name                       | original name | description                                          | unit             | original unit | constraints           |
|----------------------------|---------------|------------------------------------------------------|------------------|---------------|-----------------------|
| precipitation_duration     | rws_dau_10    | duration of precipitation within the last 10 minutes | :math:`s`        | :math:`min`   | :math:`\geq{0}`       |
| precipitation_height       | rws_10        | precipitation height of the last 10 minutes          | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`       |
| precipitation_indicator_wr | rws_ind_10    | precipitation index                                  | :math:`-`        | :math:`-`     | :math:`\in [0, 1, 3]` |

Codes (precipitation_indicator_wr):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |

### solar

#### metadata

| property         | value                                                                                                                                                                         |
|------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | solar                                                                                                                                                                         |
| original name    | solar                                                                                                                                                                         |
| description      | Historical 10-minute station observations of solar incoming radiation, longwave downward radiation and sunshine duration for Germany                                          |
| description file | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/solar/historical/DESCRIPTION_obsgermany_climate_10min_solar_historical_en.pdf) |
| url              | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/solar/)                                                                        |

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
