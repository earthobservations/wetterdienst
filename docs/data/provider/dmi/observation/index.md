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
exception: a value outside the generous physical range of its parameter (60 degrees of air
temperature; for precipitation 600 mm in an hour, 500 mm in a day, 1,500 mm in a month and 4,000 mm
in a year, the last three where DMI validated 183.5, 641.8 and 3,291.3 mm at most; the largest amounts of a day or
of half an hour, `precipitation_amount_max` and `precipitation_amount_max_30min`, 500 mm) is null and
keeps what DMI wrote as the last token of `quality_flags`, `manual,validity:false,raw:17802`. So the
monthly 17,802 mm of 04339 for 2011-10 and 3,229.9 mm for 2012-10, its daily 1978 and 989 mm of 2011
and its yearly 9,574.3 mm (2014) and 6,026.5 mm (2015) are nulled. Its yearly 3,253.4 mm of 2012, the
sum of that 3,229.9 mm and two months, is below the bound and is not: station 04390 has a year of
3,291.3 mm that DMI validated, so no range separates the two, and only `validity:false` tells. The
long shape drops the rows without a value by default, so the token shows with
`drop_nulls=False`.

DMI's `-0.1` in `precipitation_amount` and the largest amounts of a day or of half an hour is not an
amount but a code: "traces of precipitation, less than 0.1 kg/m2" ([DMI's climate data
documentation](https://www.dmi.dk/friedata/dokumentation/climate-data), "Precipitation Codes"). It is
read as `0.0` and keeps the text as the last token of `quality_flags`, `manual,validity:true,raw:-0.1`,
as the trace of KNMI, AEMET and Meteo-France's synop does.

DMI sums that code as `-0.1`: its monthly and annual `precipitation_amount` is the sum of the daily values with each
trace counted as `-0.1`, so such a total is 0.1 mm lower for every trace day in it. Station 22375, the one station
found with the code, has nine trace days in 2001 (checked on 2026-10-30 against the daily values of all stations for
1998 to 2004 and for January and July of the odd years from 1991 to 2025). Its June has three and a total of 44.7 mm,
which is the sum of the days with the traces as `-0.1`, against 45.0 mm with them as `0.0`. The other four months and
the year agree the same way: July 42.0 mm (42.1 with the trace as `0.0`), August 74.1 (74.2), September 139.6 (139.9),
October 43.5 (43.6) and the year 657.6 (658.5). The library returns the totals as DMI publishes them and
the daily trace as `0.0`, so the sum of the daily values it returns is 0.1 mm above DMI's total for each trace day
in it.

The heating degree days are two fields at DMI, by country, and one parameter here, `heating_degree_day`:
`acc_heating_degree_days_17` (17 °C minus the daily mean temperature; "graddage - Danmark") at the stations of
Denmark and `acc_heating_degree_days_19` (19 °C; "graddage - Grønland") at those of Greenland. No station has both
(checked on 2026-10-31 for all stations in the days of 2024-01-10 to 2024-01-12 and the months and years of 2022 and
2023), so the base of a value is that of the country of its station and the two are not comparable.

The summer days (`no_summer_days`) and tropical nights (`no_tropical_nights`) are counted by DMI "more than" 25 °C of
the highest and 20 °C of the lowest temperature of the day, where `count_days_summer` and `count_days_tropical_night`
count from the threshold. DMI's monthly counts are those of its daily values above the threshold in all 157 months
it published for 2010 to 2023 (of 168) at each of 06180, 06070 and 06041, and differ from the days at or above it in
5, 13 and 1 of them for the summer days and in 0, 1 and 1 for the tropical nights (a day at exactly 25.0 or 20.0 °C is not counted). Both are
published for the stations of Denmark and, the summer days only, for those of Greenland.

The highest and lowest pressure of a day (`pressure_air_sea_level_max` and `_min`) are the highest and lowest of the
hourly values of `mean_pressure`, which is reduced to mean sea level, and those of a month and a year the highest and
lowest of the daily values. DMI publishes them for 45 stations (38 in Greenland, 7 from 06007 to 06014), not at the hour
and not for the stations of Denmark proper.

## License

Data is © DMI (Danish Meteorological Institute) and licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/), as
DMI's [terms of use](https://www.dmi.dk/friedata/dokumentation/terms-of-use) state.
See [DMI Open Data](https://www.dmi.dk/friedata/dokumentation/basics) for further information and usage
conditions.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
annual.md
```
