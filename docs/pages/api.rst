###
API
###
The API offers access to different data products. They are
outlined in more detail within the :ref:`data-coverage` chapter.

.. contents::
    :local:
    :depth: 1

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

Use ``wetterdienst.discover_climate_observations()`` to discover available
time resolution, parameter, period type combinations and their subsets
based on the obtained filter arguments.


Station list
============
Get station information for a given set of *parameter*, *time resolution*
and *period type* options.

.. code-block:: python

    import wetterdienst
    from wetterdienst import Parameter, PeriodType, TimeResolution

    metadata = wetterdienst.metadata_for_climate_observations(
        parameter=Parameter.PRECIPITATION_MORE,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

The function returns a Pandas DataFrame with information about the available stations.
The column ``HAS_FILE`` indicates whether the station actually has a file with data on
the server. That might not always be the case for stations which have been phased out.

When using ``create_new_file_index=True``, the function can be forced to retrieve
a new list of files from the server. Otherwise, data will be served from the
cache because this information rarely changes.

Measurements
============
Use the ``DWDStationRequest`` class in order to get hold of measurement information.

.. code-block:: python

    from wetterdienst import DWDStationRequest
    from wetterdienst import Parameter, PeriodType, TimeResolution

    request = DWDStationRequest(
        station_ids=[3, 1048],
        parameter=[Parameter.CLIMATE_SUMMARY, Parameter.SOLAR],
        time_resolution=TimeResolution.DAILY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
        write_file=True,
        prefer_local=True
    )

    for df in request.collect_data():
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
    from wetterdienst import get_nearby_stations, DWDStationRequest
    from wetterdienst import Parameter, PeriodType, TimeResolution

    stations = get_nearby_stations(
        50.0, 8.9,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        num_stations_nearby=1
    )

The function returns a DataFrame with the list of stations with distances [in km]
to the given coordinates.

The station ids within the DataFrame:

.. code-block:: python

    station_ids = stations.STATION_ID.unique()

can be used to download the observation data:

.. code-block:: python

    request = DWDStationRequest(
        station_ids=station_ids,
        parameter=[Parameter.TEMPERATURE_AIR, Parameter.SOLAR],
        time_resolution=TimeResolution.HOURLY,
        start_date="1990-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
        write_file=True,
        prefer_local=True
    )

    for df in request.collect_data():
        # analyse the station here

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments.

Please also check out more advanced examples in the
`example <https://github.com/earthobservations/wetterdienst/tree/master/example>`_
folder on Github.

******
MOSMIX
******

Yet to be implemented...

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
