# Observation

## Overview

DMI's open climate data service provides quality-controlled, aggregated station values for
stations in Denmark, Greenland and the Faroe Islands, at hourly, daily, monthly and annual
resolution. Data is served through DMI's key-less OGC API Features endpoint (`climateData`);
no authentication is required.

The provider queries the `climateData` `stationValue` collection, which returns every
available parameter for a station/resolution/date-range in a single request.

Hourly aggregates are aligned to UTC and labelled by the start of the hour. Daily, monthly
and annual aggregates use *local civil* period boundaries (e.g. a Danish day runs from local
midnight to local midnight); the provider labels each such aggregate by its civil calendar
date at UTC midnight. The requested date range is widened internally by a day on each side so
that this local/UTC offset never drops a boundary period from the result.

## License

Data is © DMI (Danish Meteorological Institute) and licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
See [DMI Open Data](https://opendatadocs.dmi.govcloud.dk/) for further information and usage
conditions.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
annual.md
```
