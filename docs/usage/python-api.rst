.. wetterdienst-api:

Python API
##########

Introduction
************

The API offers access to different data products. They are
outlined in more detail within the :ref:`coverage` chapter.
Please also check out complete examples about how to use the API in the example_ folder.
In order to explore all features interactively,
you might want to try the :ref:`cli`.

.. _example: https://github.com/earthobservations/wetterdienst/tree/main/example

Available APIs
**************

The available APIs can be accessed by the top-level API Wetterdienst. This API also
allows the user to discover the available APIs of each service included:

.. ipython:: python
    :okwarning:

    from wetterdienst import Wetterdienst

    Wetterdienst.discover()

To load any of the available APIs pass the provider and the network of data to the
Wetterdienst API:

.. ipython:: python
    :okwarning:

    from wetterdienst import Wetterdienst

    API = Wetterdienst(provider="dwd", network="observation")

Request arguments
*****************

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
    :okwarning:

    from wetterdienst import Resolution, Period

or at the domain specific level e.g.

.. ipython:: python
    :okwarning:

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
  all datasets e.g. when two datasets contain the somehwat similar parameter we do a pre-selection of the dataset from
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
        parameter=[("precipitation_height", "more_precip"), ("temperature_air_mean_200", "kl")]
    )

Core settings
=============

Wetterdienst holds core settings in its Settings class. You can import and show the Settings like

.. ipython:: python
    :okwarning:

    from wetterdienst import Settings

    settings = Settings.default()  # default settings
    print(settings)

or modify them for your very own request like

.. ipython:: python
    :okwarning:

    from wetterdienst import Settings

    settings = Settings(tidy=False)
    print(settings)

Settings has four layers of which those arguments are sourced:
- Settings arguments e.g. Settings(tidy=True)
- environment variables e.g. WD_SCALAR_TIDY = "0"
- local .env file in the same folder (same as above)
- default arguments set by us

The arguments are overruled in the above order meaning:
- Settings argument overrules environmental variable
- environment variable overrules .env file
- .env file overrules default argument

The evaluation of environment variables can be skipped by using `ignore_env`:

.. ipython:: python
    :okwarning:

    from wetterdienst import Settings
    Settings.default()  # similar to Settings(ignore_env=True)

and to set it back to standard

.. ipython:: python
    :okwarning:

    from wetterdienst import Settings

    settings = Settings(tidy=False)
    settings = settings.reset()

The environmental settings recognized by our settings are

- WD_CACHE_DISABLE
- WD_FSSPEC_CLIENT_KWARGS
- WD_SCALAR_HUMANIZE
- WD_SCALAR_TIDY
- WD_SCALAR_SI_UNITS
- WD_SCALAR_SKIP_EMPTY
- WD_SCALAR_SKIP_THRESHOLD
- WD_SCALAR_SKIP_CRITERIA
- WD_SCALAR_DROPNA
- WD_SCALAR_INTERPOLATION_USE_NEARBY_STATION_UNTIL_KM

Scalar arguments are:
- `tidy` can be used to reshape the returned data to a `tidy format`_.
- `humanize` can be used to rename parameters to more meaningful
names.
- `si_units` can be used to convert values to SI units.
- `skip_empty` (requires option `tidy`) can be used to skip empty stations
    - empty stations are defined via `skip_threshold` which defaults to 0.95
     and requires all parameters that are requested (for an entire dataset all of the dataset parameters)
     to have at least 95 per cent of actual values (relative to start and end date if provided)
- `skip_criteria` (requires option `tidy`) is the statistical criteria on which the percentage of actual values is
    calculated with options "min", "mean", "max", where "min" means the percentage of the lowest available parameter is
    taken, while "mean" takes the average percentage of all parameters and "max" does so for the parameter with the most
    percentage
- `skip_threshold` is used in combination with `skip_empty` to define when a station is empty, with 1.0 meaning no
 values per parameter should be missing and e.g. 0.9 meaning 10 per cent of values can be missing
- `dropna` (requires option `tidy`) is used to drop all empty entries thus reducing the workload
- `fsspec_client_kwargs` can be used to pass arguments to fsspec, especially for querying data behind a proxy

All of `tidy`, `humanize` and `si_units` are defaulted to True.

If your system is running behind a proxy e.g. like `here <https://github.com/earthobservations/wetterdienst/issues/524>`_
you may want to use the `trust_env` like

```python
    from wetterdienst import Settings
    settings = Settings(fsspec_client_kwargs={"trust_env": True})
```

to allow requesting through a proxy.

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
    :okwarning:

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
    :okwarning:

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
    :okwarning:

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
    :okwarning:

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution
    from wetterdienst import Settings

    settings = Settings(tidy=True, humanize=True, si_units=True)

    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY, DwdObservationDataset.SOLAR],
        resolution=DwdObservationResolution.DAILY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        settings=settings
    ).filter_by_station_id(station_id=[3, 1048])

From here you can query data by station:

.. ipython:: python
    :okwarning:

    for result in request.values.query():
        # analyse the station here
        print(result.df.dropna().head())

Query data all together:

.. ipython:: python
    :okwarning:

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
    :okwarning:

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
        latlon=(50.0, 8.9),
        distance=30,
        unit="km"
    ).df

    print(df.head())

Distance with miles

.. ipython:: python
    :okwarning:

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
        latlon=(50.0, 8.9),
        distance=30,
        unit="mi"
    ).df

    print(df.head())

Rank selection

.. ipython:: python
    :okwarning:

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
        latlon=(50.0, 8.9),
        rank=5
    ).df

    print(df.head())

Rank selection skip empty stations

This will skip empty stations according to some settings. See the finally collected stations via the
`df_stations` property on the values result.

.. ipython:: python
    :okwarning:

    from datetime import datetime
    from wetterdienst import Settings
    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution

    settings = Settings(skip_empty=True, ignore_env=True, skip_criteria="min")

    stations = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY, DwdObservationDataset.SOLAR],
        resolution=DwdObservationResolution.DAILY,
        start_date="2021-01-01",
        end_date="2021-12-31",
        settings=settings,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=2)

    values = stations.values.all()

    print(values.df.head())
    print(values.df_stations.head())


Bbox selection

.. ipython:: python
    :okwarning:

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
    :okwarning:

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
    ).filter_by_distance(
        latlon=(50.0, 8.9),
        distance=30
    )

    for result in stations.values.query():
        # analyse the station here
        print(result.df.dropna().head())

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments.

Interpolation
-------------

Sometimes you might need data for your exact position instead of values measured at the location of a station.
Therefore, we added the interpolation feature which allows you to interpolate weather data of stations around you to your exact location.
The function uses the four nearest stations to your given lat/lon point and interpolates the given parameter values.
It uses the bilinear interpolation method from the scipy package (interp2d).
The interpolation currently only works for DWDObservationRequest and individual parameters.
It is still in an early phase and will be improved based on feedback.


The graphic below shows values of the parameter ``temperature_air_mean_200`` from multiple stations measured at the same time.
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
     - temperature_air_mean_200
     - 2022-01-02 00:00:00+00:00
     - 278.15
   * - 04411
     - temperature_air_mean_200
     - 2022-01-02 00:00:00+00:00
     - 277.15
   * - 07341
     - temperature_air_mean_200
     - 2022-01-02 00:00:00+00:00
     - 278.35
   * - 00917
     - temperature_air_mean_200
     - 2022-01-02 00:00:00+00:00
     - 276.25

The interpolated value looks like this:

.. list-table:: Interpolated value
   :header-rows: 1

   * - parameter
     - date
     - value
   * - temperature_air_mean_200
     - 2022-01-02 00:00:00+00:00
     - 277.65

The code to execute the interpolation is given below. It currently only works for ``DwdObservationRequest`` and individual parameters.
Currently the following parameters are supported (more will be added if useful): ``temperature_air_mean_200``, ``wind_speed``, ``precipitation_height``.

.. ipython:: python
    :okwarning:

    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=Resolution.HOURLY,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.interpolate(latlon=(50.0, 8.9))
    df = result.df
    print(df.head())

Instead of a latlon you may alternatively use an existing station id for which to interpolate values in a manner of
getting a more complete dataset:

.. ipython:: python
    :okwarning:

    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=Resolution.HOURLY,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.interpolate_by_station_id(station_id="02480")
    df = result.df
    print(df.head())


Summary
-------

Similar to interpolation you may sometimes want to combine multiple stations to get a complete list of data. For that
reason you can use `.summary(lat, lon)`, which goes through nearest stations and combines data from them meaningful.

The code to execute the summary is given below. It currently only works for ``DwdObservationRequest`` and individual parameters.
Currently the following parameters are supported (more will be added if useful): ``temperature_air_mean_200``, ``wind_speed``, ``precipitation_height``.

.. ipython:: python
    :okwarning:

    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=Resolution.HOURLY,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.summarize(latlon=(50.0, 8.9))
    df = result.df
    print(df.head())

Instead of a latlon you may alternatively use an existing station id for which to summarize values in a manner of
getting a more complete dataset:

.. ipython:: python
    :okwarning:

    from wetterdienst.provider.dwd.observation import DwdObservationRequest
    from wetterdienst import Parameter, Resolution

    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=Resolution.HOURLY,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.summarize_by_station_id(station_id="02480")
    df = result.df
    print(df.head())

SQL support
-----------

Querying data using SQL is provided by an in-memory DuckDB_ database.
In order to explore what is possible, please have a look at the `DuckDB SQL introduction`_.

The result data is provided through a virtual table called ``data``.

.. code-block:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationDataset, DwdObservationPeriod, DwdObservationResolution
    from wetterdienst import Settings

    settings = Settings(tidy=True, humanize=True, si_units=True)  # defaults

    stations = DwdObservationRequest(
        parameter=[DwdObservationDataset.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings
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

    settings = Settings(tidy=True, humanize=True, si_units=True)  # defaults

    stations = DwdObservationRequest(
        parameter=[DwdObservationDataset.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings
    ).filter_by_station_id(station_id=[1048])

    results = stations.values.all()
    results.to_target("influxdb://localhost/?database=dwd&table=weather")

Mosmix
======

Get stations for Mosmix:

.. ipython:: python
    :okwarning:

    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

    stations = DwdMosmixRequest(
        parameter="large",
        mosmix_type="large"
    )  # actually same for small and large

    print(stations.all().df.head())

Mosmix forecasts require us to define ``station_ids`` and ``mosmix_type``. Furthermore
we can also define explicitly the requested parameters.

Get Mosmix-L data (single station file):

.. ipython:: python
    :okwarning:

    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType

    stations = DwdMosmixRequest(
        parameter="large",
        mosmix_type=DwdMosmixType.LARGE
    ).filter_by_station_id(station_id=["01001", "01008"])
    response =  next(stations.values.query())

    print(response.stations.df)
    print(response.df)

Get Mosmix-L data (all stations file):

.. ipython:: python
    :okwarning:

    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType

    stations = DwdMosmixRequest(
        parameter="large",
        mosmix_type=DwdMosmixType.LARGE,
        station_group="all_stations"
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
    :okwarning:

    from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites

    # Acquire information for all OPERA sites.
    sites = OperaRadarSites().all()
    print(f"Number of OPERA radar sites: {len(sites)}")

    # Acquire information for a specific OPERA site.
    site_ukdea = OperaRadarSites().by_odimcode("ukdea")
    print(site_ukdea)

Retrieve information about the DWD radar sites.

.. ipython:: python
    :okwarning:

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

The backbone of wetterdienst uses fsspec caching. It requires to create a directory under ``/home`` for the
most cases. If you are not allowed to write into ``/home`` you will run into ``OSError``. For this purpose you can set
an environment variable ``WD_CACHE_DIR`` to define the place where the caching directory should be created.

FSSPEC is used for flexible file caching. It relies on the two libraries requests and aiohttp. Aiohttp is used for
asynchronous requests and may swallow some errors related to proxies, ssl or similar. Use the defined variable
FSSPEC_CLIENT_KWARGS to pass your very own client kwargs to fsspec e.g.

.. ipython:: python
    :okwarning:

    from wetterdienst import Settings

    settings = Settings(fsspec_client_kwargs={"trust_env": True})  # use proxy from environment variables


.. _wradlib: https://wradlib.org/
.. _example/radar/: https://github.com/earthobservations/wetterdienst/tree/main/example/radar

.. _SQLite: https://www.sqlite.org/
.. _DuckDB: https://duckdb.org/docs/sql/introduction
.. _DuckDB SQL introduction: https://duckdb.org/docs/sql/introduction
.. _InfluxDB: https://github.com/influxdata/influxdb
.. _CrateDB: https://github.com/crate/crate
