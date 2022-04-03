Changelog
#########

Development
***********

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

- Rename wetterdienst show to wetterdienst info, make version accessible via cli with
  wetterdienst version

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
