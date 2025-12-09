# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.

## [Unreleased]

## [0.116.0] - 2025-12-09

### Changed

- Improve polars code, thanks @SeeBastion524

### Fixed

- Allow concatenation of station data with varying columns, thanks @jb-at-bdr
- Adjust data type of "name" column, thanks @jb-at-bdr

## [0.115.0] - 2025-11-24

### Added

- Add classifier for python 3.14
- Add new data of DWD Derived, thanks @jb-at-bdr

### Changed

- Update docker image to use python 3.14

### Fixed

- Cast value in interpolate function to float

  @ninjeanne reported that wetterdienst lately quirks when running interpolation. This issue is related to one of the new polars versions > 1.33.1. A shorthand fix would be to cast the value coming from the scipy interpolate function to a float.

## [0.114.3] - 2025-11-07

### Fixed

- \[DWD Obs\] Fix encoding issue

## [0.114.2] - 2025-11-05

### Fixed

- \[DWD DMO\] Fix path for `icon_eu` and minor fixes

## [0.114.1] - 2025-11-01

### Fixed

- Fix global import of duckdb exception in `to_target` method

## [0.114.0] - 2025-10-31

### Added

- \[DWD Obs\] Use utf8 encoding for parsing data
- Add `if_exists` argument to `to_target`
- Use more polars-native methods

### Fixed

- \[DWD Road\]: Skip empty files

### Changed

- Bump polars minimum to 1.15.0

## [0.113.0] - 2025-09-21

### Added

- Make Mosmix and DMO a lot faster for multiple stations requests

### Changed

- Bump pypdf to <7
- Make pypdf optional

## [0.112.0] - 2025-09-06

### Changed

- Switch back to `WholeFileCacheFileSystem` for caching
- Improve more things on caching
- Update uv.lock
- Polars: Set format and timezone on datetime conversion

## [0.111.0] - 2025-08-03

### Added

- Make humidity interpolatable
- Improve interpolation configuration
- Set missing `return_dtype` in fileindex function
- Set `return_dtype` for polars functions

### Changed

- Pin zarr to `>=3.1;python_version>=3.11`
- Docker: Copy uv bin from uv image
- Pin lxml to <7

### Fixed

- Parse parameters only if any are given
- Fix export for interpolated values to csv
- Round timestamps of hourly solar data to nearest hour
- Fix several polars issues
- Docker: Install chromium to fix png export

## [0.110.0] - 2025-07-23

### Added

- Make retry of `download_file` more robust
- Overhaul docs switching to `sphinx` and `myst-parser`
- Improve exception handling in restapi
- Improve download of files

### Changed

- Drop upper version pins for fsspec and tzdata
- Introduce `wetterdienst.model`, streamline others
- Bump minimum kaleido version to `0.2.2`

### Fixed

- Export: Fix influx tags and fields
- \[NOAA GHCN hourly\] Fix metadata creation
- Include resolution column in wide format
- Disallow `polars==1.31.0` due to issues

## [0.109.0] - 2025-06-03

### Changed

- Split `coordinates` and `bbox` into separate arguments
- Bump dependencies

## [0.108.0] - 2025-04-25

### Added

- Improve restapi look and add impressum
- Add uvloop and httptools for speed via `uvicorn[standard]`

### Changed

- Use dataclass everywhere
- Refactor query method
- Adjust retry of function `download_file`

### Fixed

- Fix numerous radar tests

## [0.107.0] - 2025-03-25

### Changed

- Refactor `download_file`

### Fixed

- Fix false attribute parsing by pydantic model in cli
- Fix datetime parsing for generic radar data

## [0.106.0] - 2025-03-05

### Fixed

- Improve parameter unpacking in `ParameterSearch.parse`
- Fix docker manifest

## [0.105.0] - 2025-03-01

### Added

- Add user agent to default `fsspec_client_kwargs`
- Adjust apis to track resolution and dataset (allows querying data for different resolutions and datasets in one request)

### Changed

- Improve date parsing across multiple apis
- Cleanup docker image
- Improve numerous apis

### Fixed

- \[WSV Pegel\] Fix characteristic values and improve date parsing

## [0.104.0] - 2025-02-15

### Changed

- Reduce the margin of the stations plot
- Make pydantic models for uis simpler
- Migrate from `sklearn+numpy` to `pyarrow` for location querying
- Remove command from Docker file
- Improve workflow for Docker
- Get rid of columns enumeration
- \[NOAA GHCN\] Improve date parsing and other fixes

## [0.103.0] - 2025-02-02

### Added

- Stripes: Replace matplotlib by plotly
- Explorer: Add download button for plot
- Split up plotting extras into `plotting` and `matplotlib`
- Interpolation/Summary: Add dataset to DataFrame
- Add plotting capabilities

### Changed

- Update docker image extras

### Removed

- Remove unused cachetools dependency

### Fixed

- Fix benchmark code
- Make fastexcel a polars extra
- Drop click-params dependency
- Make pyarrow a polars extra

## [0.102.0] - 2025-01-17

### Added

- Add cmd to docker image

### Changed

- Use `to_list()[0]` instead of `first()`

## [0.101.0] - 2025-01-13

### Added

- Move more details into `MetadataModel`

### Changed

- \[DWD Obs\] Make the download function more flexible using threadpool
- \[DWD Obs\] Cleanup parser function
- \[DWD Obs\] Improve fileindex and metaindex

### Fixed

- \[DWD Obs\] Reduce unnecessary file index calls during retrieval of data for stations with multiple files

## [0.100.0] - 2025-01-06

### Added

- Add logo for restapi
- **Breaking:** Add dedicated unit converter

  Attention: Many units are changed to be more consistent with typical meteorological units. We now use `°C` for temperatures. Also, length units are now separated in `length_short`, `length_medium` and `length_long` to get more reasonable decimals. For more information, see the new units chapter (usage/units) in the documentation.

### Changed

- Add reasonable upper bounds for dependencies

### Fixed

- Filter out invalid underscore prefixed files

## [0.99.0] - 2024-12-30

### Added

- Add setting `ts_complete=False` that allows to prevent building a complete time series

### Changed

- Docs: Change to markdown using mkdocs
- Settings: Switch to `pydantic_settings` for settings management
- Improve wetterdienst api class
- Dissolve wetterdienst notebook into examples
- Use `duckdb.sql` and ask only for WHERE clause
- Update restapi annotations
- Use `Settings` in restapi/cli core functions
- Restapi/Cli: Use pydantic models for request parameters
- Rename `dropna` to `drop_nulls`
- Change default of `drop_nulls` to True
- Replace occurrences of `dt.timezone.utc` by `ZoneInfo("UTC")`
- Improve release workflow using `uv build` and `uv publish`
- Improve docker-publish workflow to use `uv build`

## [0.98.0] - 2024-12-09

### Added

- Add support for Python 3.13

### Changed

- **Breaking:** Add new metadata model: Requests now use `parameters` instead of `parameter` and `resolution` e.g. `parameters=[("daily", "kl")]` instead of `parameter="kl", resolution="daily"`

### Deprecated

- Deprecate Python 3.9

## [0.97.0] - 2024-10-06

### Fixed

- DWD Road: Use correct 15 minute resolution

## [0.96.0] - 2024-10-04

### Changed

- Bump polars to `>=1.0.0`
- Change `DWDMosmixValues` and `DWDDmoValues` to follow the core `_collect_station_parameter` method
- Allow only single issue retrieving with `DWDMosmixRequest` and `DWDDmoRequest`

## [0.95.1] - 2024-09-04

### Fixed

- Fix `state` column in station list creation for DWD Observation

## [0.95.0] - 2024-08-27

### Changed

- Make fastexcel non-optional
- Remove upper dependency bounds

## [0.94.0] - 2024-08-10

### Added

- DWD Road: Add new station groups, log warning if no data is available, especially if the station group is one of the temporarily unavailable ones

### Fixed

- Explorer: Fix DWD Mosmix request kwargs setup

## [0.93.0] - 2024-08-06

### Fixed

- Fix multiple Geosphere parameter and unit enums
- Explorer: Fix wrap `(parameter, dataset)` in iterator
- Adjust parameter typing of apis

## [0.92.0] - 2024-07-31

### Changed

- Rename parameters
  - units in parameter names are now directly following the number
  - temperature parameters now use meter instead of cm and also have a unit
  - e.g. TEMPERATURE_AIR_MEAN_2M, CLOUD_COVER_BETWEEN_2KM_TO_7KM, PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0MM_LAST_6H

### Fixed

- Bump pyarrow version to <18
- Fix EaHydrology station list parsing
- Rename `EaHydrology` to `EAHydrology`
- Fix propagation of settings through `EAHydrology` values

## [0.91.0] - 2024-07-14

### Fixed

- Fix DWD Road api

## [0.90.0] - 2024-07-14

### Changed

- Bump `environs` to <12

### Fixed

- Explorer: Fix json export

## [0.89.0] - 2024-07-03

### Fixed

- EaHydrology: Fix date parsing
- Hubeau: Use correct frequency unit
- Fix group by unpack

## [0.88.0] - 2024-06-14

### Added

- Allow passing `--listen` when running the explorer to specify the host and port

## [0.87.0] - 2024-06-06

### Added

- Add precipitation version

### Changed

- Rename warming stripes to climate stripes
- Replace custom Settings class with pydantic model

## [0.86.0] - 2024-06-01

### Changed

- Interpolation/Summary: Require start and end date
- Enable interpolation and summarization for all services

### Fixed

- Fix multiple issues with interpolation and summarization

## [0.85.0] - 2024-05-29

### Fixed

- Fix `dropna` argument for DWD Mosmix and DMO
- Adjust DWD Mosmix and DMO kml reader to parse all parameters
- Fix `to_target(duckdb)` for stations
- Fix init of `DwdDmoRequest`

## [0.84.0] - 2024-05-15

### Fixed

- Fix DWD Obs station list parsing again

## [0.83.0] - 2024-04-26

### Added

- Allow `wide` shape with multiple datasets

## [0.82.0] - 2024-04-25

### Fixed

- Adjust column specs for DWD Observation station listing
- Maintain order during deduplication
- Change threshold in `filter_by_name` to 0.0...1.0

## [0.81.0] - 2024-04-09

### Added

- Warming stripes: Add option to enable/disable showing only active stations

## [0.80.0] - 2024-04-08

### Added

- Migrate explorer to streamlit
- UI: Add warming stripes

### Changed

- Explorer: Disable higher than daily resolutions for hosted version

## [0.79.0] - 2024-03-21

### Fixed

- Fix parsing of DWD Observation stations where name contains a comma

## [0.78.0] - 2024-03-09

### Added

- Docker: Install more extras

### Fixed

- Cli/Restapi: Return empty values if no data is available

## [0.77.1] - 2024-03-08

### Fixed

- Fix setting NOAA GHCN-h date to UTC

## [0.77.0] - 2024-03-08

### Changed

- Refactor index caching -> Remove monkeypatch for fsspec

## [0.76.1] - 2024-03-03

### Fixed

- NOAA GHCN Hourly: Fix date parsing

## [0.76.0] - 2024-03-02

### Added

- Add NOAA GHCN Hourly API (also known as ISD)

## [0.75.0] - 2024-02-25

### Changed

- Remove join outer workaround for polars and use `outer_coalesce` instead
- Allow duckdb for Python 3.12 again
- Update REST API index layout
- Bump polars to 0.20.10
- Docker: Bump to Python 3.12
- Docker: Reduce image size

## [0.74.0] - 2024-02-22

### Added

- Restapi: Add health check endpoint

## [0.73.0] - 2024-02-09

### Changed

- Set upper version bound for Python to 4.0
- Make pandas optional

### Fixed

- Add temporary workaround for bugged line in IMGW Hydrology station list
- Fix parsing of dates in NOAA GHCN api

## [0.72.0] - 2024-01-13

### Added

- Allow for passing kwargs to the `to_csv` method

### Fixed

- Fix issue when using `force_ndarray_like=True` with pint UnitRegistry

## [0.71.0] - 2024-01-03

### Added

- CI: Add support for Python 3.12

### Fixed

- Fix issue with DWD DMO api

## [0.70.0] - 2023-12-30

### Added

- Docker: Enable interpolation in wetterdienst standard image

### Changed

- Replace partial with lambda in most places
- IMGW: Use ttl of 5 minutes for caching

### Fixed

- IMGW Meteorology: Drop workaround for mixed up station list to fix issue
- WSV Hydrology: Fix issue with station list characteristic values
- DWD Observation: Remove redundant replace empty string in parser
- NWS Observation: Read json data from bytes
- EA Hydrology: Read json data from bytes

## [0.69.0] - 2023-12-18

### Added

- Restapi: Unify station parameter and add alias
- Interpolation: Make maximum station distance per parameter configurable via settings

### Fixed

- Result: Convert date to string only if dataframe is not empty
- Restapi: Move restapi from /restapi to /api

## [0.68.0] - 2023-12-01

### Added

- Add example for comparing Mosmix forecast and Observation data

### Fixed

- Fix parsing of DWD Observation 1 minute precipitation data

## [0.67.0] - 2023-11-17

### Changed

- **Breaking:** Use start_date and end_date instead of from_date and to_date
- Use artificial station id for interpolation and summarization
- Rename taken station ids columns for interpolation and summarization

## [0.66.1] - 2023-11-08

### Fixed

- Add workaround for issue with DWD Observation station lists

## [0.66.0] - 2023-11-07

### Added

- Add lead time argument - one of short, long - for DWD DMO to address two versions of icon

### Changed

- Rework dict-like export formats and tests with extensive support for typing
- Improve radar access
- Style restapi landing page
- Replace timezonefinder by tzfpy

### Fixed

- Fix DWD DMO access again

## [0.65.0] - 2023-10-24

### Changed

- Cleanup error handling
- Make cli work with DwdDmoRequest API
- Cleanup cli docs

### Fixed

- Fix DWD Observation API for 5 minute data

## [0.64.0] - 2023-10-12

### Added

- Export: Add support for InfluxDB 3.x

### Changed

- Remove direct tzdata dependency
- Replace pandas read_fwf calls by polars substitutes

## [0.63.0] - 2023-10-08

### Added

- \[Streamlit\] Add sideboard with settings
- \[Streamlit\] Add station information json
- \[Streamlit\] Add units to DataFrame view and plots
- \[Streamlit\] Add JSON download

### Fixed

- Return data correctly sorted

## [0.62.0] - 2023-10-07

### Changed

- Raise minimum version of polars to 0.19.6 due to breaking changes

### Fixed

- Fix multiple issues with DwdObservationRequest API

## [0.61.0] - 2023-10-06

### Added

- Make parameters TEMPERATURE_AIR_MAX_200 and TEMPERATURE_AIR_MIN_200 summarizable/interpolatable
- Add streamlit app for DWD climate stations
- Add sql query function to streamlit app

### Fixed

- Fix imgw meteorology station list parsing
- Improve streamlit app plotting capabilities
- Fix DWD DMO api

## [0.60.0] - 2023-09-16

### Added

- Add implementation for DWD DMO

## [0.59.3] - 2023-09-11

### Fixed

- Fix DWD solar date string correction

## [0.59.2] - 2023-09-06

### Fixed

- Fix documentation and unit conversion for Geosphere 10minute radiation data

## [0.59.1] - 2023-07-18

### Fixed

- Fix Geosphere parameter names

## [0.59.0] - 2023-07-30

### Changed

- Revise type hints for parameter and station_id

### Fixed

- Fix Geosphere Observation parsing of dates in values -> thanks to @mhuber89 who discovered the bug and delivered a fix

## [0.58.1] - 2023-07-26

### Fixed

- Fix bug with Geosphere parameter case

## [0.58.0] - 2023-07-10

### Added

- Add retry to functions
- Add IMGW Hydrology API
- Add IMGW Meteorology API

### Changed

- Rename FLOW to DISCHARGE and WATER_LEVEL to STAGE everywhere

## [0.57.1] - 2023-06-28

### Fixed

- Fix pyarrow dependency

## [0.57.0] - 2023-05-15

### Added

- Sources: Add DWD Road Weather data

### Changed

- **Breaking:** Backend: Migrate from pandas to polars

  Switching to Polars may cause breaking changes for certain user-space code heavily using pandas idioms, because Wetterdienst now returns a [Polars DataFrame](https://pola-rs.github.io/polars/py-polars/html/reference/dataframe/). If you absolutely must use a pandas DataFrame, you can cast the Polars DataFrame to pandas by using the `.to_pandas()` method.

## [0.56.2] - 2023-05-11

### Fixed

- Fix Unit definition for RADIATION_GLOBAL

## [0.56.1] - 2023-05-10

### Fixed

- Fix JOULE_PER_SQUARE_METER definition from kilojoule/m2 to joule/m2

## [0.56.0] - 2023-05-02

### Fixed

- Update docker images
- Fix now and now_local attributes on core class

## [0.55.2] - 2023-04-20

### Fixed

- Fix precipitation index interpolation

## [0.55.1] - 2023-04-17

### Fixed

- Fix setting empty values in DWD observation data
- Fix DWD Radar composite path

## [0.55.0] - 2023-03-19

### Changed

- Drop Python 3.8 support

### Fixed

- Explorer: Fix function calls

## [0.54.1] - 2023-03-13

### Fixed

- Fix DWD Observations 1 minute fileindex

## [0.54.0] - 2023-03-06

### Changed

- SCALAR: Improve handling skipping of empty stations, especially within .filter_by_rank function
- Make all parameter levels equal for all weather services to reduce complexity in code
- Change `tidy` option to `shape`, where `shape="long"` equals `tidy=True` and `shape="wide"` equals `tidy=False`
- Naming things: All things "Scalar" are now called "Timeseries", with settings prefix `ts_`
- Drop some unnecessary enums
- Rename Environment Agency to ea in subspace

### Fixed

- CLI: Fix cli arguments with multiple items separated by comma (,)
- Fix fileindex/metaindex for DWD Observation
- DOCS: Fix precipitation height unit
- DOCS: Fix examples with "recent" period

## [0.53.0] - 2023-02-07

### Added

- CLI: Add command line options `wetterdienst --version` and `wetterdienst -v` to display version number

### Changed

- SCALAR: Change tidy option to be set to True if multiple different entire datasets are queried (in accordance with exporting results to json where multiple DataFrames are concatenated)
- Further cleanups
- Change Settings to be provided via initialization instead of having a singleton

## [0.52.0] - 2023-01-19

### Added

- Add Geosphere Observation implementation for Austrian meteorological data

### Changed

- RADAR: Clean up code and merge access module into api

### Fixed

- DWD MOSMIX: Fix parsing station list
- DWD MOSMIX: Fix converting degrees minutes to decimal degrees within the stations list. The previous method did not produce correct results on negative lat/lon values.

## [0.51.0] - 2023-01-01

### Added

- Update wetterdienst explorer with clickable stations and slightly changed layout

### Fixed

- Improve radar tests and certain dict comparisons
- Fix problem with numeric column names in method gain_of_value_pairs

## [0.50.0] - 2022-12-03

### Added

- Interpolation/Summary: Now the queried point can be an existing station laying on the border of the polygon that it's being checked against
- UI: Add interpolate/summarize methods as subspaces

### Changed

- Geo: Change function signatures to use latlon tuple instead of latitude and longitude
- Geo: Enable querying station id instead of latlon within interpolate and summarize
- Geo: Allow using values of nearby stations instead of interpolated values

### Fixed

- Fix timezone related problems when creating full date range

## [0.49.0] - 2022-11-28

### Added

- Add NOAA NWS Observation API
- Add Eaufrance Hubeau API for French river data (flow, stage)

### Fixed

- Fix bug where duplicates of acquired data would be dropped regarding only the date but not the parameter
- Fix NOAA GHCN access issues with timezones and empty data

## [0.48.0] - 2022-11-11

### Added

- Add example to dump DWD climate summary observations in zarr with help of xarray

### Fixed

- Fix DWD Observation urban_pressure dataset access (again)

## [0.47.1] - 2022-10-23

### Fixed

- Fix DWD Observation urban_pressure dataset access

## [0.47.0] - 2022-10-14

### Added

- Add support for reading DWD Mosmix-L all stations files

## [0.46.0] - 2022-10-14

### Added

- Add summary of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

## [0.45.2] - 2022-10-11

### Fixed

- Make DwdMosmixRequest return data according to start and end date

## [0.45.1] - 2022-10-10

### Fixed

- Fix passing an empty DataFrame through unit conversion and ensure set of columns

## [0.45.0] - 2022-09-22

### Added

- Add interpolation of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

### Fixed

- Fix access of DWD Observation climate_urban datasets

## [0.44.0] - 2022-09-18

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Slightly adapt the conversion function to satisfy linter
- Adjust Docker images to fix build problems, now use python 3.10 as base
- Adjust NOAA sources to AWS as NCEI sources currently are not available
- Make explorer work again for all services setting up Period enum classes instead of single instances of Period for period base

### Fixed

- Fix parameter names:
  - we now use consistently INDEX instead of INDICATOR
  - index and form got mixed up with certain parameters, where actually index was measured/given but not the form
  - global radiation was mistakenly named radiation_short_wave_direct at certain points, now it is named correctly

## [0.43.0] - 2022-09-05

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Use lxml.iterparse to reduce memory consumption when parsing DWD Mosmix files
- Fix Settings object instantiation
- Change logging level for Settings.cache_disable to INFO

## [0.42.1] - 2022-08-25

### Fixed

- Fix DWD Mosmix station locations

## [0.42.0] - 2022-08-22

### Changed

- Move cache settings to core wetterdienst Settings object

### Fixed

- Fix two parameter names

## [0.41.1] - 2022-08-04

### Fixed

- Fix correct mapping of periods for solar daily data which should also have Period.HISTORICAL besides Period.RECENT

## [0.41.0] - 2022-07-24

### Fixed

- Fix passing through of empty dataframe when trying to convert units

## [0.40.0] - 2022-07-10

### Changed

- Update dependencies

## [0.39.0] - 2022-06-27

### Changed

- Update dependencies

## [0.38.0] - 2022-06-09

### Added

- Add DWD Observation 5 minute precipitation dataset
- Add test to compare actually provided DWD observation datasets with the ones we made available with wetterdienst

### Fixed

- Fix one particular dataset which was not correctly included in our DWD observations resolution-dataset-mapping

## [0.37.0] - 2022-06-06

### Fixed

- Fix EA hydrology access
- Update ECCC observation methods to acquire station listing

## [0.36.0] - 2022-05-31

### Fixed

- Fix using shared FSSPEC_CLIENT_KWARGS everywhere

## [0.35.0] - 2022-05-29

### Added

- Add option to skip empty stations (option tidy must be set)
- Add option to drop empty rows (value is NaN) (option tidy must be set)

## [0.34.0] - 2022-05-22

### Added

- Add UKs Environment Agency hydrology API

## [0.33.0] - 2022-05-14

### Fixed

- Fix acquisition of DWD weather phenomena data
- Set default encoding when reading data from DWD with pandas to 'latin1'
- Fix typo in `EcccObservationResolution`

## [0.32.4] - 2022-05-14

### Fixed

- Fix acquisition of historical DWD radolan data that comes in archives

## [0.32.3] - 2022-05-12

### Fixed

- Fix creation of empty DataFrame for missing station ids
- Fix creation of empty DataFrame for annual data

## [0.32.2] - 2022-05-10

### Fixed

- Revert ssl option

## [0.32.1] - 2022-05-09

### Fixed

- Circumvent DWD server ssl certificate problem by temporary removing ssl verification

## [0.32.0] - 2022-04-24

### Added

- Add implementation of WSV Pegelonline service

### Changed

- Clean up code at several places

### Fixed

- Fix ECCC observations access

## [0.31.1] - 2022-04-03

### Fixed

- Change integer dtypes in untidy format to float to prevent loosing information when converting units

## [0.31.0] - 2022-03-29

### Changed

- Improve integrity of dataset, parameter and unit enumerations with further tests
- Change source of hourly sunshine duration to dataset sun
- Change source of hourly total cloud cover (+indicator) to dataset cloudiness

## [0.30.1] - 2022-03-03

### Fixed

- Fix naming of sun dataset
- Fix DWD Observation monthly test

## [0.30.0] - 2022-02-27

### Fixed

- Fix monthly/annual data of DWD observations

## [0.29.0] - 2022-02-27

### Added

- Add datasets EXTREME_WIND (subdaily) and MORE_WEATHER_PHENOMENA (daily)
- Add support for Python 3.10

### Changed

- Simplify parameters using only one enumeration for flattened and detailed parameters
- Rename dataset SUNSHINE_DURATION to SUN to avoid complications with similar named parameter and dataset
- Rename parameter VISIBILITY to VISIBILITY_RANGE

### Removed

- Drop Python 3.7 support

## [0.28.0] - 2022-02-19

### Added

- Extend explorer to use all implemented APIs

### Fixed

- Fix cli/restapi: return json and use NULL instead of NaN

## [0.27.0] - 2022-02-16

### Added

- Add support for Python 3.10

### Fixed

- Fix missing station ids within values result
- Add details about time interval for NOAA GHCN stations
- Fix falsely calculated station distances

### Removed

- Drop support for Python 3.7

## [0.26.0] - 2022-02-06

### Added

- Add Wetterdienst.Settings to manage general settings like tidy, humanize,...
- Instead of "kind" use "network" attribute to differ between different data products of a provider

### Changed

- Rename DWD forecast to mosmix

### Fixed

- Change data source of NOAA GHCN after problems with timeouts when reaching the server
- Fix problem with timezone conversion when having dates that are already timezone aware

## [0.25.1] - 2022-01-30

### Fixed

- Fix cli error with upgraded click ^8.0 where default False would be converted to "False"

## [0.25.0] - 2022-01-30

### Fixed

- Fix access to ECCC stations listing using Google Drive storage
- Remove/replace caching entirely by fsspec (+monkeypatch)
- Fix bug with DWD intervals

## [0.24.0] - 2022-01-24

### Added

- Add NOAA GHCN API

### Fixed

- Fix radar index by filtering out bz2 files

## [0.23.0] - 2021-11-21

### Fixed

- Add missing positional dataset argument for _create_empty_station_parameter_df
- Timestamps of 1 minute / 10 minutes DWD data now have a gap hour at the end of year 1999 due to timezone shifts

## [0.22.0] - 2021-10-01

### Added

- Introduce core Parameter enum with fixed set of parameter names. Several parameters may have been renamed!
- Add FSSPEC_CLIENT_KWARGS variable at wetterdienst.util.cache for passing extra settings to fsspec request client

## [0.21.0] - 2021-09-10

### Changed

- Start migrating from `dogpile.cache` to `filesystem_spec`

## [0.20.4] - 2021-08-07

### Added

- Enable selecting a parameter precisely from a dataset by passing a tuple like [("precipitation_height", "kl")] or [("precipitation_height", "precipitation_more")], or for cli/restapi use "precipitation_height/kl"
- Rename `wetterdienst show` to `wetterdienst info`, make version accessible via CLI with `wetterdienst version`

### Fixed

- Bug when querying an entire DWD dataset for 10_minutes/1_minute resolution without providing start_date/end_date, which results in the interval of the request being None
- Test of restapi with recent period
- Get rid of pandas performance warning from DWD Mosmix data

## [0.20.3] - 2021-07-15

### Fixed

- Bugfix acquisition of DWD radar data
- Adjust DWD radar composite parameters to new index

## [0.20.2] - 2021-06-26

### Fixed

- Bugfix tidy method for DWD observation data

## [0.20.1] - 2021-06-26

### Changed

- Update readme on sandbox developer installation

### Fixed

- Bugfix show method

## [0.20.0] - 2021-06-23

### Added

- Change cli base to click
- Add support for wetterdienst core API in cli and restapi
- Export: Use InfluxDBClient instead of DataFrameClient and improve connection handling with InfluxDB 1.x
- Export: Add support for InfluxDB 2.x
- Add show() method with basic information on the wetterdienst instance

### Fixed

- Fix InfluxDB export by skipping empty fields

## [0.19.0] - 2021-05-14

### Changed

- Make tidy method a abstract core method of Values class

### Fixed

- Fix DWD Mosmix generator to return all contained dataframes

## [0.18.0] - 2021-05-04

### Added

- Add origin and si unit mappings to services
- Use argument "si_units" in request classes to convert origin units to si, set to default
- Improve caching behaviour by introducing optional `WD_CACHE_DIR` and `WD_CACHE_DISABLE` environment variables. Thanks, @meteoDaniel!
- Add baseline test for ECCC observations
- Add DWD Observation hourly moisture to catalogue

## [0.17.0] - 2021-04-08

### Added

- Add capability to export data to Zarr format
- Add Wetterdienst Explorer UI. Thanks, @meteoDaniel!
- Add MAC ARM64 support with dependency restrictions
- Add support for stations filtering via bbox and name
- Add support for units in distance filtering

### Changed

- Rename station_name to name
- Rename filter methods to .filter_by_station_id and .filter_by_name, use same convention for bbox, filter_by_rank (previously nearby_number), filter_by_distance (nearby_distance)

### Fixed

- Radar: Verify HDF5 responses instead of returning invalid data
- Mosmix: Use cached stations to improve performance

## [0.16.1] - 2021-03-31

### Changed

- Make .discover return lowercase parameters and datasets

## [0.16.0] - 2021-03-29

### Added

- Add capability to export to Feather- and Parquet-files to I/O subsystem
- Add `--reload` parameter to `wetterdienst restapi` for supporting development
- Add Environment and Climate Change Canada API

### Changed

- Use direct mapping to get a parameter set for a parameter
- Rename DwdObservationParameterSet to DwdObservationDataset as well as corresponding columns
- Merge metadata access into Request
- Repair CLI and I/O subsystem
- Improve spreadsheet export
- Increase I/O subsystem test coverage
- Make all DWD observation field names lowercase
- Make all DWD forecast (mosmix) field names lowercase
- Rename humanize_parameters to humanize and tidy_data to tidy

### Deprecated

- Deprecate support for Python 3.6

### Fixed

- Radar: Use OPERA as data source for improved list of radar sites

## [0.15.0] - 2021-03-07

### Added

- Add StationsResult and ValuesResult to allow for new workflow and connect stations and values request
- Add accessor .values to Stations class to get straight to values for a request
- Add top-level API

### Fixed

- Fix issue with Mosmix station location

## [0.14.1] - 2021-02-21

### Fixed

- Fix date filtering of DWD observations, where accidentally an empty dataframe was returned

## [0.14.0] - 2021-02-05

### Added

- DWD: Add missing radar site "Emden" (EMD, wmo=10204)

### Changed

- Change key STATION_HEIGHT to HEIGHT, LAT to LATITUDE, LON to LONGITUDE
- Rename "Data" classes to "Values"
- Make arguments singular

### Fixed

- Mosmix stations: fix longitudes/latitudes to be decimal degrees (before they were degrees and minutes)

## [0.13.0] - 2021-01-21

### Added

- Create general Resolution and Period enumerations that can be used anywhere
- Create a full dataframe even if no values exist at requested time
- Add further attributes to the class structure
- Make dates timezone aware
- Restrict dates to isoformat

## [0.12.1] - 2020-12-29

### Fixed

- Fix 10minutes file index interval range by adding timezone information

## [0.12.0] - 2020-12-23

### Changed

- Move more functionality into core classes
- Add more attributes to the core e.g. source and timezone
- Make dates of internal data timezone aware, set start date and end date to UTC
- Add issue date to Mosmix class that actually refers to the Mosmix run instead of start date and end date
- Use Result object for every data related return
- In accordance with typical naming conventions, DWDObservationSites is renamed to DWDObservationStations, the same is applied to DWDMosmixSites
- The name ELEMENT is removed and replaced by parameter while the actual parameter set e.g. CLIMATE_SUMMARY is now found under PARAMETER_SET

### Removed

- Remove StorageAdapter and its dependencies
- Methods self.collect_data() and self.collect_safe() are replaced by self.query() and self.all() and will deprecate at some point

## [0.11.1] - 2020-12-10

### Fixed

- Bump `h5py` to version 3.1.0 in order to satisfy installation on Python 3.9

## [0.11.0] - 2020-12-04

### Added

- Upgrade Docker images to Python 3.8.6
- Radar data: Add non-RADOLAN data acquisition

### Changed

- Change wherever possible column type to category
- Increase efficiency by downloading only historical files with overlapping dates if start_date and end_date are given
- Use periods dynamically depending on start and end date

### Fixed

- InfluxDB export: Fix export in non-tidy format (#230). Thanks, @wetterfrosch!
- InfluxDB export: Use "quality" column as tag (#234). Thanks, @wetterfrosch!
- InfluxDB export: Use a batch size of 50000 to handle larger amounts of data (#235). Thanks, @wetterfrosch!
- Update radar examples to use `wradlib>=1.9.0`. Thanks, @kmuehlbauer!
- Fix inconsistency within 1 minute precipitation data where historical files have more columns
- Improve DWD PDF parser to extract quality information and select language. Also, add an example at `example/dwd_describe_fields.py` as well as respective documentation.
- Move intermediate storage of HDF out of data collection
- Fix bug with date filtering for empty/no station data for a given parameter

## [0.10.1] - 2020-11-14

### Fixed

- Upgrade to dateparser-1.0.0. Thanks, @steffen746, @noviluni and @Gallaecio! This fixes a problem with timezones on Windows. The reason is that Windows has no zoneinfo database and `tzlocal` switched from `pytz` to `tzinfo`. https://github.com/earthobservations/wetterdienst/issues/222

## [0.10.0] - 2020-10-26

### Added

- CLI: Obtain "--tidy" argument from command line
- Extend MOSMIX support to equal the API of observations
- DWDObservationData now also takes an individual parameter independent of the pre-configured DWD datasets by using DWDObservationParameter or similar names e.g. "precipitation_height"
- Newly introduced coexistence of DWDObservationParameter and DWDObservationParameterSet to address parameter sets as well as individual parameters

### Changed

- DWDObservationSites now filters for those stations which have a file on the server
- Imports are changed to submodule thus now one has to import everything from wetterdienst.dwd
- Renaming of time_resolution to resolution, period_type to period, several other relabels

## [0.9.0] - 2020-10-09

### Added

- Rename `DWDStationRequest` to `DWDObservationData`
- Add `DWDObservationSites` API wrapper to acquire station information
- Move `discover_climate_observations` to `DWDObservationMetadata.discover_parameters`
- Add PDF-based `DWDObservationMetadata.describe_fields()`

### Changed

- Large refactoring
- Make period type in DWDObservationData and cli optional
- Activate SQL querying again by using DuckDB 0.2.2.dev254. Thanks, @Mytherin!

### Fixed

- Fix coercion of integers with nans
- Fix problem with storing IntegerArrays in HDF

## [0.8.0] - 2020-09-25

### Added

- Add TTL-based persistent caching using dogpile.cache
- Add `example/radolan.py` and adjust documentation
- Export dataframe to different data sinks like SQLite, DuckDB, InfluxDB and CrateDB
- Query results with SQL, based on in-memory DuckDB
- Split get_nearby_stations into two functions, get_nearby_stations_by_number and get_nearby_stations_by_distance
- Add MOSMIX client and parser. Thanks, @jlewis91!
- Add basic HTTP API

## [0.7.0] - 2020-09-16

### Added

- Add test for Jupyter notebook
- Add function to discover available climate observations (time resolution, parameter, period type)
- Make the CLI work again and add software tests to prevent future havocs
- Use Sphinx Material theme for documentation

### Fixed

- Fix typo in enumeration for TimeResolution.MINUTES_10

## [0.6.0] - 2020-09-07

### Changed

- Enhance usage of get_nearby_stations to check for availability
- Output of get_nearby_stations is now a slice of meta_data DataFrame output

## [0.5.0] - 2020-08-27

### Added

- Add RADOLAN support
- Change module and function naming in accordance with RADOLAN

## [0.4.0] - 2020-08-03

### Added

- Extend DWDObservationData to take multiple parameters as request
- Add documentation at readthedocs.io
- \[cli\] Adjust methods to work with multiple parameters

## [0.3.0] - 2020-07-26

### Added

- Add option for data collection to tidy the DataFrame (properly reshape) with the "tidy_data" keyword and set it to be used as default

### Changed

- Establish code style black
- Setup nox session that can be used to run black via nox -s black for one of the supported Python versions

### Fixed

- Fix integer type casting for cases with nans in the column/series
- Fix humanizing of column names for tidy data

## [0.2.0] - 2020-07-23

### Added

- \[cli\] Add geospatial filtering by distance.
- \[cli\] Filter stations by station identifiers.
- \[cli\] Add GeoJSON output format for station data.
- Improvements to parsing high resolution data by setting specific datetime formats and changing to concurrent.futures

### Changed

- Change column name mapping to more explicit one with columns being individually addressable
- Add full column names for every individual parameter
- More specific type casting for integer fields and string fields

### Fixed

- Fix na value detection for cases where cells have leading and trailing whitespace

## [0.1.1] - 2020-07-05

### Added

- \[cli\] Add geospatial filtering by number of nearby stations.
- Simplify release pipeline
- Small updates to readme

### Changed

- Parameter, time resolution and period type can now also be passed as strings of the enumerations e.g. "climate_summary" or "CLIMATE_SUMMARY" for Parameter.CLIMATE_SUMMARY
- Enable selecting nearby stations by distance rather than by number of stations

### Fixed

- Change updating "parallel" argument to be done after parameter parsing to prevent mistakenly not found parameter
- Remove find_all_match_strings function and extract functionality to individual operations

## [0.1.0] - 2020-07-02

### Added

- Initial release
- Update README.md
- Update example notebook
- Add Gh Action for release
- Rename library

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/v0.116.0...HEAD
[0.116.0]: https://github.com/earthobservations/wetterdienst/compare/v0.115.0...v0.116.0
[0.115.0]: https://github.com/earthobservations/wetterdienst/compare/v0.114.3...v0.115.0
[0.114.3]: https://github.com/earthobservations/wetterdienst/compare/v0.114.2...v0.114.3
[0.114.2]: https://github.com/earthobservations/wetterdienst/compare/v0.114.1...v0.114.2
[0.114.1]: https://github.com/earthobservations/wetterdienst/compare/v0.114.0...v0.114.1
[0.114.0]: https://github.com/earthobservations/wetterdienst/compare/v0.113.0...v0.114.0
[0.113.0]: https://github.com/earthobservations/wetterdienst/compare/v0.112.0...v0.113.0
[0.112.0]: https://github.com/earthobservations/wetterdienst/compare/v0.111.0...v0.112.0
[0.111.0]: https://github.com/earthobservations/wetterdienst/compare/v0.110.0...v0.111.0
[0.110.0]: https://github.com/earthobservations/wetterdienst/compare/v0.109.0...v0.110.0
[0.109.0]: https://github.com/earthobservations/wetterdienst/compare/v0.108.0...v0.109.0
[0.108.0]: https://github.com/earthobservations/wetterdienst/compare/v0.107.0...v0.108.0
[0.107.0]: https://github.com/earthobservations/wetterdienst/compare/v0.106.0...v0.107.0
[0.106.0]: https://github.com/earthobservations/wetterdienst/compare/v0.105.0...v0.106.0
[0.105.0]: https://github.com/earthobservations/wetterdienst/compare/v0.104.0...v0.105.0
[0.104.0]: https://github.com/earthobservations/wetterdienst/compare/v0.103.0...v0.104.0
[0.103.0]: https://github.com/earthobservations/wetterdienst/compare/v0.102.0...v0.103.0
[0.102.0]: https://github.com/earthobservations/wetterdienst/compare/v0.101.0...v0.102.0
[0.101.0]: https://github.com/earthobservations/wetterdienst/compare/v0.100.0...v0.101.0
[0.100.0]: https://github.com/earthobservations/wetterdienst/compare/v0.99.0...v0.100.0
[0.99.0]: https://github.com/earthobservations/wetterdienst/compare/v0.98.0...v0.99.0
[0.98.0]: https://github.com/earthobservations/wetterdienst/compare/v0.97.0...v0.98.0
[0.97.0]: https://github.com/earthobservations/wetterdienst/compare/v0.96.0...v0.97.0
[0.96.0]: https://github.com/earthobservations/wetterdienst/compare/v0.95.1...v0.96.0
[0.95.1]: https://github.com/earthobservations/wetterdienst/compare/v0.95.0...v0.95.1
[0.95.0]: https://github.com/earthobservations/wetterdienst/compare/v0.94.0...v0.95.0
[0.94.0]: https://github.com/earthobservations/wetterdienst/compare/v0.93.0...v0.94.0
[0.93.0]: https://github.com/earthobservations/wetterdienst/compare/v0.92.0...v0.93.0
[0.92.0]: https://github.com/earthobservations/wetterdienst/compare/v0.91.0...v0.92.0
[0.91.0]: https://github.com/earthobservations/wetterdienst/compare/v0.90.0...v0.91.0
[0.90.0]: https://github.com/earthobservations/wetterdienst/compare/v0.89.0...v0.90.0
[0.89.0]: https://github.com/earthobservations/wetterdienst/compare/v0.88.0...v0.89.0
[0.88.0]: https://github.com/earthobservations/wetterdienst/compare/v0.87.0...v0.88.0
[0.87.0]: https://github.com/earthobservations/wetterdienst/compare/v0.86.0...v0.87.0
[0.86.0]: https://github.com/earthobservations/wetterdienst/compare/v0.85.0...v0.86.0
[0.85.0]: https://github.com/earthobservations/wetterdienst/compare/v0.84.0...v0.85.0
[0.84.0]: https://github.com/earthobservations/wetterdienst/compare/v0.83.0...v0.84.0
[0.83.0]: https://github.com/earthobservations/wetterdienst/compare/v0.82.0...v0.83.0
[0.82.0]: https://github.com/earthobservations/wetterdienst/compare/v0.81.0...v0.82.0
[0.81.0]: https://github.com/earthobservations/wetterdienst/compare/v0.80.0...v0.81.0
[0.80.0]: https://github.com/earthobservations/wetterdienst/compare/v0.79.0...v0.80.0
[0.79.0]: https://github.com/earthobservations/wetterdienst/compare/v0.78.0...v0.79.0
[0.78.0]: https://github.com/earthobservations/wetterdienst/compare/v0.77.1...v0.78.0
[0.77.1]: https://github.com/earthobservations/wetterdienst/compare/v0.77.0...v0.77.1
[0.77.0]: https://github.com/earthobservations/wetterdienst/compare/v0.76.1...v0.77.0
[0.76.1]: https://github.com/earthobservations/wetterdienst/compare/v0.76.0...v0.76.1
[0.76.0]: https://github.com/earthobservations/wetterdienst/compare/v0.75.0...v0.76.0
[0.75.0]: https://github.com/earthobservations/wetterdienst/compare/v0.74.0...v0.75.0
[0.74.0]: https://github.com/earthobservations/wetterdienst/compare/v0.73.0...v0.74.0
[0.73.0]: https://github.com/earthobservations/wetterdienst/compare/v0.72.0...v0.73.0
[0.72.0]: https://github.com/earthobservations/wetterdienst/compare/v0.71.0...v0.72.0
[0.71.0]: https://github.com/earthobservations/wetterdienst/compare/v0.70.0...v0.71.0
[0.70.0]: https://github.com/earthobservations/wetterdienst/compare/v0.69.0...v0.70.0
[0.69.0]: https://github.com/earthobservations/wetterdienst/compare/v0.68.0...v0.69.0
[0.68.0]: https://github.com/earthobservations/wetterdienst/compare/v0.67.0...v0.68.0
[0.67.0]: https://github.com/earthobservations/wetterdienst/compare/v0.66.1...v0.67.0
[0.66.1]: https://github.com/earthobservations/wetterdienst/compare/v0.66.0...v0.66.1
[0.66.0]: https://github.com/earthobservations/wetterdienst/compare/v0.65.0...v0.66.0
[0.65.0]: https://github.com/earthobservations/wetterdienst/compare/v0.64.0...v0.65.0
[0.64.0]: https://github.com/earthobservations/wetterdienst/compare/v0.63.0...v0.64.0
[0.63.0]: https://github.com/earthobservations/wetterdienst/compare/v0.62.0...v0.63.0
[0.62.0]: https://github.com/earthobservations/wetterdienst/compare/v0.61.0...v0.62.0
[0.61.0]: https://github.com/earthobservations/wetterdienst/compare/v0.60.0...v0.61.0
[0.60.0]: https://github.com/earthobservations/wetterdienst/compare/v0.59.3...v0.60.0
[0.59.3]: https://github.com/earthobservations/wetterdienst/compare/v0.59.2...v0.59.3
[0.59.2]: https://github.com/earthobservations/wetterdienst/compare/v0.59.1...v0.59.2
[0.59.1]: https://github.com/earthobservations/wetterdienst/compare/v0.59.0...v0.59.1
[0.59.0]: https://github.com/earthobservations/wetterdienst/compare/v0.58.1...v0.59.0
[0.58.1]: https://github.com/earthobservations/wetterdienst/compare/v0.58.0...v0.58.1
[0.58.0]: https://github.com/earthobservations/wetterdienst/compare/v0.57.1...v0.58.0
[0.57.1]: https://github.com/earthobservations/wetterdienst/compare/v0.57.0...v0.57.1
[0.57.0]: https://github.com/earthobservations/wetterdienst/compare/v0.56.2...v0.57.0
[0.56.2]: https://github.com/earthobservations/wetterdienst/compare/v0.56.1...v0.56.2
[0.56.1]: https://github.com/earthobservations/wetterdienst/compare/v0.56.0...v0.56.1
[0.56.0]: https://github.com/earthobservations/wetterdienst/compare/v0.55.2...v0.56.0
[0.55.2]: https://github.com/earthobservations/wetterdienst/compare/v0.55.1...v0.55.2
[0.55.1]: https://github.com/earthobservations/wetterdienst/compare/v0.55.0...v0.55.1
[0.55.0]: https://github.com/earthobservations/wetterdienst/compare/v0.54.1...v0.55.0
[0.54.1]: https://github.com/earthobservations/wetterdienst/compare/v0.54.0...v0.54.1
[0.54.0]: https://github.com/earthobservations/wetterdienst/compare/v0.53.0...v0.54.0
[0.53.0]: https://github.com/earthobservations/wetterdienst/compare/v0.52.0...v0.53.0
[0.52.0]: https://github.com/earthobservations/wetterdienst/compare/v0.51.0...v0.52.0
[0.51.0]: https://github.com/earthobservations/wetterdienst/compare/v0.50.0...v0.51.0
[0.50.0]: https://github.com/earthobservations/wetterdienst/compare/v0.49.0...v0.50.0
[0.49.0]: https://github.com/earthobservations/wetterdienst/compare/v0.48.0...v0.49.0
[0.48.0]: https://github.com/earthobservations/wetterdienst/compare/v0.47.1...v0.48.0
[0.47.1]: https://github.com/earthobservations/wetterdienst/compare/v0.47.0...v0.47.1
[0.47.0]: https://github.com/earthobservations/wetterdienst/compare/v0.46.0...v0.47.0
[0.46.0]: https://github.com/earthobservations/wetterdienst/compare/v0.45.2...v0.46.0
[0.45.2]: https://github.com/earthobservations/wetterdienst/compare/v0.45.1...v0.45.2
[0.45.1]: https://github.com/earthobservations/wetterdienst/compare/v0.45.0...v0.45.1
[0.45.0]: https://github.com/earthobservations/wetterdienst/compare/v0.44.0...v0.45.0
[0.44.0]: https://github.com/earthobservations/wetterdienst/compare/v0.43.0...v0.44.0
[0.43.0]: https://github.com/earthobservations/wetterdienst/compare/v0.42.1...v0.43.0
[0.42.1]: https://github.com/earthobservations/wetterdienst/compare/v0.42.0...v0.42.1
[0.42.0]: https://github.com/earthobservations/wetterdienst/compare/v0.41.1...v0.42.0
[0.41.1]: https://github.com/earthobservations/wetterdienst/compare/v0.41.0...v0.41.1
[0.41.0]: https://github.com/earthobservations/wetterdienst/compare/v0.40.0...v0.41.0
[0.40.0]: https://github.com/earthobservations/wetterdienst/compare/v0.39.0...v0.40.0
[0.39.0]: https://github.com/earthobservations/wetterdienst/compare/v0.38.0...v0.39.0
[0.38.0]: https://github.com/earthobservations/wetterdienst/compare/v0.37.0...v0.38.0
[0.37.0]: https://github.com/earthobservations/wetterdienst/compare/v0.36.0...v0.37.0
[0.36.0]: https://github.com/earthobservations/wetterdienst/compare/v0.35.0...v0.36.0
[0.35.0]: https://github.com/earthobservations/wetterdienst/compare/v0.34.0...v0.35.0
[0.34.0]: https://github.com/earthobservations/wetterdienst/compare/v0.33.0...v0.34.0
[0.33.0]: https://github.com/earthobservations/wetterdienst/compare/v0.32.4...v0.33.0
[0.32.4]: https://github.com/earthobservations/wetterdienst/compare/v0.32.3...v0.32.4
[0.32.3]: https://github.com/earthobservations/wetterdienst/compare/v0.32.2...v0.32.3
[0.32.2]: https://github.com/earthobservations/wetterdienst/compare/v0.32.1...v0.32.2
[0.32.1]: https://github.com/earthobservations/wetterdienst/compare/v0.32.0...v0.32.1
[0.32.0]: https://github.com/earthobservations/wetterdienst/compare/v0.31.1...v0.32.0
[0.31.1]: https://github.com/earthobservations/wetterdienst/compare/v0.31.0...v0.31.1
[0.31.0]: https://github.com/earthobservations/wetterdienst/compare/v0.30.1...v0.31.0
[0.30.1]: https://github.com/earthobservations/wetterdienst/compare/v0.30.0...v0.30.1
[0.30.0]: https://github.com/earthobservations/wetterdienst/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/earthobservations/wetterdienst/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/earthobservations/wetterdienst/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/earthobservations/wetterdienst/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/earthobservations/wetterdienst/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/earthobservations/wetterdienst/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/earthobservations/wetterdienst/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/earthobservations/wetterdienst/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/earthobservations/wetterdienst/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/earthobservations/wetterdienst/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/earthobservations/wetterdienst/compare/v0.20.4...v0.21.0
[0.20.4]: https://github.com/earthobservations/wetterdienst/compare/v0.20.3...v0.20.4
[0.20.3]: https://github.com/earthobservations/wetterdienst/compare/v0.20.2...v0.20.3
[0.20.2]: https://github.com/earthobservations/wetterdienst/compare/v0.20.1...v0.20.2
[0.20.1]: https://github.com/earthobservations/wetterdienst/compare/v0.20.0...v0.20.1
[0.20.0]: https://github.com/earthobservations/wetterdienst/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/earthobservations/wetterdienst/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/earthobservations/wetterdienst/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/earthobservations/wetterdienst/compare/v0.16.1...v0.17.0
[0.16.1]: https://github.com/earthobservations/wetterdienst/compare/v0.16.0...v0.16.1
[0.16.0]: https://github.com/earthobservations/wetterdienst/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/earthobservations/wetterdienst/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/earthobservations/wetterdienst/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/earthobservations/wetterdienst/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/earthobservations/wetterdienst/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/earthobservations/wetterdienst/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/earthobservations/wetterdienst/compare/v0.11.1...v0.12.0
[0.11.1]: https://github.com/earthobservations/wetterdienst/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/earthobservations/wetterdienst/compare/v0.10.1...v0.11.0
[0.10.1]: https://github.com/earthobservations/wetterdienst/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/earthobservations/wetterdienst/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/earthobservations/wetterdienst/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/earthobservations/wetterdienst/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/earthobservations/wetterdienst/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/earthobservations/wetterdienst/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/earthobservations/wetterdienst/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/earthobservations/wetterdienst/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/earthobservations/wetterdienst/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/earthobservations/wetterdienst/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/earthobservations/wetterdienst/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/v0.1.0