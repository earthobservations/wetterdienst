.. python-api:

Python API
##########

Introduction
************

The API offers access to different data products. They are outlined in more detail within the :ref:`coverage` chapter.
Please also check out complete examples about how to use the API in the examples_ folder. In order to explore all
features interactively, you might want to try the :ref:`cli`. For managing general settings, please refer to the
:ref:`settings` chapter.

.. _examples: https://github.com/earthobservations/wetterdienst/tree/main/examples

Available APIs
**************

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
*****************

Some of the `wetterdienst` request arguments e.g. ``parameter``, ``resolution``, ``period`` are based on enumerations.
This allows the user to define them in three different ways:

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

Regarding the definition of requested parameters:

Parameters can be requested in three different ways:

1. Requesting an entire dataset e.g. climate_summary

.. code-block:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter="kl"
    )


2. Requesting one parameter of a specific resolution without defining the exact dataset.

  For each offered resolution we have created a list of unique parameters which are drafted from the entire space of
  all datasets e.g. when two datasets contain the somewhat similar parameter we do a pre-selection of the dataset from
  which the parameter is taken.

.. code-block:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter="precipitation_height"
    )

3. Request a parameter-dataset tuple

   This gives you entire freedom to request a unique parameter-dataset tuple just as you wish.

.. code-block:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter=[("precipitation_height", "more_precip"), ("temperature_air_mean_2m", "kl")]
    )

Data
****

In case of the DWD, requests have to be defined by resolution and period (respectively
``start_date`` and ``end_date``). Use ``DwdObservationRequest.discover()``
to discover available parameters based on the given filter arguments.

Stations
========

all stations
------------

Get station information for a given *parameter/dataset*, *resolution* and
*period*.

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    )
    stations = request.all()
    df = stations.df
    print(df.head())

The function returns a Polars DataFrame with information about the available stations.

filter by station id
--------------------

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    )
    stations = request.filter_by_station_id(station_id=("01048", ))
    df = stations.df
    print(df.head())

filter by name
--------------

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    )
    stations = request.filter_by_name(name="Dresden-Klotzsche")
    df = stations.df
    print(df.head())

filter by distance
------------------

Distance in kilometers (default)

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    hamburg = (53.551086, 9.993682)
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2020, 1, 20)
    )
    stations = request.filter_by_distance(latlon=hamburg, distance=30, unit="km")
    df = stations.df
    print(df.head())

Distance in miles

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    hamburg = (53.551086, 9.993682)
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2020, 1, 20)
    )
    stations = request.filter_by_distance(latlon=hamburg, distance=30, unit="mi")
    df = stations.df
    print(df.head())

filter by rank
--------------

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    hamburg = (53.551086, 9.993682)
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2020, 1, 20)
    )
    stations = request.filter_by_rank(latlon=hamburg, rank=5)
    df = stations.df
    print(df.head())

filter by bbox
--------------

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    bbox = (8.9, 50.0, 8.91, 50.01)
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2020, 1, 20)
    )
    stations = request.filter_by_bbox(*bbox)
    df = stations.df
    print(df.head())

Values
======

Values are just an extension of requests:

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Settings

    # if no settings are provided, default settings are used which are
    # Settings(ts_shape="long", ts_humanize=True, ts_si_units=True)
    request = DwdObservationRequest(
        parameter=["kl", "solar"],
        resolution="daily",
        start_date="1990-01-01",
        end_date="2020-01-01",
    )
    stations = request.filter_by_station_id(station_id=("00003", "01048"))

From here you can query data by station:

.. ipython:: python

    for result in stations.values.query():
        # analyse the station here
        print(result.df.drop_nulls().head())

Query data all together:

.. ipython:: python

    df = stations.values.all().df.drop_nulls()
    print(df.head())

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names. Instead of
``start_date`` and ``end_date`` you may as well want to use ``period`` to update your
database once in a while with a fixed set of records.

In case you use `filter_by_rank` you may want to skip empty stations. We can use the Settings from :ref:`settings` to
achieve that:

.. ipython:: python

    from wetterdienst import Settings
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    settings = Settings(ts_skip_empty=True, ts_skip_criteria="min", ignore_env=True)
    karlsruhe = (49.19780976647141, 8.135207205143768)
    request = DwdObservationRequest(
        parameter=["kl", "solar"],
        resolution="daily",
        start_date="2021-01-01",
        end_date="2021-12-31",
        settings=settings,
    )
    stations = request.filter_by_rank(latlon=karlsruhe, rank=2)
    values = stations.values.all()
    print(values.df.head())
    # df_stations has only stations that appear in the values
    print(values.df_stations.head())

Interpolation
=============

Occasionally, you may require data specific to your precise location rather than relying on values measured at a
station's location. To address this need, we have introduced an interpolation feature, enabling you to interpolate data
from nearby stations to your exact coordinates. The function leverages the four closest stations to your specified
latitude and longitude and employs the bilinear interpolation method provided by the scipy package (interp2d) to
interpolate the given parameter values. Currently, this interpolation feature is exclusive to
`DWDObservationRequest` and parameters ``temperature_air_mean_2m``, ``wind_speed``, ``precipitation_height``.
As it is in its early stages, we welcome feedback to enhance and refine its functionality. Interpolation by nearby
stations is limited to a distance of 40 km by default (20.0 km for precipitation). You can
change this by setting the ``ts_interpolation_station_distance`` setting. An example is shown below.

The graphic below shows values of the parameter ``temperature_air_mean_2m`` from multiple stations measured at the same time.
The blue points represent the position of a station and includes the measured value.
The red point represents the position of the interpolation and includes the interpolated value.

.. image:: docs/img/interpolation.png
   :width: 600

Values represented as a table:

.. list-table:: Individual station values
   :header-rows: 1

   * - station_id
     - parameter
     - date
     - value
   * - 02480
     - temperature_air_mean_2m
     - 2022-01-02 00:00:00+00:00
     - 278.15
   * - 04411
     - temperature_air_mean_2m
     - 2022-01-02 00:00:00+00:00
     - 277.15
   * - 07341
     - temperature_air_mean_2m
     - 2022-01-02 00:00:00+00:00
     - 278.35
   * - 00917
     - temperature_air_mean_2m
     - 2022-01-02 00:00:00+00:00
     - 276.25

The interpolated value looks like this:

.. list-table:: Interpolated value
   :header-rows: 1

   * - parameter
     - date
     - value
   * - temperature_air_mean_2m
     - 2022-01-02 00:00:00+00:00
     - 277.65


.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    request = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_2M,
        resolution=Resolution.HOURLY,
        start_date=dt.datetime(2022, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
    )
    values = request.interpolate(latlon=(50.0, 8.9))
    df = values.df
    print(df.head())

Instead of a latlon you may alternatively use an existing station id for which to interpolate values in a manner of
getting a more complete dataset:

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    request = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_2M,
        resolution=Resolution.HOURLY,
        start_date=dt.datetime(2022, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
    )
    values = request.interpolate_by_station_id(station_id="02480")
    df = values.df
    print(df.head())

Increase maximum distance for interpolation:

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution, Settings

    settings = Settings(ts_interpolation_station_distance={"precipitation_height": 25.0})
    request = DwdObservationRequest(
        parameter=Parameter.PRECIPITATION_HEIGHT,
        resolution=Resolution.HOURLY,
        start_date=dt.datetime(2022, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=settings
    )
    values = request.interpolate(latlon=(52.8, 12.9))
    df = values.df
    print(df.head())


Summary
=======

Similar to interpolation you may sometimes want to combine multiple stations to get a complete list of data. For that
reason you can use `.summary(latlon)`, which goes through nearest stations and combines data from them meaningful.

The code to execute the summary is given below. It currently only works for ``DwdObservationRequest`` and individual parameters.
Currently the following parameters are supported (more will be added if useful): ``temperature_air_mean_2m``, ``wind_speed``, ``precipitation_height``.

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    request = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_2M,
        resolution=Resolution.HOURLY,
        start_date=dt.datetime(2022, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
    )
    values = request.summarize(latlon=(50.0, 8.9))
    df = values.df
    print(df.head())

Instead of a latlon you may alternatively use an existing station id for which to summarize values in a manner of
getting a more complete dataset:

.. ipython:: python

    import datetime as dt
    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    request = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_2M,
        resolution=Resolution.HOURLY,
        start_date=dt.datetime(2022, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
    )
    values = request.summarize_by_station_id(station_id="02480")
    df = values.df
    print(df.head())

Format
******

To Dict
=======

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter="temperature_air_mean_2m",
        resolution="daily",
        start_date="2020-01-01",
        end_date="2020-01-02"
    )
    stations = request.filter_by_station_id(station_id="01048")
    values = stations.values.all()
    print(values.to_dict(with_metadata=True, with_stations=True))

To Json
=======

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter="temperature_air_mean_2m",
        resolution="daily",
        start_date="2020-01-01",
        end_date="2020-01-02"
    )
    stations = request.filter_by_station_id(station_id="01048")
    values = stations.values.all()
    print(values.to_json(with_metadata=True, with_stations=True))

To Ogc Feature Collection
=========================

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter="temperature_air_mean_2m",
        resolution="daily",
        start_date="2020-01-01",
        end_date="2020-01-02"
    )
    stations = request.filter_by_station_id(station_id="01048")
    values = stations.values.all()
    print(values.to_ogc_feature_collection(with_metadata=True))

To GeoJson
==========

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter="temperature_air_mean_2m",
        resolution="daily",
        start_date="2020-01-01",
        end_date="2020-01-02"
    )
    stations = request.filter_by_station_id(station_id="01048")
    values = stations.values.all()
    print(values.to_geojson(with_metadata=True))

To CSV
======

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    request = DwdObservationRequest(
        parameter="temperature_air_mean_2m",
        resolution="daily",
        start_date="2020-01-01",
        end_date="2020-01-02"
    )
    stations = request.filter_by_station_id(station_id="01048")
    values = stations.values.all()
    print(values.to_csv())


SQL
****

Querying data using SQL is provided by an in-memory DuckDB_ database.
In order to explore what is possible, please have a look at the `DuckDB SQL introduction`_.

The result data is provided through a virtual table called ``data``.

.. code-block:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution
    from wetterdienst import Settings

    settings = Settings(ts_shape="long", ts_humanize=True, ts_si_units=True)  # defaults
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings
    )
    stations = request.filter_by_station_id(station_id=[1048])
    values = stations.values.all()
    df = values.filter_by_sql("SELECT * FROM data WHERE parameter='temperature_air_2m' AND value < -7.0;")
    print(df.head())

Export
******

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

    settings = Settings(ts_shape="long", ts_humanize=True, ts_si_units=True)  # defaults
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings
    )
    stations = request.filter_by_station_id(station_id=[1048])
    values = stations.values.all()
    values.to_target("influxdb://localhost/?database=dwd&table=weather")

Caching
*******

The backbone of wetterdienst uses fsspec caching. It requires to create a directory under ``/home`` for the
most cases. If you are not allowed to write into ``/home`` you will run into ``OSError``. For this purpose you can set
an environment variable ``WD_CACHE_DIR`` to define the place where the caching directory should be created.

To find out where your cache is located you can use the following code:

.. ipython:: python

    from wetterdienst import Settings

    settings = Settings()
    print(settings.cache_dir)

Or similarly with the cli:

.. code-block:: bash

    wetterdienst cache

FSSPEC
******

FSSPEC is used for flexible file caching. It relies on the two libraries requests and aiohttp. Aiohttp is used for
asynchronous requests and may swallow some errors related to proxies, ssl or similar. Use the defined variable
FSSPEC_CLIENT_KWARGS to pass your very own client kwargs to fsspec e.g.

.. ipython:: python

    from wetterdienst import Settings
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    settings = Settings(fsspec_client_kwargs={"trust_env": True})  # use proxy from environment variables

    stations = DwdObservationRequest(
        parameter=[DwdObservationDataset.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        settings=settings
    ).filter_by_station_id(station_id=[1048])

.. _wradlib: https://wradlib.org/
.. _SQLite: https://www.sqlite.org/
.. _DuckDB: https://duckdb.org/docs/sql/introduction
.. _DuckDB SQL introduction: https://duckdb.org/docs/sql/introduction
.. _InfluxDB: https://github.com/influxdata/influxdb
.. _CrateDB: https://github.com/crate/crate
