.. wetterdienst-api:

##########
Python API
##########

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

.. _example: https://github.com/earthobservations/wetterdienst/tree/main/example

Available APIs
==============

The available APIs can be accessed by the top-level API Wetterdienst. This API also
allows the user to discover the available APIs of each service included:

.. ipython:: python

    from wetterdienst import Wetterdienst

    Wetterdienst.discover()

To load any of the available APIs pass the provider and the network of data to the
Wetterdienst API:

.. ipython:: python

    from wetterdienst import Wetterdienst

    API = Wetterdienst(provider="dwd", network="observation")

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

This leaves a lot of flexibility to the user defining the arguments either by what they
know from the weather service or what they know from `wetterdienst` itself.

Typical requests are defined by five arguments:

- ``parameter``
- ``resolution``
- ``period``
- ``start_date``
- ``end_date``

Only the parameter, start_date and end_date argument may be needed for a request, as the resolution and period of
the data may be fixed (per station or for all data) within individual services. However if
the period is not defined, it is assumed that the user wants data for all available
periods and the request then is handled that way.

Arguments start_date and end_date are possible replacements for the period argument if
the period of a weather service is fixed. In case both arguments are given they are
combined thus data is only taken from the given period and between the given time span.

Enumerations for resolution and period arguments are given at the main level e.g.

.. ipython:: python

    from wetterdienst import Resolution, Period

or at the domain specific level e.g.

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationResolution, DwdObservationPeriod

Both enumerations can be used interchangeably however the weather services enumeration
is limited to what resolutions and periods are actually available while the main level
enumeration is a summation of all kinds of resolutions and periods found at the
different weather services.

When it comes to values one can either query all data by ``request.all()`` or typically
query by ``station_id`` via ``request.filter_by_station_id()``. Alternatively the API offers
various possibilities to query stations by geographic context. Further details can be found below.

Core settings
=============

Wetterdienst holds core settings in its Settings class. You can import and show the Settings like

.. ipython:: python

    from wetterdienst import Settings

    print(Settings)

or modify them for your very own request like

.. ipython:: python

    from wetterdienst import Settings

    Settings.tidy = False

Settings has three layers of which those arguments are sourced:
- environmental variables
(- a local .env file in the same folder, mainly for testing purposes)
- Python code, which reevaluates those arguments like seen above

To make sure that non of your environmental variables are used, call to set our default values

.. ipython:: python

    from wetterdienst import Settings
    Settings.default()

and to set it back to standard

.. ipython:: python

    from wetterdienst import Settings
    Settings.reset()

The environmental settings recognized by our settings are

.. ipython:: python

    import json
    from wetterdienst import Settings
    print(json.dumps(Settings.env.dump(), indent=4))

Also if for whatever reason you have concurrent code running and want it all to have thread-safe settings use it like

.. ipython:: python

    from wetterdienst import Settings
    with Settings:
        Settings.tidy = False
        # request = DwdObservationRequest() <- with tidy = False

Scalar arguments are:
- `tidy` can be used to reshape the returned data to a `tidy format`_.
- `humanize` can be used to rename parameters to more meaningful
names.
- `si_units` can be used to convert values to SI units.

All of `tidy`, `humanize` and `si_units` are defaulted to True.

.. _tidy format: https://vita.had.co.nz/papers/tidy-data.pdf

Historical Weather Observations
===============================

In case of the DWD requests have to be defined by resolution and period (respectively
``start_date`` and ``end_date``). Use ``DwdObservationRequest.discover()``
to discover available parameters based on the given filter arguments.

Stations
--------

Get station information for a given *parameter/dataset*, *resolution* and
*period*.

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    ).all()

    df = stations.df

    print(df.head())

The function returns a Pandas DataFrame with information about the available stations.

Filter for specific station ids:

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    ).filter_by_station_id(station_id=("01048", ))

    df = stations.df

    print(df.head())

Filter for specific station name:

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    ).filter_by_name(name="Dresden-Klotzsche")

    df = stations.df

    print(df.head())

Values
------

Use the ``DwdObservationRequest`` class in order to get hold of stations.

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution
    from wetterdienst import Settings

    Settings.tidy = True
    Settings.humanize = True
    Settings.si_units = True

    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY, DwdObservationDataset.SOLAR],
        resolution=DwdObservationResolution.DAILY,
        start_date="1990-01-01",
        end_date="2020-01-01",
    ).filter_by_station_id(station_id=[3, 1048])

From here you can query data by station:

.. ipython:: python

    for result in request.values.query():
        # analyse the station here
        print(result.df.dropna().head())

Query data all together:

.. ipython:: python

    df = request.values.all().df.dropna()
    print(df.head())

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names. Instead of
``start_date`` and ``end_date`` you may as well want to use ``period`` to update your
database once in a while with a fixed set of records.

Geospatial support
------------------

Inquire the list of stations by geographic coordinates.

- Calculate weather stations close to the given coordinates and set of parameters.
- Select stations by
    - rank (n stations)
    - distance (km, mi,...)
    - bbox

Distance with default (kilometers)

.. ipython:: python

    from datetime import datetime
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
    )

    df = stations.filter_by_distance(
        latitude=50.0,
        longitude=8.9,
        distance=30,
        unit="km"
    ).df

    print(df.head())

Distance with miles

.. ipython:: python

    from datetime import datetime
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
    )

    df = stations.filter_by_distance(
        latitude=50.0,
        longitude=8.9,
        distance=30,
        unit="mi"
    ).df

    print(df.head())

Rank selection

.. ipython:: python

    from datetime import datetime
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
    )

    df = stations.filter_by_rank(
        latitude=50.0,
        longitude=8.9,
        rank=5
    ).df

    print(df.head())

Bbox selection

.. ipython:: python

    from datetime import datetime
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
    )

    df = stations.filter_by_bbox(
        left=8.9,
        bottom=50.0,
        right=8.91,
        top=50.01,
    ).df

    print(df.head())


The function returns a StationsResult with the list of stations being filtered for
distances [in km] to the given coordinates.

Again from here we can jump to the corresponding data:

.. ipython:: python

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
    ).filter_by_distance(
        latitude=50.0,
        longitude=8.9,
        distance=30
    )

    for result in stations.values.query():
        # analyse the station here
        print(result.df.dropna().head())

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments.


SQL support
-----------

Querying data using SQL is provided by an in-memory DuckDB_ database.
In order to explore what is possible, please have a look at the `DuckDB SQL introduction`_.

The result data is provided through a virtual table called ``data``.

.. code-block:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution
    from wetterdienst import Settings

    Settings.tidy = True
    Settings.humanize = True
    Settings.si_units = True

    stations = DwdObservationRequest(
        parameter=[DwdObservationDataset.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
    ).filter_by_station_id(station_id=[1048])

    results = stations.values.all()
    df = results.filter_by_sql("SELECT * FROM data WHERE parameter='temperature_air_200' AND value < -7.0;")
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

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset,
        DwdObservationPeriod, DwdObservationResolution
    from wetterdienst import Settings

    Settings.tidy = True
    Settings.humanize = True
    Settings.si_units = True

    stations = DwdObservationRequest(
        parameter=[DwdObservationDataset.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
    ).filter_by_station_id(station_id=[1048])

    results = stations.values.all()
    results.to_target("influxdb://localhost/?database=dwd&table=weather")

Mosmix
======

Get stations for Mosmix:

.. ipython:: python

    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

    stations = DwdMosmixRequest(
        parameter="large",
        mosmix_type="large"
    )  # actually same for small and large

    print(stations.all().df.head())

Mosmix forecasts require us to define ``station_ids`` and ``mosmix_type``. Furthermore
we can also define explicitly the requested parameters.

Get Mosmix-L data:

.. ipython:: python

    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType

    stations = DwdMosmixRequest(
        parameter="large",
        mosmix_type=DwdMosmixType.LARGE
    ).filter_by_station_id(station_id=["01001", "01008"])
    response =  next(stations.values.query())

    print(response.stations.df)
    print(response.df)

Radar
=====

Sites
-----

Retrieve information about all OPERA radar sites.

.. ipython:: python

    from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites

    # Acquire information for all OPERA sites.
    sites = OperaRadarSites().all()
    print(f"Number of OPERA radar sites: {len(sites)}")

    # Acquire information for a specific OPERA site.
    site_ukdea = OperaRadarSites().by_odimcode("ukdea")
    print(site_ukdea)

Retrieve information about the DWD radar sites.

.. ipython:: python

    from wetterdienst.provider.dwd.radar.api import DwdRadarSites

    # Acquire information for a specific site.
    site_asb = DwdRadarSites().by_odimcode("ASB")
    print(site_asb)


Data
----

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

    from wetterdienst.provider.dwd.radar import DwdRadarValues, DwdRadarParameter, DwdRadarResolution
    import wradlib as wrl

    radar = DwdRadarValues(
        radar_parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        start_date="2020-09-04T12:00:00",
        end_date="2020-09-04T12:00:00"
    )

    for item in radar.query():

        # Decode item.
        timestamp, buffer = item

        # Decode data using wradlib.
        data, attributes = wrl.io.read_radolan_composite(buffer)

        # Do something with the data (numpy.ndarray) here.

Caching
=======

The backbone of wetterdienst uses dogpile + fsspec caching. It requires to create a directory under ``/home`` for the
most cases. If you are not allowed to write into ``/home`` you will run into ``OSError``. For this purpose you can set
an environment variable ``WD_CACHE_DIR`` to define the place where the caching directory should be created.

FSSPEC is used for flexible file caching. It relies on the two libraries requests and aiohttp. Aiohttp is used for
asynchronous requests and may swallow some errors related to proxies, ssl or similar. Use the defined variable
FSSPEC_CLIENT_KWARGS to pass your very own client kwargs to fsspec e.g.

.. ipython:: python

    from wetterdienst.util.cache import FSSPEC_CLIENT_KWARGS

    FSSPEC_CLIENT_KWARGS["trust_env"] = True  # use proxy from environment variables


.. _wradlib: https://wradlib.org/
.. _example/radar/: https://github.com/earthobservations/wetterdienst/tree/main/example/radar

.. _SQLite: https://www.sqlite.org/
.. _DuckDB: https://duckdb.org/docs/sql/introduction
.. _DuckDB SQL introduction: https://duckdb.org/docs/sql/introduction
.. _InfluxDB: https://github.com/influxdata/influxdb
.. _CrateDB: https://github.com/crate/crate
