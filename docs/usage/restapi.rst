REST API
########

Wetterdienst has an integrated REST API which can be started by invoking::

    wetterdienst restapi

There's also a hosted version at wetterdienst.eobs.org .

The following examples use `httpie <https://github.com/httpie/cli>`_ to demonstrate the usage of the REST API.

Examples
********

Coverage
========
::

    http localhost:7890/api/coverage

Stations
========
::

    # Acquire list of DWD OBS stations.
    http localhost:7890/api/stations provider==dwd network==observation parameter==kl resolution==daily period==recent all==true

    # Query list of stations with SQL.
    http localhost:7890/api/stations provider==dwd network==observation parameter==kl resolution==daily period==recent sql=="SELECT * FROM data WHERE lower(name) LIKE lower('%dresden%');"

    # Acquire list of DWD DMO stations.
    http localhost:7890/api/stations provider==dwd network==dmo parameter==temperature_air_mean_200 resolution==icon period==recent all==true

Values
======
::

    # Acquire observations.
    http localhost:7890/api/values provider==dwd network==observation parameter==kl resolution==daily period==recent station==1048,4411

    # Observations for specific date.
    http localhost:7890/api/values provider==dwd network==observation parameter==kl resolution==daily period==recent station==1048,4411 date==2020-08-01

    # Observations for date range.
    http localhost:7890/api/values provider==dwd network==observation parameter==kl resolution==daily period==recent station==1048,4411 date==2020-08-01/2020-08-05

    # Observations with SQL.
    http localhost:7890/api/values provider==dwd network==observation parameter==kl resolution==daily period==recent station==1048,4411 shape=="wide" sql=="SELECT * FROM data WHERE temperature_air_max_200 < 2.0;"

    # Acquire ICON data.
    http localhost:7890/api/values provider==dwd network==dmo parameter==temperature_air_mean_200 resolution==icon station==01001 date==2024-05-27
