HTTP API
********

Wetterdienst has an integrated HTTP API which can be started by invoking::

    wetterdienst restapi


Examples
========


Station list
------------
::

    # Acquire list of stations.
    http localhost:7890/api/dwd/observation/stations parameter==kl resolution==daily period==recent

    # Query list of stations with SQL.
    http localhost:7890/api/dwd/observation/stations parameter==kl resolution==daily period==recent sql=="SELECT * FROM data WHERE lower(station_name) LIKE lower('%dresden%');"


Observations
------------
::

    # Acquire observations.
    http localhost:7890/api/dwd/observation/values stations==1048,4411 parameter==kl resolution==daily period==recent

    # Observations for specific date.
    http localhost:7890/api/dwd/observation/values stations==1048,4411 parameter==kl resolution==daily period==recent date==2020-08-01

    # Observations for date range.
    http localhost:7890/api/dwd/observation/values stations==1048,4411 parameter==kl resolution==daily period==recent date==2020-08-01/2020-08-05

    # Observations with SQL.
    http localhost:7890/api/dwd/observation/values stations==1048,4411 parameter==kl resolution==daily period==recent shape=="wide" sql=="SELECT * FROM data WHERE temperature_air_max_200 < 2.0;"
