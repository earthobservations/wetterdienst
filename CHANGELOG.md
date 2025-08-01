# Changelog

## Development

## Feature
- Make humidity interpolatable
- Improve interpolation configuration
- Set missing `return_dtype` in fileindex function

### Fix
- Parse parameters only if any are given
- Fix export for interpolated values to csv
- Round timestamps of hourly solar data to nearest hour

## 0.110.0 - 2025-07-23

### Feature
- Drop upper version pins for fsspec and tzdata
- Make retry of `download_file` more robust
- Overhaul docs switching to `sphinx` and `myst-parser`
- Improve exception handling in restapi
- Improve download of files

### Fix
- Export: Fix influx tags and fields
- \[NOAA GHCN hourly\] Fix metadata creation
- Include resolution column in wide format
- Disallow `polars==1.31.0` due to issues

### Refactor
- Introduce `wetterdienst.model`, streamline others

### Chore
- Bump minimum kaleido version to `0.2.2`

## 0.109.0 - 2025-06-03

### Feature
- Split `coordinates` and `bbox` into separate arguments
- Bump dependencies

## 0.108.0 - 2025-04-25

### Feature
- Improve restapi look and add impressum
- Use dataclass everywhere
- Refactor query method
- Adjust retry of function `download_file`
- Restapi: Add uvloop and httptools for speed via `uvicorn[standard]`

### Fix
- Fix numerous radar tests

## 0.107.0 - 2025-03-25

### Refactor
- Refactor `download_file`

### Fix
- Fix false attribute parsing by pydantic model in cli
- Fix datetime parsing for generic radar data

## 0.106.0 - 2025-03-05

### Fix
- Improve parameter unpacking in `ParameterSearch.parse`
- Fix docker manifest

## 0.105.0 - 2025-03-01

### Feature
- Add user agent to default `fsspec_client_kwargs`
- Adjust apis to track resolution and dataset
  This also allows querying data for diffrent resolutions and datasets in one request

### Refactor
- Improve date parsing across multiple apis
- Cleanup docker image
- Improve numerous apis

### Fix
- \[WSV Pegel\] Fix characteristic values and improve date parsing

## 0.104.0 - 2025-02-15

### Refactor
- Reduce the margin of the stations plot
- Make pydantic models for uis simpler
- Migrate from `sklearn+numpy` to `pyarrow` for location querying
- Remove command from Docker file
- Improve workflow for Docker
- Get rid of columns enumeration
- \[NOAA GHCN\] Improve date parsing and other fixes

## 0.103.0 - 2025-02-02

### Feature
- Stripes: Replace matplotlib by plotly
- Explorer: Add download button for plot
- Split up plotting extras into `plotting` and `matplotlib`
- Interpolation/Summary: Add dataset to DataFrame
- Add plotting capabilities

### Refactor
- Update docker image extras

### Chore
- Remove unused cachetools dependency
- Make fastexcel a polars extra
- Drop click-params dependency
- Make pyarrow a polars extra

### Fix
- Fix benchmark code

## 0.102.0 - 2025-01-17

### Feature
- Add cmd to docker image

### Refactor
- Use `to_list()[0]` instead of `first()`

## 0.101.0 - 2025-01-13

### Feature
- Move more details into `MetadataModel`

### Refactor
- \[DWD Obs\] Make the download function more flexible using threadpool
- \[DWD Obs\] Cleanup parser function
- \[DWD Obs\] Improve fileindex and metaindex

### Fix
- \[DWD Obs\] Reduce unnecessary file index calls during retrieval of data for stations with multiple files

## 0.100.0 - 2025-01-06 

### Feature
- Add logo for restapi
- [Breaking] Add dedicated unit converter
  
  Attention: Many units are changed to be more consistent with typical meteorological units. We now use `°C` for 
  temperatures. Also, length units are now separated in `length_short`, `length_medium` and `length_long` to get more
  reasonable decimals. Fore more information, see the new units chapter (usage/units) in the documentation.

### Refactor
- Add reasonable upper bounds for dependencies

### Fix
- Filter out invalid underscore prefixed files

## 0.99.0 - 2024-12-30

### Feature
- Add setting `ts_complete=False` that allows to prevent building a complete time series

### Refactor
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

## 0.98.0 - 2024-12-09

### Feature
- Add support for Python 3.13 and deprecate Python 3.9

### Refactor
- [Breaking] Add new metadata model: Requests now use `parameters` instead of `parameter` and `resolution` e.g. `parameters=[("daily", "kl")]` instead of `parameter="kl", resolution="daily"`

## 0.97.0 - 2024-10-06

### Fix
- DWD Road: Use correct 15 minute resolution

## 0.96.0 - 2024-10-04

### Refactor
- Bump polars to `>=1.0.0`
- Change `DWDMosmixValues` and `DWDDmoValues` to follow the core `_collect_station_parameter` method
- Allow only single issue retrieving with `DWDMosmixRequest` and `DWDDmoRequest`

## 0.95.1 - 2024-09-04

### Fix
- Fix `state` column in station list creation for DWD Observation

## 0.95.0 - 2024-08-27

### Refactor
- Make fastexcel non-optional
- Remove upper dependency bounds

## 0.94.0 - 2024-08-10

### Feature
- DWD Road: Add new station groups, log warning if no data is available, especially if the station group is one of the temporarily unavailable ones

### Fix
- Explorer: Fix DWD Mosmix request kwargs setup

## 0.93.0 - 2024-08-06

### Fix
- Fix multiple Geosphere parameter and unit enums
- Explorer: Fix wrap `(parameter, dataset)` in iterator
- Adjust parameter typing of apis

## 0.92.0 - 2024-07-31

### Refactor
- Rename parameters
  - units in parameter names are now directly following the number
  - temperature parameters now use meter instead of cm and also have a unit
  - e.g. TEMPERATURE_AIR_MEAN_2M, CLOUD_COVER_BETWEEN_2KM_TO_7KM, PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0MM_LAST_6H

### Fix
- Bump pyarrow version to <18
- Fix EaHydrology station list parsing
- Rename `EaHydrology` to `EAHydrology`
- Fix propagation of settings through `EAHydrology` values

## 0.91.0 - 2024-07-14

### Fix
- Fix DWD Road api

## 0.90.0 - 2024-07-14

### Refactor
- Bump `environs` to <12

### Fix
- Explorer: Fix json export

## 0.89.0 - 2024-07-03

### Fix
- EaHydrology: Fix date parsing
- Hubeau: Use correct frequency unit
- Fix group by unpack

## 0.88.0 - 2024-06-14

### Feature
- Allow passing `--listen` when running the explorer to specify the host and port

## 0.87.0 - 2024-06-06

### Refactor
- Rename warming stripes to climate stripes
- Add precipitation version
- Replace custom Settings class with pydantic model

## 0.86.0 - 2024-06-01

### Feature
- Interpolation/Summary: Require start and end date
- Enable interpolation and summarization for all services

### Fix
- Fix multiple issues with interpolation and summarization

## 0.85.0 - 2024-05-29

### Fix
- Fix `dropna` argument for DWD Mosmix and DMO
- Adjust DWD Mosmix and DMO kml reader to parse all parameters
- Fix `to_target(duckdb)` for stations
- Fix init of `DwdDmoRequest`

## 0.84.0 - 2024-05-15

### Fix
- Fix DWD Obs station list parsing again

## 0.83.0 - 2024-04-26

### Feature
- Allow `wide` shape with multiple datasets

## 0.82.0 - 2024-04-25

### Fix
- Adjust column specs for DWD Observation station listing
- Maintain order during deduplication
- Change threshold in `filter_by_name` to 0.0...1.0

## 0.81.0 - 2024-04-09

### Feature
- Warming stripes: Add option to enable/disable showing only active stations

## 0.80.0 - 2024-04-08

### Feature
- Migrate explorer to streamlit
- Explorer: Disable higher than daily resolutions for hosted version
- UI: Add warming stripes

## 0.79.0 - 2024-03-21

### Fix
- Fix parsing of DWD Observation stations where name contains a comma

## 0.78.0 - 2024-03-09

### Feature
- Docker: Install more extras

### Fix
- Cli/Restapi: Return empty values if no data is available

## 0.77.1 - 2024-03-08

### Fix
- Fix setting NOAA GHCN-h date to UTC

## 0.77.0 - 2024-03-08

### Refactor
- Refactor index caching -> Remove monkeypatch for fsspec

## 0.76.1 - 2024-03-03

### Fix
- NOAA GHCN Hourly: Fix date parsing

## 0.76.0 - 2024-03-02

### Feature
- Add NOAA GHCN Hourly API (also known as ISD)

## 0.75.0 - 2024-02-25

### Refactor
- Remove join outer workaround for polars and use `outer_coalesce` instead
- Allow duckdb for Python 3.12 again
- Update REST API index layout
- Bump polars to 0.20.10
- Docker: Bump to Python 3.12
- Docker: Reduce image size

## 0.74.0 - 2024-02-22

### Feature
- Restapi: Add health check endpoint

## 0.73.0 - 2024-02-09

### Refactor
- Set upper version bound for Python to 4.0

### Fix
- Add temporary workaround for bugged line in IMGW Hydrology station list
- Fix parsing of dates in NOAA GHCN api
- Make pandas optional

## 0.72.0 - 2024-01-13

### Feature
- Allow for passing kwargs to the `to_csv` method

### Fix
- Fix issue when using `force_ndarray_like=True` with pint UnitRegistry

## 0.71.0 - 2024-01-03

### Fix
- Fix issue with DWD DMO api

### Refactor
- CI: Add support for Python 3.12

## 0.70.0 - 2023-12-30

### Feature
- Docker: Enable interpolation in wetterdienst standard image

### Fix
- IMGW Meteorology: Drop workaround for mixed up station list to fix issue
- WSV Hydrology: Fix issue with station list characteristic values
- DWD Observation: Remove redundant replace empty string in parser
- NWS Observation: Read json data from bytes
- EA Hydrology: Read json data from bytes

### Refactor
- Replace partial with lambda in most places
- IMGW: Use ttl of 5 minutes for caching

## 0.69.0 - 2023-12-18

### Feature
- Restapi: Unify station parameter and add alias
- Interpolation: Make maximum station distance per parameter configurable via settings

### Fix
- Result: Convert date to string only if dataframe is not empty
- Restapi: Move restapi from /restapi to /api

## 0.68.0 - 2023-12-01

### Feature
- Add example for comparing Mosmix forecast and Observation data

### Fix
- Fix parsing of DWD Observation 1 minute precipitation data

## 0.67.0 - 2023-11-17

### Refactor
- [Breaking] Use start_date and end_date instead of from_date and to_date
- Use artificial station id for interpolation and summarization
- Rename taken station ids columns for interpolation and summarization

## 0.66.1 - 2023-11-08

### Fix
- Add workaround for issue with DWD Observation station lists

## 0.66.0 - 2023-11-07

### Fix
- Fix DWD DMO access again

### Feature
- Add lead time argument - one of short, long - for DWD DMO to address two versions of icon

### Refactor
- Rework dict-like export formats and tests with extensive support for typing
- Improve radar access
- Style restapi landing page
- Replace timezonefinder by tzfpy

## 0.65.0 - 2023-10-24

### Refactor
- Cleanup error handling
- Make cli work with DwdDmoRequest API
- Cleanup cli docs

### Fix
- Fix DWD Observation API for 5 minute data

## 0.64.0 - 2023-10-12

### Refactor
- Remove direct tzdata dependency
- Replace pandas read_fwf calls by polars substitutes

### Feature
- Export: Add support for InfluxDB 3.x

## 0.63.0 - 2023-10-08

### Feature
- [Streamlit] Add sideboard with settings
- [Streamlit] Add station information json
- [Streamlit] Add units to DataFrame view and plots
- [Streamlit] Add JSON download

### Fix
- Return data correctly sorted

## 0.62.0 - 2023-10-07

### Fix
- Fix multiple issues with DwdObservationRequest API

### Refactor
- Raise minimum version of polars to 0.19.6 due to breaking changes

## 0.61.0 - 2023-10-06

### Feature
- Make parameters TEMPERATURE_AIR_MAX_200 and TEMPERATURE_AIR_MIN_200 summarizable/interpolatable
- Add streamlit app for DWD climate stations
- Add sql query function to streamlit app

### Fix
- Fix imgw meteorology station list parsing
- Improve streamlit app plotting capabilities
- Fix DWD DMO api

## 0.60.0 - 2023-09-16

### Feature
- Add implementation for DWD DMO

## 0.59.3 - 2023-09-11

### Fix
- Fix DWD solar date string correction

## 0.59.2 - 2023-09-06

### Fix
- Fix documentation and unit conversion for Geosphere 10minute radiation data

## 0.59.1 - 2023-07-18

### Fix
- Fix Geosphere parameter names

## 0.59.0 - 2023-07-30

### Refactor
- Revise type hints for parameter and station_id

### Fix
- Fix Geosphere Observation parsing of dates in values -> thanks to @mhuber89 who discovered the bug and delivered a fix

## 0.58.1 - 2023-07-26

### Fix
- Fix bug with Geosphere parameter case

## 0.58.0 - 2023-07-10

### Feature
- Add retry to functions
- Add IMGW Hydrology API
- Add IMGW Meteorology API

### Refactor
- Rename FLOW to DISCHARGE and WATER_LEVEL to STAGE everywhere

## 0.57.1 - 2023-06-28

### Fix
- Fix pyarrow dependency

## 0.57.0 - 2023-05-15

### Refactor
- Backend: Migrate from pandas to polars

### Feature
- Sources: Add DWD Road Weather data

### Note
- Switching to Polars may cause breaking changes for certain user-space code heavily using pandas idioms, because Wetterdienst now returns a [Polars DataFrame](https://pola-rs.github.io/polars/py-polars/html/reference/dataframe/). If you absolutely must use a pandas DataFrame, you can cast the Polars DataFrame to pandas by using the `.to_pandas()` method.

## 0.56.2 - 2023-05-11

### Fix
- Fix Unit definition for RADIATION_GLOBAL

## 0.56.1 - 2023-05-10

### Fix
- Fix JOULE_PER_SQUARE_METER definition from kilojoule/m2 to joule/m2

## 0.56.0 - 2023-05-02

### Fix
- Update docker images
- Fix now and now_local attributes on core class

## 0.55.2 - 2023-04-20

### Fix
- Fix precipitation index interpolation

## 0.55.1 - 2023-04-17

### Fix
- Fix setting empty values in DWD observation data
- Fix DWD Radar composite path

## 0.55.0 - 2023-03-19

### Fix
- Explorer: Fix function calls

### Refactor
- Drop Python 3.8 support

## 0.54.1 - 2023-03-13

### Fix
- Fix DWD Observations 1 minute fileindex

## 0.54.0 - 2023-03-06

### Fix
- CLI: Fix cli arguments with multiple items separated by comma (,)
- Fix fileindex/metaindex for DWD Observation

### Refactor
- SCALAR: Improve handling skipping of empty stations, especially within .filter_by_rank function

### Fix
- DOCS: Fix precipitation height unit
- DOCS: Fix examples with "recent" period

### Refactor
- Make all parameter levels equal for all weather services to reduce complexity in code
- Change `tidy` option to `shape`, where `shape="long"` equals `tidy=True` and `shape="wide"` equals `tidy=False`

### Refactor
- Naming things: All things "Scalar" are now called "Timeseries", with settings prefix `ts_`
- Drop some unnecessary enums
- Rename Environment Agency to ea in subspace

## 0.53.0 - 2023-02-07

### Refactor
- SCALAR: Change tidy option to be set to True if multiple different entire datasets are queried
  This change is in accordance with exporting results to json where multiple DataFrames are concatenated.

### Feature
- CLI: Add command line options `wetterdienst --version` and `wetterdienst -v` to display version number

### Refactor
- Further cleanups
- Change Settings to be provided via initialization instead of having a singleton

## 0.52.0 - 2023-01-19

### Feature
- Add Geosphere Observation implementation for Austrian meteorological data

### Refactor
- RADAR: Clean up code and merge access module into api

### Fix
- DWD MOSMIX: Fix parsing station list
- DWD MOSMIX: Fix converting degrees minutes to decimal degrees within the stations list. The previous method did not produce correct results on negative lat/lon values.

## 0.51.0 - 2023-01-01

### Feature
- Update wetterdienst explorer with clickable stations and slighly changed layout

### Fix
- Improve radar tests and certain dict comparisons
- Fix problem with numeric column names in method gain_of_value_pairs

## 0.50.0 - 2022-12-03

### Feature
- Interpolation/Summary: Now the queried point can be an existing station laying on the border of the polygon that it's being checked against

### Refactor
- Geo: Change function signatures to use latlon tuple instead of latitude and longitude
- Geo: Enable querying station id instead of latlon within interpolate and summarize
- Geo: Allow using values of nearby stations instead of interpolated values

### Fix
- Fix timezone related problems when creating full date range

### Feature
- UI: Add interpolate/summarize methods as subspaces

## 0.49.0 - 2022-11-28

### Fix
- Fix bug where duplicates of acquired data would be dropped regarding only the date but not the parameter

### Feature
- Add NOAA NWS Observation API
- Add Eaufrance Hubeau API for French river data (flow, stage)

### Fix
- Fix NOAA GHCN access issues with timezones and empty data

## 0.48.0 - 2022-11-11

### Fix
- Fix DWD Observation urban_pressure dataset access (again)

### Feature
- Add example to dump DWD climate summary observations in zarr with help of xarray

## 0.47.1 - 2022-10-23

### Fix
- Fix DWD Observation urban_pressure dataset access

## 0.47.0 - 2022-10-14

### Feature
- Add support for reading DWD Mosmix-L all stations files

## 0.46.0 - 2022-10-14

### Feature
- Add summary of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

## 0.45.2 - 2022-10-11

### Fix
- Make DwdMosmixRequest return data according to start and end date

## 0.45.1 - 2022-10-10

### Fix
- Fix passing an empty DataFrame through unit conversion and ensure set of columns

## 0.45.0 - 2022-09-22

### Feature
- Add interpolation of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

### Fix
- Fix access of DWD Observation climate_urban datasets

## 0.44.0 - 2022-09-18

### Refactor
- Slightly adapt the conversion function to satisfy linter
- Fix parameter names:
  - we now use consistently INDEX instead of INDICATOR
  - index and form got mixed up with certain parameters, where actually index was measured/given but not the form
  - global radiation was mistakenly named radiation_short_wave_direct at certain points, now it is named correctly
- Adjust Docker images to fix build problems, now use python 3.10 as base
- Adjust NOAA sources to AWS as NCEI sources currently are not available
- Make explorer work again for all services setting up Period enum classes instead of single instances of Period for period base

## 0.43.0 - 2022-09-05

### Refactor
- Use lxml.iterparse to reduce memory consumption when parsing DWD Mosmix files
- Fix Settings object instantiation
- Change logging level for Settings.cache_disable to INFO

### Feature
- Add DWD Observation climate_urban datasets

## 0.42.1 - 2022-08-25

### Fix
- Fix DWD Mosmix station locations

## 0.42.0 - 2022-08-22

### Refactor
- Move cache settings to core wetterdienst Settings object

### Fix
- Fix two parameter names

## 0.41.1 - 2022-08-04

### Fix
- Fix correct mapping of periods for solar daily data which should also have Period.HISTORICAL besides Period.RECENT

## 0.41.0 - 2022-07-24

### Fix
- Fix passing through of empty dataframe when trying to convert units

## 0.40.0 - 2022-07-10

### Refactor
- Update dependencies

## 0.39.0 - 2022-06-27

### Refactor
- Update dependencies

## 0.38.0 - 2022-06-09

### Feature
- Add DWD Observation 5 minute precipitation dataset
- Add test to compare actually provided DWD observation datasets with the ones we made available with wetterdienst

### Fix
- Fix one particular dataset which was not correctly included in our DWD observations resolution-dataset-mapping

## 0.37.0 - 2022-06-06

### Fix
- Fix EA hydrology access
- Update ECCC observation methods to acquire station listing

## 0.36.0 - 2022-05-31

### Fix
- Fix using shared FSSPEC_CLIENT_KWARGS everywhere

## 0.35.0 - 2022-05-29

### Feature
- Add option to skip empty stations (option tidy must be set)
- Add option to drop empty rows (value is NaN) (option tidy must be set)

## 0.34.0 - 2022-05-22

### Feature
- Add UKs Environment Agency hydrology API

## 0.33.0 - 2022-05-14

### Fix
- Fix acquisition of DWD weather phenomena data
- Set default encoding when reading data from DWD with pandas to 'latin1'
- Fix typo in `EcccObservationResolution`

## 0.32.4 - 2022-05-14

### Fix
- Fix acquisition of historical DWD radolan data that comes in archives

## 0.32.3 - 2022-05-12

### Fix
- Fix creation of empty DataFrame for missing station ids
- Fix creation of empty DataFrame for annual data

## 0.32.2 - 2022-05-10

### Fix
- Revert ssl option

## 0.32.1 - 2022-05-09

### Fix
- Circumvent DWD server ssl certificate problem by temporary removing ssl verification

## 0.32.0 - 2022-04-24

### Feature
- Add implementation of WSV Pegelonline service

### Refactor
- Clean up code at several places

### Fix
- Fix ECCC observations access

## 0.31.1 - 2022-04-03

### Fix
- Change integer dtypes in untidy format to float to prevent loosing information when converting units

## 0.31.0 - 2022-03-29

### Refactor
- Improve integrity of dataset, parameter and unit enumerations with further tests
- Change source of hourly sunshine duration to dataset sun
- Change source of hourly total cloud cover (+indicator) to dataset cloudiness

## 0.30.1 - 2022-03-03

### Fix
- Fix naming of sun dataset
- Fix DWD Observation monthly test

## 0.30.0 - 2022-02-27

### Fix
- Fix monthly/annual data of DWD observations

## 0.29.0 - 2022-02-27

### Refactor
- Simplify parameters using only one enumeration for flattened and detailed parameters
- Rename dataset SUNSHINE_DURATION to SUN to avoid complications with similar named parameter and dataset
- Rename parameter VISIBILITY to VISIBILITY_RANGE

### Feature
- Add datasets EXTREME_WIND (subdaily) and MORE_WEATHER_PHENOMENA (daily)
- Add support for Python 3.10 and drop Python 3.7

## 0.28.0 - 2022-02-19

### Feature
- Extend explorer to use all implemented APIs

### Fix
- Fix cli/restapi: return json and use NULL instead of NaN

## 0.27.0 - 2022-02-16

### Fix
- Fix missing station ids within values result
- Add details about time interval for NOAA GHCN stations
- Fix falsely calculated station distances

### Feature
- Add support for Python 3.10, drop support for Python 3.7

## 0.26.0 - 2022-02-06

### Feature
- Add Wetterdienst.Settings to manage general settings like tidy, humanize,...
- Rename DWD forecast to mosmix
- Instead of "kind" use "network" attribute to differ between different data products of a provider

### Fix
- Change data source of NOAA GHCN after problems with timeouts when reaching the server
- Fix problem with timezone conversion when having dates that are already timezone aware

## 0.25.1 - 2022-01-30

### Fix
- Fix cli error with upgraded click ^8.0 where default False would be converted to "False"

## 0.25.0 - 2022-01-30

### Fix
- Fix access to ECCC stations listing using Google Drive storage
- Remove/replace caching entirely by fsspec (+monkeypatch)
- Fix bug with DWD intervals

## 0.24.0 - 2022-01-24

### Feature
- Add NOAA GHCN API

### Fix
- Fix radar index by filtering out bz2 files

## 0.23.0 - 2021-11-21

### Fix
- Add missing positional dataset argument for _create_empty_station_parameter_df
- Timestamps of 1 minute / 10 minutes DWD data now have a gap hour at the end of year 1999 due to timezone shifts

## 0.22.0 - 2021-10-01

### Refactor
- Introduce core Parameter enum with fixed set of parameter names. Several parameters may have been renamed!
- Add FSSPEC_CLIENT_KWARGS variable at wetterdienst.util.cache for passing extra settings to fsspec request client

## 0.21.0 - 2021-09-10

### Refactor
- Start migrating from ``dogpile.cache`` to ``filesystem_spec``

## 0.20.4 - 2021-08-07

### Feature
- Enable selecting a parameter precisely from a dataset by passing a tuple like [("precipitation_height", "kl")] or [("precipitation_height", "precipitation_more")], or for cli/restapi use "precipitation_height/kl"
- Rename ``wetterdienst show`` to ``wetterdienst info``, make version accessible via CLI with ``wetterdienst version``

### Fix
- Bug when querying an entire DWD dataset for 10_minutes/1_minute resolution without providing start_date/end_date, which results in the interval of the request being None
- Test of restapi with recent period
- Get rid of pandas performance warning from DWD Mosmix data

## 0.20.3 - 2021-07-15

### Fix
- Bugfix acquisition of DWD radar data
- Adjust DWD radar composite parameters to new index

## 0.20.2 - 2021-06-26

### Fix
- Bugfix tidy method for DWD observation data

## 0.20.1 - 2021-06-26

### Refactor
- Update readme on sandbox developer installation

### Fix
- Bugfix show method

## 0.20.0 - 2021-06-23

### Feature
- Change cli base to click
- Add support for wetterdienst core API in cli and restapi
- Export: Use InfluxDBClient instead of DataFrameClient and improve connection handling with InfluxDB 1.x
- Export: Add support for InfluxDB 2.x
- Add show() method with basic information on the wetterdienst instance

### Fix
- Fix InfluxDB export by skipping empty fields

## 0.19.0 - 2021-05-14

### Refactor
- Make tidy method a abstract core method of Values class

### Fix
- Fix DWD Mosmix generator to return all contained dataframes

## 0.18.0 - 2021-05-04

### Feature
- Add origin and si unit mappings to services
- Use argument "si_units" in request classes to convert origin units to si, set to default
- Improve caching behaviour by introducing optional ``WD_CACHE_DIR`` and ``WD_CACHE_DISABLE`` environment variables. Thanks, @meteoDaniel!
- Add baseline test for ECCC observations
- Add DWD Observation hourly moisture to catalogue

## 0.17.0 - 2021-04-08

### Feature
- Add capability to export data to Zarr format
- Add Wetterdienst Explorer UI. Thanks, @meteoDaniel!
- Add MAC ARM64 supoort with dependency restrictions
- Add support for stations filtering via bbox and name
- Add support for units in distance filtering

### Refactor
- Rename station_name to name
- Rename filter methods to .filter_by_station_id and .filter_by_name, use same convention for bbox, filter_by_rank (previously nearby_number), filter_by_distance (nearby_distance)

### Fix
- Radar: Verify HDF5 responses instead of returning invalid data
- Mosmix: Use cached stations to improve performance

## 0.16.1 - 2021-03-31

### Refactor
- Make .discover return lowercase parameters and datasets

## 0.16.0 - 2021-03-29

### Refactor
- Use direct mapping to get a parameter set for a parameter
- Rename DwdObservationParameterSet to DwdObservationDataset as well as corresponding columns
- Merge metadata access into Request
- Repair CLI and I/O subsystem
- Add capability to export to Feather- and Parquet-files to I/O subsystem
- Deprecate support for Python 3.6
- Add ``--reload`` parameter to ``wetterdienst restapi`` for supporting development
- Improve spreadsheet export
- Increase I/O subsystem test coverage
- Make all DWD observation field names lowercase
- Make all DWD forecast (mosmix) field names lowercase
- Rename humanize_parameters to humanize and tidy_data to tidy

### Feature
- Add Environment and Climate Change Canada API

### Fix
- Radar: Use OPERA as data source for improved list of radar sites

## 0.15.0 - 2021-03-07

### Feature
- Add StationsResult and ValuesResult to allow for new workflow and connect stations and values request
- Add accessor .values to Stations class to get straight to values for a request
- Add top-level API

### Fix
- Fix issue with Mosmix station location

## 0.14.1 - 2021-02-21

### Fix
- Fix date filtering of DWD observations, where accidentally an empty dataframe was returned

## 0.14.0 - 2021-02-05

### Feature
- DWD: Add missing radar site "Emden" (EMD, wmo=10204)

### Fix
- Mosmix stations: fix longitudes/latitudes to be decimal degrees (before they were degrees and minutes)

### Refactor
- Change key STATION_HEIGHT to HEIGHT, LAT to LATITUDE, LON to LONGITUDE
- Rename "Data" classes to "Values"
- Make arguments singular

## 0.13.0 - 2021-01-21

### Feature
- Create general Resolution and Period enumerations that can be used anywhere
- Create a full dataframe even if no values exist at requested time
- Add further attributes to the class structure
- Make dates timezone aware
- Restrict dates to isoformat

## 0.12.1 - 2020-12-29

### Fix
- Fix 10minutes file index interval range by adding timezone information

## 0.12.0 - 2020-12-23

### Refactor
- Move more functionality into core classes
- Add more attributes to the core e.g. source and timezone
- Make dates of internal data timezone aware, set start date and end date to UTC
- Add issue date to Mosmix class that actually refers to the Mosmix run instead of start date and end date
- Use Result object for every data related return
- In accordance with typical naming conventions, DWDObservationSites is renamed to DWDObservationStations, the same is applied to DWDMosmixSites
- The name ELEMENT is removed and replaced by parameter while the acutal parameter set e.g. CLIMATE_SUMMARY is now found under PARAMETER_SET
- Remove StorageAdapter and its dependencies
- Methods self.collect_data() and self.collect_safe() are replaced by self.query() and self.all() and will deprecate at some point

## 0.11.1 - 2020-12-10

### Fix
- Bump ``h5py`` to version 3.1.0 in order to satisfy installation on Python 3.9

## 0.11.0 - 2020-12-04

### Fix
- InfluxDB export: Fix export in non-tidy format (#230). Thanks, @wetterfrosch!
- InfluxDB export: Use "quality" column as tag (#234). Thanks, @wetterfrosch!
- InfluxDB export: Use a batch size of 50000 to handle larger amounts of data (#235). Thanks, @wetterfrosch!
- Update radar examples to use ``wradlib>=1.9.0``. Thanks, @kmuehlbauer!
- Change wherever possible column type to category
- Increase efficiency by downloading only historical files with overlapping dates if start_date and end_date are given
- Use periods dynamically depending on start and end date
- Fix inconsistency within 1 minute precipitation data where historical files have more columns
- Improve DWD PDF parser to extract quality information and select language. Also, add an example at ``example/dwd_describe_fields.py`` as well as respective documentation.

## 0.10.1 - 2020-11-14

### Fix
- Upgrade to dateparser-1.0.0. Thanks, @steffen746, @noviluni and @Gallaecio! This fixes a problem with timezones on Windows. The reason is that Windows has no zoneinfo database and ``tzlocal`` switched from ``pytz`` to ``tzinfo``. https://github.com/earthobservations/wetterdienst/issues/222

## 0.10.0 - 2020-10-26

### Feature
- CLI: Obtain "--tidy" argument from command line
- Extend MOSMIX support to equal the API of observations
- DWDObservationSites now filters for those stations which have a file on the server
- DWDObservationData now also takes an individual parameter independent of the pre-configured DWD datasets by using DWDObservationParameter or similar names e.g. "precipitation_height"
- Newly introduced coexistence of DWDObservationParameter and DWDObservationParameterSet to address parameter sets as well as individual parameters

### Refactor
- Imports are changed to submodule thus now one has to import everything from wetterdienst.dwd
- Renaming of time_resolution to resolution, period_type to period, several other relabels

## 0.9.0 - 2020-10-09

### Refactor
- Large refactoring
- Make period type in DWDObservationData and cli optional
- Activate SQL querying again by using DuckDB 0.2.2.dev254. Thanks, @Mytherin!

### Fix
- Fix coercion of integers with nans
- Fix problem with storing IntegerArrays in HDF

### Feature
- Rename ``DWDStationRequest`` to ``DWDObservationData``
- Add ``DWDObservationSites`` API wrapper to acquire station information
- Move ``discover_climate_observations`` to ``DWDObservationMetadata.discover_parameters``
- Add PDF-based ``DWDObservationMetadata.describe_fields()``
- Upgrade Docker images to Python 3.8.6
- Move intermediate storage of HDF out of data collection
- Fix bug with date filtering for empty/no station data for a given parameter
- Radar data: Add non-RADOLAN data acquisition

## 0.8.0 - 2020-09-25

### Feature
- Add TTL-based persistent caching using dogpile.cache
- Add ``example/radolan.py`` and adjust documentation
- Export dataframe to different data sinks like SQLite, DuckDB, InfluxDB and CrateDB
- Query results with SQL, based on in-memory DuckDB
- Split get_nearby_stations into two functions, get_nearby_stations_by_number and get_nearby_stations_by_distance
- Add MOSMIX client and parser. Thanks, @jlewis91!
- Add basic HTTP API

## 0.7.0 - 2020-09-16

### Feature
- Add test for Jupyter notebook
- Add function to discover available climate observations (time resolution, parameter, period type)
- Make the CLI work again and add software tests to prevent future havocs
- Use Sphinx Material theme for documentation

### Fix
- Fix typo in enumeration for TimeResolution.MINUTES_10

## 0.6.0 - 2020-09-07

### Feature
- Enhance usage of get_nearby_stations to check for availability
- Output of get_nearby_stations is now a slice of meta_data DataFrame output

## 0.5.0 - 2020-08-27

### Feature
- Add RADOLAN support
- Change module and function naming in accordance with RADOLAN

## 0.4.0 - 2020-08-03

### Feature
- Extend DWDObservationData to take multiple parameters as request
- Add documentation at readthedocs.io
- [cli] Adjust methods to work with multiple parameters

## 0.3.0 - 2020-07-26

### Refactor
- Establish code style black
- Setup nox session that can be used to run black via nox -s black for one of the supported Python versions

### Feature
- Add option for data collection to tidy the DataFrame (properly reshape) with the "tidy_data" keyword and set it to be used as default

### Fix
- Fix integer type casting for cases with nans in the column/series
- Fix humanizing of column names for tidy data

## 0.2.0 - 2020-07-23

### Feature
- [cli] Add geospatial filtering by distance.
- [cli] Filter stations by station identifiers.
- [cli] Add GeoJSON output format for station data.
- Improvements to parsing high resolution data by setting specific datetime formats and changing to concurrent.futures

### Fix
- Fix na value detection for cases where cells have leading and trailing whitespace

### Refactor
- Change column name mapping to more explicit one with columns being individually addressable
- Add full column names for every individual parameter
- More specific type casting for integer fields and string fields

## 0.1.1 - 2020-07-05

### Feature
- [cli] Add geospatial filtering by number of nearby stations.
- Simplify release pipeline
- Small updates to readme

### Fix
- Change updating "parallel" argument to be done after parameter parsing to prevent mistakenly not found parameter
- Remove find_all_match_strings function and extract functionality to individual operations

### Refactor
- Parameter, time resolution and period type can now also be passed as strings of the enumerations e.g. "climate_summary" or "CLIMATE_SUMMARY" for Parameter.CLIMATE_SUMMARY
- Enable selecting nearby stations by distance rather than by number of stations

## 0.1.0 - 2020-07-02

### Feature
- Initial release
- Update README.md
- Update example notebook
- Add Gh Action for release
- Rename library
