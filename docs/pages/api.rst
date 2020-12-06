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

    from wetterdienst.dwd.observations import DWDObservationStations, DWDObservationParameterSet, DWDObservationPeriod, DWDObservationResolution

    stations = DWDObservationStations(
        parameter_set=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    df = stations.all()

    df.head()

The function returns a Pandas DataFrame with information about the available stations.
The column ``HAS_FILE`` indicates whether the station actually has a file with data on
the server. That might not always be the case for stations which have been phased out.


Measurements
============
Use the ``DWDObservationData`` class in order to get hold of measurement information.

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationData, DWDObservationParameterSet, DWDObservationPeriod, DWDObservationResolution

    observations = DWDObservationData(
        station_ids=[3, 1048],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY, DWDObservationParameterSet.SOLAR],
        resolution=DWDObservationResolution.DAILY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
    )

    for df in observations.collect_data():
        # analyse the station here
        df.data.head()

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names and stored
automatically on the drive if wanted. Instead of ``start_date`` and ``end_date`` you may
as well want to use periods to update your database once in a while with a fixed set of
records. You can also define start_date and end_date in order to reduce the amount of
data loaded for a request. Just make sure that you are really meeting the date range with
the specified periods.


Geospatial support
==================

Inquire the list of stations by geographic coordinates.

- Calculate weather stations close to the given coordinates and set of parameters.
- Either select by rank (n stations) or by distance in km.

.. ipython:: python

    from datetime import datetime
    from wetterdienst.dwd.observations import DWDObservationStations, DWDObservationParameterSet, DWDObservationPeriod, DWDObservationResolution

    stations = DWDObservationStations(
        parameter_set=DWDObservationParameterSet.TEMPERATURE_AIR,
        resolution=DWDObservationResolution.HOURLY,
        period=DWDObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
    )

    df = stations.nearby_radius(
        latitude=50.0,
        longitude=8.9,
        max_distance_in_km=30
    )

    df.head()

The function returns a DataFrame with the list of stations with distances [in km]
to the given coordinates.

The station ids within the DataFrame:

.. ipython:: python

    station_ids = df.STATION_ID.unique()

can be used to download the observation data:

.. ipython:: python

    observations = DWDObservationData(
        station_ids=station_ids,
        parameters=[DWDObservationParameterSet.TEMPERATURE_AIR, DWDObservationParameterSet.SOLAR],
        resolution=DWDObservationResolution.HOURLY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
    )

    for df in observations.collect_data():
        # analyse the station here
        df.data.head()

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments.


SQL support
===========
Querying data using SQL is provided by an in-memory DuckDB_ database.
In order to explore what is possible, please have a look at the `DuckDB SQL introduction`_.

The result data is provided through a virtual table called ``data``.

.. code-block:: python

    from wetterdienst.dwd.observations import DWDObservationData, DWDObservationParameterSet, DWDObservationPeriod, DWDObservationResolution

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=[DWDObservationParameterSet.TEMPERATURE_AIR],
        resolution=DWDObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
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

    from wetterdienst.dwd.observations import DWDObservationData, DWDObservationParameterSet,
        DWDObservationPeriod, DWDObservationResolution, StorageAdapter

    storage = StorageAdapter(persist=True, folder="/path/to/dwd-archive")

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=[DWDObservationParameterSet.TEMPERATURE_AIR],
        resolution=DWDObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
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

    from wetterdienst.dwd.observations import DWDObservationData, DWDObservationParameterSet,
        DWDObservationPeriod, DWDObservationResolution, StorageAdapter

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=[DWDObservationParameterSet.TEMPERATURE_AIR],
        resolution=DWDObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
    )

    df = observations.collect_safe().dwd.lower()
    df.io.export("influxdb://localhost/?database=dwd&table=weather")


******
MOSMIX
******
MOSMIX-S - less parameters:

.. code-block:: python

    from wetterdienst.dwd.forecasts import DWDMosmixData, DWDMosmixType

    mosmix = DWDMosmixData(
        station_ids=["01001", "01008"],
        mosmix_type=DWDMosmixType.LARGE
    )
    response = mosmix.collect_data()

    print(response.metadata)
    print(response.data)

MOSMIX-L - more parameters:

.. code-block:: python

    mosmix = DWDMosmixData(
        station_ids=["01001", "01008"],
        mosmix_type=DWDMosmixType.LARGE
    )
    response = mosmix.collect_data()

    print(response.metadata)
    print(response.data)


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

    from wetterdienst.dwd.radar import DWDRadarData, DWDRadarParameter, DWDRadarResolution
    import wradlib as wrl

    radar = DWDRadarData(
        radar_parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.DAILY,
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
