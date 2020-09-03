API
###

The API is divided amongst the data products as written in the Data coverage chapter.

API For Historical Weather Data
*******************************

The API for the historical weather data mainly consists of the following functions:

- **metadata_for_dwd_data:**
    - discover what data for a set of parameters (parameter, time_resolution,
      period_type) is available, especially which stations can be found.
    - with **create_new_file_index**, the function can be forced to retrieve a new list
      of files from the server, which is usually avoided as it rarely changes.

- **get_nearby_stations:**
    - calculates the close weather stations based on the coordinates for the requested
      data
    - either selected by rank (n stations) or by distance in km
    - it returns a DataFrame with meta data, distances [in km] and station ids that can be used to download the
      data plus the

- **DWDStationRequest:**
    - a class that can combine multiple periods/date ranges for any number of stations
      and parameters of one time resolution
    - wraps collect_dwd_data:

        - **collect_dwd_data:**
            - combines create_file_list_for_dwd_server, download_dwd_data and
              parse_dwd_data for multiple stations
            - wraps the following three functions:

                - **create_file_list_for_dwd_server:**
                    - is used with the help of the metadata to retrieve file paths to
                      files for a set of parameters + station id
                    - here also **create_new_file_index** can be used

                - **download_dwd_data_parallel:**
                    - is used with the created file paths to download and store the data
                      (second os optionally, in a hdf)

                - **parse_dwd_data:**
                            - is used to get the data into the Python environment in
                              shape of a pandas DataFrame.
                            - the data will be ready to be analyzed by you!



Additionally the following functions allow you to reset the cache of the file/meta index:

- **reset_file_index_cache:**
    - reset the cached file index to get latest list of files (only required for
      constantly running system)

- **reset_meta_index_cache:**
    - reset the cached meta index to get latest list of files (only required for
      constantly running system)

Parameter, time resolution and period type can be entered in three ways:

- by using the exact enumeration e.g.
    .. code-block:: Python

        Parameter.CLIMATE_SUMMARY

- by using the enumeration string e.g.
    .. code-block:: Python

        "climate_summary" or "CLIMATE_SUMMARY"

- by using the originally defined parameter string e.g.
    .. code-block:: Python

        "kl"

How can you use the functions above? Let's take a look!

We want to get the metadata for a given parameter, time resolution and period type

.. code-block:: Python

    import wetterdienst
    from wetterdienst import Parameter, PeriodType, TimeResolution

    metadata = wetterdienst.metadata_for_dwd_data(
        parameter=Parameter.PRECIPITATION_MORE,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

The function returns a pandas DataFrame with information about the available stations,
including the column **HAS_FILE**, that indicates if the station has a file with data on
the server (which may not always be the case!).

Now, we know an approximate location, where we cant to get data for the temperature.

.. code-block:: Python

    from datetime import datetime
    from wetterdienst import Parameter, PeriodType, TimeResolution
    from wetterdienst import get_nearby_stations

    get_nearby_stations(
        50., 8.9,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        num_stations_nearby=1
    )

The function returns a meta data DataFrame, where we can find weather station ids and distances to get our
observation data.

.. code-block:: Python

    from wetterdienst import collect_dwd_data
    from wetterdienst import Parameter, PeriodType, TimeResolution

    station_data = collect_dwd_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

Et voila: We just got the data we wanted for our location and are ready to analyse the
temperature on historical developments. To go even further we may use the following
code.

.. code-block:: Python

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

    for station_data in request.collect_data():
        # analyse the station here

This gives us the most options to work with the data, getting multiple parameters at
once, parsed nicely into column structure with improved parameter names and stored
automatically on the drive if wanted.

Check out the more advanced examples in the
`example <https://github.com/earthobservations/wetterdienst/tree/master/example>`_
folder on Github.

API For MOSMIX
**************

Yet to be implemented...

API For RADOLAN
***************

A request for RADOLAN data can be made either with DWDRadolanRequest or can be directly
collected with collect_radolan_data.

To use DWDRadolanRequest, you have to provide a time resolution (either hourly or daily)
and date_times (list of datetimes or strings) or a start date and end date. Datetimes
are rounded to HH:50min as the data is packaged for this minute step. Additionally
you can provide a folder and if to use local RADOLAN (to read in stored data) and if
to write the file to a folder.


