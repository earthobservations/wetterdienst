*********
Changelog
*********

Development
===========



0.12.0 (23.12.2020)
===================

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
===================

- Bump ``h5py`` to version 3.1.0 in order to satisfy installation on Python 3.9

0.11.0 (04.12.2020)
===================

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
===================

- Upgrade to dateparser-1.0.0. Thanks, @steffen746, @noviluni and @Gallaecio!
  This fixes a problem with timezones on Windows. The reason is that
  Windows has no zoneinfo database and ``tzlocal`` switched from ``pytz`` to ``tzinfo``.
  https://github.com/earthobservations/wetterdienst/issues/222

0.10.0 (26.10.2020)
===================

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
==================

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
==================

- Add TTL-based persistent caching using dogpile.cache
- Add ``example/radolan.py`` and adjust documentation
- Export dataframe to different data sinks like SQLite, DuckDB, InfluxDB and CrateDB
- Query results with SQL, based on in-memory DuckDB
- Split get_nearby_stations into two functions, get_nearby_stations_by_number and
  get_nearby_stations_by_distance
- Add MOSMIX client and parser. Thanks, @jlewis91!
- Add basic HTTP API

0.7.0 (16.09.2020)
==================

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
==================

- enhance usage of get_nearby_stations to check for availability
- output of get_nearby_stations is now a slice of meta_data DataFrame output

0.5.0 (27.08.2020)
==================

- add RADOLAN support
- change module and function naming in accordance with RADOLAN

0.4.0 (03.08.2020)
==================

- extend DWDObservationData to take multiple parameters as request
- add documentation at readthedocs.io
- [cli] Adjust methods to work with multiple parameters

0.3.0 (26.07.2020)
==================

- establish code style black
- setup nox session that can be used to run black via nox -s black for one of the supported
  Python versions
- add option for data collection to tidy the DataFrame (properly reshape) with the 
  "tidy_data" keyword and set it to be used as default
- fix integer type casting for cases with nans in the column/series
- fix humanizing of column names for tidy data

0.2.0 (23.07.2020)
==================

- [cli] Add geospatial filtering by distance.
- [cli] Filter stations by station identifiers.
- [cli] Add GeoJSON output format for station data.
- improvements to parsing high resolution data by setting specific datetime formats and changing to concurrent.futures
- fix na value detection for cases where cells have leading and trailing whitespace
- change column name mapping to more explicit one with columns being individually addressable
- add full column names for every individual parameter
- more specific type casting for integer fields and string fields

0.1.1 (05.07.2020)
==================

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
==================

- initial release
- update README.md
- update example notebook
- add Gh Action for release
- rename library
