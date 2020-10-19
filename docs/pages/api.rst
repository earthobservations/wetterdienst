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

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationSites, DWDObsParameterSet,
        DWDObsPeriodType, DWDObsTimeResolution

    sites = DWDObservationSites(
        parameter=DWDObsParameterSet.PRECIPITATION_MORE,
        time_resolution=DWDObsTimeResolution.DAILY,
        period_type=DWDObsPeriodType.HISTORICAL
    )

    df = sites.all()

    print(df)

The function returns a Pandas DataFrame with information about the available stations.
The column ``HAS_FILE`` indicates whether the station actually has a file with data on
the server. That might not always be the case for stations which have been phased out.


Measurements
============
Use the ``DWDObservationData`` class in order to get hold of measurement information.

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationData, DWDObsParameterSet,
        DWDObsPeriodType, DWDObsTimeResolution

    observations = DWDObservationData(
        station_ids=[3, 1048],
        parameter=[DWDObsParameterSet.CLIMATE_SUMMARY, DWDObsParameterSet.SOLAR],
        time_resolution=DWDObsTimeResolution.DAILY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
    )

    for df in observations.collect_data():
        # analyse the station here
        print(df)

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names and stored
automatically on the drive if wanted.


Geospatial support
==================

Inquire the list of stations by geographic coordinates.

- Calculate weather stations close to the given coordinates and set of parameters.
- Either select by rank (n stations) or by distance in km.

.. ipython:: python

    from datetime import datetime
    from wetterdienst.dwd.observations import DWDObservationSites, DWDObsParameterSet,
        DWDObsPeriodType, DWDObsTimeResolution

    sites = DWDObservationSites(
        DWDObsParameterSet.TEMPERATURE_AIR,
        DWDObsTimeResolution.HOURLY,
        DWDObsPeriodType.RECENT,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20)
    )

    df = sites.nearby_radius(
        latitude=50.0,
        longitude=8.9,
        max_distance_in_km=30
    )

    print(df)

The function returns a DataFrame with the list of stations with distances [in km]
to the given coordinates.

The station ids within the DataFrame:

.. ipython:: python

    station_ids = stations.STATION_ID.unique()

can be used to download the observation data:

.. ipython:: python

    observations = DWDObservationData(
        station_ids=station_ids,
        parameter=[DWDObsParameterSet.TEMPERATURE_AIR, DWDObsParameterSet.SOLAR],
        DWDObsTimeResolution=TimeResolution.HOURLY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
    )

    for df in observations.collect_data():
        # analyse the station here
        print(df)

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments.


SQL support
===========
Querying data using SQL is provided by an in-memory DuckDB_ database.
In order to explore what is possible, please have a look at the `DuckDB SQL introduction`_.

The result data is provided through a virtual table called ``data``.

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationData, DWDObsParameterSet,
        DWDObsPeriodType, DWDObsTimeResolution

    observations = DWDObservationData(
        station_ids=[1048],
        parameter=[DWDObsParameterSet.TEMPERATURE_AIR],
        time_resolution=DWDObsTimeResolution.HOURLY,
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

    from wetterdienst.dwd.observations import DWDObservationData, DWDObsParameterSet,
        DWDObsPeriodType, DWDObsTimeResolution, StorageAdapter

    storage = StorageAdapter(persist=True, folder="/path/to/dwd-archive")

    observations = DWDObservationData(
        station_ids=[1048],
        parameter=[DWDObsParameterSet.TEMPERATURE_AIR],
        time_resolution=DWDObsTimeResolution.HOURLY,
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

    from wetterdienst.dwd.observations import DWDObservationData, DWDObsParameterSet,
        DWDObsPeriodType, DWDObsTimeResolution, StorageAdapter

    observations = DWDObservationData(
        station_ids=[1048],
        parameter=[DWDObsParameterSet.TEMPERATURE_AIR],
        time_resolution=DWDObsTimeResolution.HOURLY,
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
MOSMIX-S - less parameters:
.. code-block:: python

    from wetterdienst.dwd.forecasts import DWDMosmixData, DWDFcstPeriodType

    mosmix = DWDMosmixData(
        station_ids=["01001", "01008"],
        period_type=DWDFcstPeriodType.FORECAST_LONG
    )
    response = mosmix.collect_data()

    print(response.metadata)
    print(response.forecast)

MOSMIX-L - more parameters:
.. code-block:: python
    mosmix = DWDMosmixData(
        station_ids=["01001", "01008"],
        period_type=DWDFcstPeriodType.FORECAST_LONG
    )
    response = mosmix.collect_data()

    print(response.metadata)
    print(response.forecast)


*****
RADAR
*****

To use ``DWDRadarRequest``, you have to provide a ``RadarParameter``,
which designates the type of radar data you want to obtain. There is
radar data available at different locations within the DWD data repository:

- https://opendata.dwd.de/weather/radar/composit/
- https://opendata.dwd.de/weather/radar/radolan/
- https://opendata.dwd.de/weather/radar/radvor/
- https://opendata.dwd.de/weather/radar/sites/
- https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
- https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
- https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/

For ``RADOLAN_CDC``-data, the time resolution parameter (either hourly or daily)
must be specified.

The ``date_times`` (list of datetimes or strings) or a ``start_date``
and ``end_date`` parameters can optionally be specified to obtain data
from specific points in time.

For ``RADOLAN_CDC``-data, datetimes are rounded to ``HH:50min``, as the
data is packaged for this minute step.

This is an example on how to acquire ``RADOLAN_CDC`` data using
``wetterdienst`` and process it using ``wradlib``.

For more examples, please have a look at `example/radar/`_.

.. code-block:: python

    from wetterdienst import DWDRadarRequest, RadarParameter, TimeResolution
    import wradlib as wrl

    radar = DWDRadarRequest(
        radar_parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=TimeResolution.DAILY,
        start_date="2020-09-04T12:00:00",
        end_date="2020-09-04T12:00:00"
    )

    for item in radar.collect_data():

        # Decode item.
        timestamp, buffer = item

        # Decode data using wradlib.
        data, attributes = wrl.io.read_radolan_composite(buffer)

        # Do something with the data (numpy.ndarray) here.


.. _wradlib: https://wradlib.org/
.. _example/radar/: https://github.com/earthobservations/wetterdienst/tree/master/example/radar

.. _SQLite: https://www.sqlite.org/
.. _DuckDB: https://duckdb.org/docs/sql/introduction
.. _DuckDB SQL introduction: https://duckdb.org/docs/sql/introduction
.. _InfluxDB: https://github.com/influxdata/influxdb
.. _CrateDB: https://github.com/crate/crate
