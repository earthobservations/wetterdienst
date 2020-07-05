# Changelog

## Development
- ...

## 0.1.1 (05.07.2020)
- Bring geospatial filtering to the command line.
- Simplify release pipeline
- small updates to readme
- change updating "parallel" argument to be done after parameter parsing to prevent mistakenly not found 
parameter
- remove find_all_match_strings function and extract functionality to individual operations
- parameter, time resolution and period type can now also be passed as strings of the enumerations e.g.
"climate_summary" or "CLIMATE_SUMMARY" for Parameter.CLIMATE_SUMMARY
- enable selecting nearby stations by distance rather then by number of stations

## 0.1.0 (02.07.2020)
- initial release
- update README.md
- update example notebook
- add Gh Action for release
- rename library
