Changelog
#########

Development
***********

0.80.0 (08.04.2024)
*******************

- Migrate explorer to streamlit
- Explorer: Disable higher than daily resolutions for hosted version
- UI: Add warming stripes

0.79.0 (21.03.2024)
*******************

- Fix parsing of DWD Observation stations where name contains a comma

0.78.0 (09.03.2024)
*******************

- Docker: Install more extras
- Cli/Restapi: Return empty values if no data is available

0.77.1 (08.03.2024)
*******************

- Fix setting NOAA GHCN-h date to UTC

0.77.0 (08.03.2024)
*******************

- Refactor index caching -> Remove monkeypatch for fsspec

0.76.1 (03.03.2024)
*******************

- NOAA GHCN Hourly: Fix date parsing

0.76.0 (02.03.2024)
*******************

- Add NOAA GHCN Hourly API (also known as ISD)

0.75.0 (25.02.2024)
*******************

- Remove join outer workaround for polars and use `outer_coalesce` instead
- Allow duckdb for Python 3.12 again
- Update REST API index layout
- Bump polars to 0.20.10
- Docker: Bump to Python 3.12
- Docker: Reduce image size

0.74.0 (22.02.2024)
*******************

- Restapi: Add health check endpoint

0.73.0 (09.02.2024)
*******************

- Set upper version bound for Python to 4.0
- Add temporary workaround for bugged line in IMGW Hydrology station list
- Fix parsing of dates in NOAA GHCN api
- Make pandas optional

0.72.0 (13.01.2024)
*******************

- Allow for passing kwargs to the `to_csv` method
- Fix issue when using `force_ndarray_like=True` with pint UnitRegistry

0.71.0 (03.01.2024)
*******************

- Fix issue with DWD DMO api
- CI: Add support for Python 3.12

0.70.0 (30.12.2023)
*******************

- Docker: Enable interpolation in wetterdienst standard image
- IMGW Meteorology: Drop workaround for mixed up station list to fix issue
- WSV Hydrology: Fix issue with station list characteristic values
- DWD Observation: Remove redundant replace empty string in parser
- NWS Observation: Read json data from bytes
- EA Hydrology: Read json data from bytes
- Replace partial with lambda in most places
- IMGW: Use ttl of 5 minutes for caching

0.69.0 (18.12.2023)
*******************

- Restapi: Unify station parameter and add alias
- Interpolation: Make maximum station distance per parameter configurable via settings
- Result: Convert date to string only if dataframe is not empty
- Restapi: Move restapi from /restapi to /api

0.68.0 (01.12.2023)
*******************

- Add example for comparing Mosmix forecast and Observation data
- Fix parsing of DWD Observation 1 minute precipitation data

0.67.0 (17.11.2023)
*******************

- [Breaking] Use start_date and end_date instead of from_date and to_date
- Use artificial station id for interpolation and summarization
- Rename taken station ids columns for interpolation and summarization

0.66.1 (08.11.2023)
*******************

- Add workaround for issue with DWD Observation station lists

0.66.0 (07.11.2023)
*******************

- Fix DWD DMO access again
- Add lead time argument - one of short, long - for DWD DMO to address two versions of icon
- Rework dict-like export formats and tests with extensive support for typing
- Improve radar access
- Style restapi landing page
- Replace timezonefinder by tzfpy

0.65.0 (24.10.2023)
*******************

- Cleanup error handling
- Make cli work with DwdDmoRequest API
- Cleanup cli docs
- Fix DWD Observation API for 5 minute data

0.64.0 (12.10.2023)
*******************

- Remove direct tzdata dependency
- Replace pandas read_fwf calls by polars substitutes
- Export: Add support for InfluxDB 3.x

0.63.0 (08.10.2023)
*******************

- [Streamlit] Add sideboard with settings
- [Streamlit] Add station information json
- [Streamlit] Add units to DataFrame view and plots
- [Streamlit] Add JSON download
- Return data correctly sorted

0.62.0 (07.10.2023)
*******************

- Fix multiple issues with DwdObservationRequest API
- Raise minimum version of polars to 0.19.6 due to breaking changes

0.61.0 (06.10.2023)
*******************

- Make parameters TEMPERATURE_AIR_MAX_200 and TEMPERATURE_AIR_MIN_200 summarizable/interpolatable
- Add streamlit app for DWD climate stations
- Add sql query function to streamlit app
- Fix imgw meteorology station list parsing
- Improve streamlit app plotting capabilities
- Fix DWD DMO api

0.60.0 (16.09.2023)
*******************

- Add implementation for DWD DMO

0.59.3 (11.09.2023)
*******************

- Fix DWD solar date string correction

0.59.2 (06.09.2023)
*******************

- Fix documentation and unit conversion for Geosphere 10minute radiation data

0.59.1 (18.07.2023)
*******************

- Fix Geosphere parameter names

0.59.0 (30.07.2023)
*******************

- Revise type hints for parameter and station_id
- Fix Geosphere Observation parsing of dates in values -> thanks to @mhuber89 who discovered the bug and delivered a fix

0.58.1 (26.07.2023)
*******************

- Fix bug with Geosphere parameter case

0.58.0 (10.07.2023)
*******************

- Add retry to functions
- Add IMGW Hydrology API
- Add IMGW Meteorology API
- Rename FLOW to DISCHARGE and WATER_LEVEL to STAGE everywhere

0.57.1 (28.06.2023)
*******************

- Fix pyarrow dependency

0.57.0 (15.05.2023)
*******************

- Backend: Migrate from pandas to polars
- Sources: Add DWD Road Weather data

.. attention::

    Switching to Polars may cause breaking changes for certain user-space code
    heavily using pandas idioms, because Wetterdienst now returns a `Polars DataFrame`_.
    If you absolutely must use a pandas DataFrame, you can cast the Polars DataFrame
    to pandas by using the ``.to_pandas()`` method.

.. _Polars DataFrame: https://pola-rs.github.io/polars/py-polars/html/reference/dataframe/

0.56.2 (11.05.2023)
*******************

- Fix Unit definition for RADIATION_GLOBAL

0.56.1 (10.05.2023)
*******************

- Fix JOULE_PER_SQUARE_METER definition from kilojoule/m2 to joule/m2

0.56.0 (02.05.2023)
*******************

- Update docker images
- Fix now and now_local attributes on core class

0.55.2 (20.04.2023)
*******************

- Fix precipitation index interpolation

0.55.1 (17.04.2023)
*******************

- Fix setting empty values in DWD observation data
- Fix DWD Radar composite path

0.55.0 (19.03.2023)
*******************

- Explorer: Fix function calls
- Drop Python 3.8 support

0.54.1 (13.03.2023)
*******************

- Fix DWD Observations 1 minute fileindex

0.54.0 (06.03.2023)
*******************

- CLI: Fix cli arguments with multiple items separated by comma (,)
- Fix fileindex/metaindex for DWD Observation
- SCALAR: Improve handling skipping of empty stations, especially within .filter_by_rank function
- DOCS: Fix precipitation height unit
- DOCS: Fix examples with "recent" period
- Make all parameter levels equal for all weather services to reduce complexity in code
- Change ``tidy`` option to ``shape``, where ``shape="long"`` equals ``tidy=True`` and ``shape="wide"`` equals ``tidy=False``
- Naming things: All things "Scalar" are now called "Timeseries", with settings prefix ``ts_``
- Drop some unnecessary enums
- Rename Environment Agency to ea in subspace

0.53.0 (07.02.2023)
*******************

- SCALAR: Change tidy option to be set to True if multiple different entire datasets are queried
  This change is in accordance with exporting results to json where multiple DataFrames are concatenated.
- CLI: Add command line options ``wetterdienst --version`` and ``wetterdienst -v``
  to display version number
- Further cleanups
- Change Settings to be provided via initialization instead of having a singleton

0.52.0 (19.01.2023)
*******************

- Add Geosphere Observation implementation for Austrian meteorological data
- RADAR: Clean up code and merge access module into api
- DWD MOSMIX: Fix parsing station list
- DWD MOSMIX: Fix converting degrees minutes to decimal degrees within the
  stations list. The previous method did not produce correct results on
  negative lat/lon values.

0.51.0 (01.01.2023)
*******************

- Update wetterdienst explorer with clickable stations and slighly changed layout
- Improve radar tests and certain dict comparisons
- Fix problem with numeric column names in method gain_of_value_pairs

0.50.0 (03.12.2022)
*******************

- Interpolation/Summary: Now the queried point can be an existing station laying on the border of the polygon that it's
  being checked against
- Geo: Change function signatures to use latlon tuple instead of latitude and longitude
- Geo: Enable querying station id instead of latlon within interpolate and summarize
- Geo: Allow using values of nearby stations instead of interpolated values
- Fix timezone related problems when creating full date range
- UI: Add interpolate/summarize methods as subspaces

0.49.0 (28.11.2022)
*******************

- Fix bug where duplicates of acquired data would be dropped regarding only the date but not the parameter
- Add NOAA NWS Observation API
- Add Eaufrance Hubeau API for French river data (flow, stage)
- Fix NOAA GHCN access issues with timezones and empty data

0.48.0 (11.11.2022)
*******************

- Fix DWD Observation urban_pressure dataset access (again)
- Add example to dump DWD climate summary observations in zarr with help of xarray

0.47.1 (23.10.2022)
*******************

- Fix DWD Observation urban_pressure dataset access

0.47.0 (14.10.2022)
*******************

- Add support for reading DWD Mosmix-L all stations files

0.46.0 (14.10.2022)
*******************

- Add summary of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

0.45.2 (11.10.2022)
*******************

- Make DwdMosmixRequest return data according to start and end date

0.45.1 (10.10.2022)
*******************

- Fix passing an empty DataFrame through unit conversion and ensure set of columns

0.45.0 (22.09.2022)
*******************

- Add interpolation of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)
- Fix access of DWD Observation climate_urban datasets

0.44.0 (18.09.2022)
*******************

- Slightly adapt the conversion function to satisfy linter
- Fix parameter names:
    - we now use consistently INDEX instead of INDICATOR
    - index and form got mixed up with certain parameters, where actually index was measured/given but not the form
    - global radiation was mistakenly named radiation_short_wave_direct at certain points, now it is named correctly
- Adjust Docker images to fix build problems, now use python 3.10 as base
- Adjust NOAA sources to AWS as NCEI sources currently are not available
- Make explorer work again for all services setting up Period enum classes instead of single instances of Period for
  period base

0.43.0 (05.09.2022)
*******************

- Use lxml.iterparse to reduce memory consumption when parsing DWD Mosmix files
- Fix Settings object instantiation
- Change logging level for Settings.cache_disable to INFO
- Add DWD Observation climate_urban datasets

0.42.1 (25.08.2022)
*******************

- Fix DWD Mosmix station locations

0.42.0 (22.08.2022)
*******************

- Move cache settings to core wetterdienst Settings object
- Fix two parameter names

0.41.1 (04.08.2022)
*******************

- Fix correct mapping of periods for solar daily data which should also have Period.HISTORICAL besides Period.RECENT

0.41.0 (24.07.2022)
*******************

- Fix passing through of empty dataframe when trying to convert units

0.40.0 (10.07.2022)
*******************

- Update dependencies

0.39.0 (27.06.2022)
*******************

- Update dependencies

0.38.0 (09.06.2022)
*******************

- Add DWD Observation 5 minute precipitation dataset
- Add test to compare actually provided DWD observation datasets with the ones we made available with wetterdienst
- Fix one particular dataset which was not correctly included in our DWD observations resolution-dataset-mapping

0.37.0 (06.06.2022)
*******************

- Fix EA hydrology access
- Update ECCC observation methods to acquire station listing

0.36.0 (31.05.2022)
*******************

- Fix using shared FSSPEC_CLIENT_KWARGS everywhere

0.35.0 (29.05.2022)
*******************

- Add option to skip empty stations (option tidy must be set)
- Add option to drop empty rows (value is NaN) (option tidy must be set)

0.34.0 (22.05.2022)
*******************

- Add UKs Environment Agency hydrology API

0.33.0 (14.05.2022)
*******************

- Fix acquisition of DWD weather phenomena data
- Set default encoding when reading data from DWD with pandas to 'latin1'
- Fix typo in `EcccObservationResolution`

0.32.4 (14.05.2022)
*******************

- Fix acquisition of historical DWD radolan data that comes in archives

0.32.3 (12.05.2022)
*******************

- Fix creation of empty DataFrame for missing station ids
- Fix creation of empty DataFrame for annual data

0.32.2 (10.05.2022)
*******************

- Revert ssl option

0.32.1 (09.05.2022)
*******************

- Circumvent DWD server ssl certificate problem by temporary removing ssl verification

0.32.0 (24.04.2022)
*******************

- Add implementation of WSV Pegelonline service
- Clean up code at several places
- Fix ECCC observations access

0.31.1 (03.04.2022)
*******************

- Change integer dtypes in untidy format to float to prevent loosing information when converting units

0.31.0 (29.03.2022)
*******************

- Improve integrity of dataset, parameter and unit enumerations with further tests
- Change source of hourly sunshine duration to dataset sun
- Change source of hourly total cloud cover (+indicator) to dataset cloudiness

0.30.1 (03.03.2022)
*******************

- Fix naming of sun dataset
- Fix DWD Observation monthly test

0.30.0 (27.02.2022)
*******************

- Fix monthly/annual data of DWD observations

0.29.0 (27.02.2022)
*******************

- Simplify parameters using only one enumeration for flattened and detailed parameters
- Rename dataset SUNSHINE_DURATION to SUN to avoid complications with similar named parameter and dataset
- Rename parameter VISIBILITY to VISIBILITY_RANGE
- Add datasets EXTREME_WIND (subdaily) and MORE_WEATHER_PHENOMENA (daily)
- Add support for Python 3.10 and drop Python 3.7

0.28.0 (19.02.2022)
*******************

- Extend explorer to use all implemented APIs
- Fix cli/restapi: return json and use NULL instead of NaN

0.27.0 (16.02.2022)
*******************

- Fix missing station ids within values result
- Add details about time interval for NOAA GHCN stations
- Fix falsely calculated station distances
- Add support for Python 3.10, drop support for Python 3.7

0.26.0 (06.02.2022)
*******************

- Add Wetterdienst.Settings to manage general settings like tidy, humanize,...
- Rename DWD forecast to mosmix
- Instead of "kind" use "network" attribute to differ between different data products of a provider
- Change data source of NOAA GHCN after problems with timeouts when reaching the server
- Fix problem with timezone conversion when having dates that are already timezone aware

0.25.1 (30.01.2022)
*******************

- Fix cli error with upgraded click ^8.0 where default False would be converted to "False"

0.25.0 (30.01.2022)
*******************

- Fix access to ECCC stations listing using Google Drive storage
- Remove/replace caching entirely by fsspec (+monkeypatch)
- Fix bug with DWD intervals

0.24.0 (24.01.2022)
*******************

- Add NOAA GHCN API
- Fix radar index by filtering out bz2 files

0.23.0 (21.11.2021)
*******************

- [FIX] Add missing positional dataset argument for _create_empty_station_parameter_df
- [FIX] Timestamps of 1 minute / 10 minutes DWD data now have a gap hour at the end of year 1999
  due to timezone shifts

0.22.0 (01.10.2021)
*******************

- [BREAKING] Introduce core Parameter enum with fixed set of parameter names. Several parameters may have been
  renamed!
- Add FSSPEC_CLIENT_KWARGS variable at wetterdienst.util.cache for passing extra settings to fsspec request client

0.21.0 (10.09.2021)
*******************

- Start migrating from ``dogpile.cache`` to ``filesystem_spec``

0.20.4 (07.08.2021)
*******************

Features
========

- Enable selecting a parameter precisely from a dataset by passing a tuple like [("precipitation_height", "kl")] or
  [("precipitation_height", "precipitation_more")], or for cli/restapi use "precipitation_height/kl"
- Rename ``wetterdienst show`` to ``wetterdienst info``, make version accessible via CLI with
  ``wetterdienst version``

Bugfixes
========

- Bug when querying an entire DWD dataset for 10_minutes/1_minute resolution without providing start_date/end_date,
  which results in the interval of the request being None
- Test of restapi with recent period
- Get rid of pandas performance warning from DWD Mosmix data

0.20.3 (15.07.2021)
*******************

- Bugfix acquisition of DWD radar data
- Adjust DWD radar composite parameters to new index

0.20.2 (26.06.2021)
*******************

- Bugfix tidy method for DWD observation data

0.20.1 (26.06.2021)
*******************

- Update readme on sandbox developer installation
- Bugfix show method

0.20.0 (23.06.2021)
*******************

- Change cli base to click
- Add support for wetterdienst core API in cli and restapi
- Export: Use InfluxDBClient instead of DataFrameClient and improve connection handling with InfluxDB 1.x
- Export: Add support for InfluxDB 2.x
- Fix InfluxDB export by skipping empty fields
- Add show() method with basic information on the wetterdienst instance

0.19.0 (14.05.2021)
*******************

- Make tidy method a abstract core method of Values class
- Fix DWD Mosmix generator to return all contained dataframes

0.18.0 (04.05.2021)
*******************

- Add origin and si unit mappings to services
- Use argument "si_units" in request classes to convert origin units to si, set to default
- Improve caching behaviour by introducing optional ``WD_CACHE_DIR`` and
  ``WD_CACHE_DISABLE`` environment variables. Thanks, @meteoDaniel!
- Add baseline test for ECCC observations
- Add DWD Observation hourly moisture to catalogue

0.17.0 (08.04.2021)
*******************

- Add capability to export data to Zarr format
- Add Wetterdienst Explorer UI. Thanks, @meteoDaniel!
- Add MAC ARM64 supoort with dependency restrictions
- Radar: Verify HDF5 responses instead of returning invalid data
- Add support for stations filtering via bbox and name
- Add support for units in distance filtering
- Rename station_name to name
- Rename filter methods to .filter_by_station_id and .filter_by_name, use same convention for bbox, filter_by_rank
  (previously nearby_number), filter_by_distance (nearby_distance)
- Mosmix: Use cached stations to improve performance

0.16.1 (31.03.2021)
*******************

- Make .discover return lowercase parameters and datasets

0.16.0 (29.03.2021)
*******************

- Use direct mapping to get a parameter set for a parameter
- Rename DwdObservationParameterSet to DwdObservationDataset as well as corresponding
  columns
- Merge metadata access into Request
- Repair CLI and I/O subsystem
- Add capability to export to Feather- and Parquet-files to I/O subsystem
- Deprecate support for Python 3.6
- Add ``--reload`` parameter to ``wetterdienst restapi`` for supporting development
- Improve spreadsheet export
- Increase I/O subsystem test coverage
- Make all DWD observation field names lowercase
- Make all DWD forecast (mosmix) field names lowercase
- Add Environment and Climate Change Canada API
- Rename humanize_parameters to humanize and tidy_data to tidy
- Radar: Use OPERA as data source for improved list of radar sites

0.15.0 (07.03.2021)
*******************

- Add StationsResult and ValuesResult to allow for new workflow and connect stations and
  values request
- Add accessor .values to Stations class to get straight to values for a request
- Rename Stations to Request and use upper camel case e.g. DwdObservationRequest
- Add top-level API
- Fix issue with Mosmix station location

0.14.1 (21.02.2021)
*******************

- Fix date filtering of DWD observations, where accidentally an empty dataframe was
  returned

0.14.0 (05.02.2021)
*******************

- DWD: Add missing radar site "Emden" (EMD, wmo=10204)
- Mosmix stations: fix longitudes/latitudes to be decimal degrees (before they were
  degrees and minutes)
- Change key STATION_HEIGHT to HEIGHT, LAT to LATITUDE, LON to LONGITUDE
- Rename "Data" classes to "Values"
- Make arguments singular

0.13.0 (21.01.2021)
*******************

- Create general Resolution and Period enumerations that can be used anywhere
- Create a full dataframe even if no values exist at requested time
- Add further attributes to the class structure
- Make dates timezone aware
- Restrict dates to isoformat

0.12.1 (29.12.2020)
*******************

- Fix 10minutes file index interval range by adding timezone information

0.12.0 (23.12.2020)
*******************

- Move more functionality into core classes
- Add more attributes to the core e.g. source and timezone
- Make dates of internal data timezone aware, set start date and end date to UTC
- Add issue date to Mosmix class that actually refers to the Mosmix run instead of start
  date and end date
- Use Result object for every data related return
- In accordance with typical naming conventions, DWDObservationSites is renamed to
  DWDObservationStations, the same is applied to DWDMosmixSites
- The name ELEMENT is removed and replaced by parameter while the acutal parameter set
  e.g. CLIMATE_SUMMARY is now found under PARAMETER_SET
- Remove StorageAdapter and its dependencies
- Methods self.collect_data() and self.collect_safe() are replaced by self.query() and
  self.all() and will deprecate at some point

0.11.1 (10.12.2020)
*******************

- Bump ``h5py`` to version 3.1.0 in order to satisfy installation on Python 3.9

0.11.0 (04.12.2020)
*******************

- InfluxDB export: Fix export in non-tidy format (#230). Thanks, @wetterfrosch!
- InfluxDB export: Use "quality" column as tag (#234). Thanks, @wetterfrosch!
- InfluxDB export: Use a batch size of 50000 to handle larger amounts of data (#235). Thanks, @wetterfrosch!
- Update radar examples to use ``wradlib>=1.9.0``. Thanks, @kmuehlbauer!
- Change wherever possible column type to category
- Increase efficiency by downloading only historical files with overlapping dates if start_date and end_date are given
- Use periods dynamically depending on start and end date
- Fix inconsistency within 1 minute precipitation data where historical files have more columns
- Improve DWD PDF parser to extract quality information and select language.
  Also, add an example at ``example/dwd_describe_fields.py`` as well as
  respective documentation.

0.10.1 (14.11.2020)
*******************

- Upgrade to dateparser-1.0.0. Thanks, @steffen746, @noviluni and @Gallaecio!
  This fixes a problem with timezones on Windows. The reason is that
  Windows has no zoneinfo database and ``tzlocal`` switched from ``pytz`` to ``tzinfo``.
  https://github.com/earthobservations/wetterdienst/issues/222

0.10.0 (26.10.2020)
*******************

- CLI: Obtain "--tidy" argument from command line
- Extend MOSMIX support to equal the API of observations
- DWDObservationSites now filters for those stations which have a file on the server
- DWDObservationData now also takes an individual parameter
  independent of the pre-configured DWD datasets by using DWDObservationParameter or
  similar names e.g. "precipitation_height"
- Newly introduced coexistence of DWDObservationParameter and DWDObservationParameterSet
  to address parameter sets as well as individual parameters
- Imports are changed to submodule thus now one has to import everything from
  wetterdienst.dwd
- Renaming of time_resolution to resolution, period_type to period, several other
  relabels

0.9.0 (09.10.2020)
*******************

- Large refactoring
- Make period type in DWDObservationData and cli optional
- Activate SQL querying again by using DuckDB 0.2.2.dev254. Thanks, @Mytherin!
- Fix coercion of integers with nans
- Fix problem with storing IntegerArrays in HDF
- Rename ``DWDStationRequest`` to ``DWDObservationData``
- Add ``DWDObservationSites`` API wrapper to acquire station information
- Move ``discover_climate_observations`` to ``DWDObservationMetadata.discover_parameters``
- Add PDF-based ``DWDObservationMetadata.describe_fields()``
- Upgrade Docker images to Python 3.8.6
- Move intermediate storage of HDF out of data collection
- Fix bug with date filtering for empty/no station data for a given parameter
- Radar data: Add non-RADOLAN data acquisition

0.8.0 (25.09.2020)
*******************

- Add TTL-based persistent caching using dogpile.cache
- Add ``example/radolan.py`` and adjust documentation
- Export dataframe to different data sinks like SQLite, DuckDB, InfluxDB and CrateDB
- Query results with SQL, based on in-memory DuckDB
- Split get_nearby_stations into two functions, get_nearby_stations_by_number and
  get_nearby_stations_by_distance
- Add MOSMIX client and parser. Thanks, @jlewis91!
- Add basic HTTP API

0.7.0 (16.09.2020)
*******************

- Add test for Jupyter notebook
- Add function to discover available climate observations
  (time resolution, parameter, period type)
- Make the CLI work again and add software tests to prevent future havocs
- Use Sphinx Material theme for documentation
- Fix typo in enumeration for TimeResolution.MINUTES_10
- Add test for Jupyter notebook
- Add function to discover available climate observations
  (time resolution, parameter, period type)

0.6.0 (07.09.2020)
*******************

- enhance usage of get_nearby_stations to check for availability
- output of get_nearby_stations is now a slice of meta_data DataFrame output

0.5.0 (27.08.2020)
*******************

- add RADOLAN support
- change module and function naming in accordance with RADOLAN

0.4.0 (03.08.2020)
*******************

- extend DWDObservationData to take multiple parameters as request
- add documentation at readthedocs.io
- [cli] Adjust methods to work with multiple parameters

0.3.0 (26.07.2020)
*******************

- establish code style black
- setup nox session that can be used to run black via nox -s black for one of the supported
  Python versions
- add option for data collection to tidy the DataFrame (properly reshape) with the
  "tidy_data" keyword and set it to be used as default
- fix integer type casting for cases with nans in the column/series
- fix humanizing of column names for tidy data

0.2.0 (23.07.2020)
*******************

- [cli] Add geospatial filtering by distance.
- [cli] Filter stations by station identifiers.
- [cli] Add GeoJSON output format for station data.
- improvements to parsing high resolution data by setting specific datetime formats and changing to concurrent.futures
- fix na value detection for cases where cells have leading and trailing whitespace
- change column name mapping to more explicit one with columns being individually addressable
- add full column names for every individual parameter
- more specific type casting for integer fields and string fields

0.1.1 (05.07.2020)
*******************

- [cli] Add geospatial filtering by number of nearby stations.
- Simplify release pipeline
- small updates to readme
- change updating "parallel" argument to be done after parameter parsing to prevent mistakenly not found
  parameter
- remove find_all_match_strings function and extract functionality to individual operations
- parameter, time resolution and period type can now also be passed as strings of the enumerations e.g.
  "climate_summary" or "CLIMATE_SUMMARY" for Parameter.CLIMATE_SUMMARY
- enable selecting nearby stations by distance rather then by number of stations

0.1.0 (02.07.2020)
*******************

- initial release
- update README.md
- update example notebook
- add Gh Action for release
- rename library
