.. wetterdienst-api:

API
***

.. contents::
    :local:
    :depth: 1


Introduction
============

The API offers access to different data products. They are
outlined in more detail within the :ref:`coverage` chapter.
Please also check out complete examples about how to use the API in the example_ folder.
In order to explore all features interactively,
you might want to try the :ref:`cli`.

.. _example: https://github.com/earthobservations/wetterdienst/tree/master/example

Request arguments
=================

Some of the `wetterdienst` request arguments e.g. ``parameter``, ``resolution``,
``period`` are based on enumerations. This allows the user to define them in three
different ways:

- by using the exact enumeration e.g.
    .. code-block:: python

        Parameter.CLIMATE_SUMMARY

- by using the enumeration name (our proposed name) e.g.
    .. code-block:: python

        "climate_summary" or "CLIMATE_SUMMARY"

- by using the enumeration value (most probably the original name) e.g.
    .. code-block:: python

        "kl"

This leaves a lot flexibility to the user defining the arguments either by what they
know from the weather service or what they know from `wetterdienst` itself.

Typical requests are defined by three arguments:

- ``parameter``
- ``resolution``
- ``period``

Only the parameter argument may be needed for a request, as the resolution and period of
the data may be fixed (per station or for all data) within individual services.
However for the case of the DWD a request requires all of them to be fined. However if
the period is not defined, it is assumed that the user wants data for all available
periods and the request then is handled that way.

Enumerations for resolution and period arguments are given at the main level e.g.

.. ipython:: python

    from wetterdienst import Resolution, Period

or at the domain specific level e.g.

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationResolution, DWDObservationPeriod

Both enumerations can be used interchangeably however the weather services enumeration
is limited to what resolutions and periods are actually available while the main level
enumeration is a summation of all kinds of resolutions and periods found at the
different weather services.

When it comes to values ``station_id`` also has to be defined to refer to an actual
existing station from which values are queried.

Other arguments for the request are

- ``start_date``
- ``end_date``
- ``tidy_data``
- ``humanize_parameters``

Arguments start_date and end_date are possible replacements for the period argument if
the period of a weather service is fixed. In case both arguments are given they are
combined thus data is only taken from the given period and between the given time span.
The argument tidy_data can be used to reshape the returned data to a `tidy format`_.
The argument humanize_parameters can be used to rename parameters to more meaningful
names. Both tidy_data and humanize_parameters are defaulted to True.

.. _tidy format: https://vita.had.co.nz/papers/tidy-data.pdf

Historical Weather Observations
===============================

In case of the DWD requests have to be defined by resolution and period (respectively
``start_date`` and ``end_date``). Use ``DWDObservationMetadata.discover_parameters()``
to discover available resolution, parameter, period combinations and their subsets
based on the obtained filter arguments.

Stations
--------

Get station information for a given *parameter/parameter_set*, *resolution* and
*period*.

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationStations, DWDObservationParameterSet, DWDObservationPeriod, DWDObservationResolution

    stations = DWDObservationStations(
        parameter_set=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    df = stations.all()

    print(df.head())

The function returns a Pandas DataFrame with information about the available stations.

Values
------

Use the ``DWDObservationData`` class in order to get hold of values.

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

Query data by station:

.. ipython:: python

    for result in observations.query():
        # analyse the station here
        print(result.data.dropna().head())

Query data all together:

.. ipython:: python

    df = observations.all().dropna()
    print(df.head())

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names. Instead of
``start_date`` and ``end_date`` you may as well want to use ``period`` to update your
database once in a while with a fixed set of records.

Geospatial support
------------------

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

    print(df.head())

    df = stations.nearby_number(
        latitude=50.0,
        longitude=8.9,
        number=5
    )

    print(df.head())


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

    for result in observations.query():
        # analyse the station here
        print(result.data.dropna().head())

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments.


SQL support
-----------

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

    df = observations.all().dwd.lower()
    df = df.io.sql("SELECT * FROM data WHERE parameter='temperature_air_200' AND value < -7.0;")
    print(df.head())

Data export
-----------

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

    df = observations.all().dwd.lower()
    df.io.export("influxdb://localhost/?database=dwd&table=weather")

Mosmix
======

Get stations for Mosmix:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixStations

    stations = DWDMosmixStations()

    print(stations.all().head())

Mosmix forecasts require us to define ``station_ids`` and ``mosmix_type``. Furthermore
we can also define explicitly the requested parameters.

Get Mosmix-L data:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixData, DWDMosmixType

    mosmix = DWDMosmixData(
        station_ids=["01001", "01008"],
        mosmix_type=DWDMosmixType.LARGE
    )
    response =  next(mosmix.query())

    print(response.metadata)
    print(response.data)

Radar
=====

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

    for item in radar.query():

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
