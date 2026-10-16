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

Each station's `country` is DMI's three-letter code for the country it is in: `DNK`, `GRL` or `FRO`.
DMI gives no region within a country, so `region` is null.

Each value carries DMI's `qcStatus` in `quality_flags`, `manual` (quality controlled by DMI's
climatologists) or `none` (not controlled), followed by `validity:true` or `validity:false`. DMI
documents `validity` as whether the climatologists consider the value valid: "Invalid data is
generally not correct". It is `false` mostly for Greenland (station 04339 Ittoqqortoormiit has daily
precipitation totals of 1978 mm and annual ones of 9574 mm marked so) and rarely for Denmark. The
library returns those values as they are and leaves it to the caller to filter on the flag, with one
exception: a value outside the generous physical range of its parameter (60 degrees of air temperature,
6,000 mm of precipitation: far above what a gauge in Denmark, the Faroe Islands or Greenland reads) is
null and keeps what DMI wrote as the last token of `quality_flags`,
`manual,validity:false,raw:17802`. The bounds are the same at every resolution, so the monthly 17,802 mm
of 04339 for 2011-10 and its yearly 9,574.3 mm (2014) and 6,026.5 mm (2015) are nulled, and its daily
1978 mm and monthly 3,229.9 mm, which are below the bound, are not. The long shape drops the rows without a value by default, so the token shows with
`drop_nulls=False`.

## License

Data is © DMI (Danish Meteorological Institute) and licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
See [DMI Open Data](https://www.dmi.dk/friedata/dokumentation/basics) for further information and usage
conditions.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
annual.md
```
