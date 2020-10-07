.. wetterdienst-api:

###
API
###

.. contents::
    :local:
    :depth: 1


************
Introduction
************
The API offers access to different data products. They are
outlined in more detail within the :ref:`data-coverage` chapter.
Please also check out complete examples about how to use the API in the
`example <https://github.com/earthobservations/wetterdienst/tree/master/example>`_
folder.
In order to explore all features interactively,
you might want to try the :ref:`cli`.


************
Observations
************
Acquire historical weather data through requesting by
*parameter*, *time resolution* and *period type*.


Request arguments
=================
The options *parameter*, *time resolution* and *period type* can be used in three ways:

- by using the exact enumeration e.g.
    .. code-block:: python

        Parameter.CLIMATE_SUMMARY

- by using the enumeration string e.g.
    .. code-block:: python

        "climate_summary" or "CLIMATE_SUMMARY"

- by using the originally defined parameter string e.g.
    .. code-block:: python

        "kl"

Use ``DWDObservationMetadata.discover_parameters()`` to discover available
time resolution, parameter, period type combinations and their subsets
based on the obtained filter arguments.


Station list
============
Get station information for a given set of *parameter*, *time resolution*
and *period type* options.

.. code-block:: python

    from wetterdienst import DWDObservationSites
    from wetterdienst import Parameter, PeriodType, TimeResolution

    sites = DWDObservationSites(
        parameter=Parameter.PRECIPITATION_MORE,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

    df = sites.all()

The function returns a Pandas DataFrame with information about the available stations.
The column ``HAS_FILE`` indicates whether the station actually has a file with data on
the server. That might not always be the case for stations which have been phased out.


Measurements
============
Use the ``DWDObservationData`` class in order to get hold of measurement information.

.. code-block:: python

    from wetterdienst import DWDObservationData
    from wetterdienst import Parameter, PeriodType, TimeResolution

    observations = DWDObservationData(
        station_ids=[3, 1048],
        parameter=[Parameter.CLIMATE_SUMMARY, Parameter.SOLAR],
        time_resolution=TimeResolution.DAILY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
    )

    for df in observations.collect_data():
        # analyse the station here

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names and stored
automatically on the drive if wanted.


Geospatial support
==================

Inquire the list of stations by geographic coordinates.

- Calculate weather stations close to the given coordinates and set of parameters.
- Either select by rank (n stations) or by distance in km.

.. code-block:: python

    from datetime import datetime
    from wetterdienst import DWDObservationSites
    from wetterdienst import Parameter, PeriodType, TimeResolution

    sites = DWDObservationSites(
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20)
    )

    df = sites.nearby_radius(
        latitude=50.0,
        longitude=8.9,
        max_distance_in_km=30
    )

The function returns a DataFrame with the list of stations with distances [in km]
to the given coordinates.

The station ids within the DataFrame:

.. code-block:: python

    station_ids = stations.STATION_ID.unique()

can be used to download the observation data:

.. code-block:: python

    observations = DWDObservationData(
        station_ids=station_ids,
        parameter=[Parameter.TEMPERATURE_AIR, Parameter.SOLAR],
        time_resolution=TimeResolution.HOURLY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
    )

    for df in observations.collect_data():
        # analyse the station here

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments.


SQL support
===========
Querying data using SQL is provided by an in-memory DuckDB_ database.
In order to explore what is possible, please have a look at the `DuckDB SQL introduction`_.

The result data is provided through a virtual table called ``data``.

.. code-block:: python

    from wetterdienst import DWDObservationData
    from wetterdienst import Parameter, PeriodType, TimeResolution

    observations = DWDObservationData(
        station_ids=[1048],
        parameter=[Parameter.TEMPERATURE_AIR],
        time_resolution=TimeResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
    )

    df = observations.collect_safe().dwd.lower()
    df = df.io.sql("SELECT * FROM data WHERE element='temperature_air_200' AND value < -7.0;")
    print(df)


HDF5 storage
============
Wetterdienst can optionally persist acquired data to HDF5 files.
To use that feature, pass a ``StorageAdapter`` instance to
``DWDObservationData``.

.. code-block:: python

    from wetterdienst import DWDObservationData
    from wetterdienst import Parameter, PeriodType, TimeResolution

    storage = StorageAdapter(persist=True, folder="/path/to/dwd-archive")

    observations = DWDObservationData(
        station_ids=[1048],
        parameter=[Parameter.TEMPERATURE_AIR],
        time_resolution=TimeResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
        storage=storage,
    )

    df = observations.collect_safe().dwd.lower()
    print(df)


Data export
===========
Data can be exported to SQLite_, DuckDB_, InfluxDB_, CrateDB_ and more targets.
A target is identified by a connection string.

Examples:

- sqlite:///dwd.sqlite?table=weather
- duckdb:///dwd.duckdb?table=weather
- influxdb://localhost/?database=dwd&table=weather
- crate://localhost/?database=dwd&table=weather

.. code-block:: python

    from wetterdienst import DWDObservationData
    from wetterdienst import Parameter, PeriodType, TimeResolution

    observations = DWDObservationData(
        station_ids=[1048],
        parameter=[Parameter.TEMPERATURE_AIR],
        time_resolution=TimeResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
    )

    df = observations.collect_safe().dwd.lower()
    df.io.export("influxdb://localhost/?database=dwd&table=weather")


******
MOSMIX
******
::

    from wetterdienst.mosmix.api import MOSMIXRequest

    # MOSMIX-L, all parameters
    mosmix = MOSMIXRequest(station_ids=["01001", "01008"])
    response = mosmix.read_mosmix_l_latest()

    print(response.metadata)
    print(response.stations)
    print(response.forecasts)

Other variants::

    # MOSMIX-L, specific parameters
    mosmix = MOSMIXRequest(station_ids=["01001", "01008"], parameters=["DD", "ww"])
    response = mosmix.read_mosmix_l_latest()

    # MOSMIX-S, all parameters
    mosmix = MOSMIXRequest(station_ids=["01028", "01092"])
    response = mosmix.read_mosmix_s_latest()


*******
RADOLAN
*******

To use ``DWDRadolanRequest``, you have to provide a time resolution (either hourly or daily)
and ``date_times`` (list of datetimes or strings) or a start date and end date. Datetimes
are rounded to HH:50min as the data is packaged for this minute step. Additionally,
you can provide a folder to store/restore RADOLAN data to/from the local filesystem.

This is a short snippet which should give you an idea
how to use ``DWDRadolanRequest`` together with ``wradlib``.
For a more thorough example, please have a look at `example/radolan.py`_.

.. code-block:: python

    from wetterdienst import DWDRadolanRequest, TimeResolution
    import wradlib as wrl

    radolan = DWDRadolanRequest(
        TimeResolution.DAILY,
        start_date="2020-09-04T12:00:00",
        end_date="2020-09-04T12:00:00"
    )

    for item in radolan.collect_data():

        # Decode item.
        timestamp, buffer = item

        # Decode data using wradlib.
        data, attributes = wrl.io.read_radolan_composite(buffer)

        # Do something with the data (numpy.ndarray) here.


.. _wradlib: https://wradlib.org/
.. _example/radolan.py: https://github.com/earthobservations/wetterdienst/blob/master/example/radolan.py

.. _SQLite: https://www.sqlite.org/
.. _DuckDB: https://duckdb.org/docs/sql/introduction
.. _DuckDB SQL introduction: https://duckdb.org/docs/sql/introduction
.. _InfluxDB: https://github.com/influxdata/influxdb
.. _CrateDB: https://github.com/crate/crate
