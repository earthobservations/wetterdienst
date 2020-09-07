Changelog
*********

Current
=======

...

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

- extend DWDStationRequest to take multiple parameters as request
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
