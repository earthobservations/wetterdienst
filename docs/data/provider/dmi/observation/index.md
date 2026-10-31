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
exception: a value outside the generous physical range of its parameter, the check `range`, hard by default (60 degrees of air
temperature; for precipitation 600 mm in an hour, 500 mm in a day, 1,500 mm in a month and 4,000 mm
in a year, the last three where DMI validated 183.5, 641.8 and 3,291.3 mm at most; the largest amounts of a day or
of half an hour, `precipitation_amount_max` and `precipitation_amount_max_30min`, 500 mm) is null and
keeps what DMI wrote as the last token of `quality_flags`, `manual,validity:false,rejected:range,raw:17802`. With
`plausibility={"range": "soft"}` the value is kept and flagged `manual,validity:false,suspect:range`
([plausibility checks](../../../plausibility.md)). So the
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

The global radiation of a day, a month and a year (`mean_radiation`) is the energy summed over the span, which DMI
publishes in MJ/m² ("for all other time resolutions the unit is MJ/m^2"; the sum of the underlying hourly values times
3600 / 10^6). The library has no MJ/m² and returns it as `radiation_global` in the unit asked for (J/cm² by default),
reading the value as kJ/m² (DMI's value times 1000). A clear June day in Denmark brings 15 to 30 MJ/m² (25.4 MJ/m² at
06041 on 2023-06-22, which the 24 hourly means of that day add up to). The hour stays `radiation_global_intensity_mean`
in W/m². A day above 60 MJ/m², a month above 1860 and a year above 5000 are read as null: 04339 has days of 135 to 284
MJ/m² in the polar night of January 2021 that DMI marks valid.

The counts of days are `count_days_*` with the threshold of DMI's own definition (its calculation table, read on
2026-10-31), each held to the daily records DMI publishes. The cold days are those with a minimum temperature "less
than -10 °C" (`count_days_temperature_air_min_2m_lt_minus_10c`). The windy, stormy, storm and hurricane days
(`no_windy_days`, `no_stormy_days`, `no_days_w_storm`, `no_days_w_hurricane`) are the days on which the highest
10-minute mean wind speed (`max_wind_speed_10min`) was "greater or equal to" 10.8, 20.8, 24.5 and 28.5 m/s
(`count_days_wind_speed_rolling_mean_max_ge_10_8mps` and so on); the parameter list of the documentation says "mean
wind speed", but the counts fit the 10-minute maximum (the daily mean wind speed in 2 of 60 months at 06180, the
maximum in 59, and `>` in 27). The clear and cloudy days are those with a mean cloud cover "less than 20%" and
"greater than 80%" (`count_days_cloud_cover_total_mean_lt_20pct` and `_gt_80pct`), a day of exactly 20 % being no
clear day and one of exactly 80 % no cloudy day; DMI publishes them for every day as 1 or 0. The days with snow cover
are those with a snow depth "greater than 0" and a snow cover "greater than 50" percent
(`count_days_snow_cover_gt_50pct`, published for 2011 to 2015 only).

DMI also publishes the mean vapour pressure from the day on (`pressure_vapor_mean`), the greatest snow depth of a
month and a year (`snow_depth_max`; a 999.0 of September 2020 at 24043 and 31259 is no depth and is null), the highest
and lowest temperature and the precipitation of the last 12 and 24 hours (`temperature_air_max_2m_last_12h`,
`temperature_air_min_2m_last_12h`, `precipitation_amount_last_12h` and `_24h`) and the soil temperature at 10 cm
(`temperature_soil_mean_0_1m`). The 12 hour values are reports of 06:00 and 18:00 UTC (the temperatures also of 12:00
and 00:00 UTC for a few stations), the 24 hour values of 00:00, 06:00, 12:00 and 18:00 UTC, and they are stamped at
the end of their window, the report time: DMI's `from` is the start of the last hour of the window (17:00 for the
18:00 report), where the other values of the hour are stamped by their `from`. Not served, for want of a canonical
name that fits exactly: `snow_cover` (would be `snow_cover`), `leaf_moisture` (`leaf_wetness_duration`), `temp_grass`,
the air temperature at grass height of 5 to 20 cm (`temperature_air_mean_grass_height`), `temp_soil_30`
(`temperature_soil_mean_0_3m`) and `vapour_pressure_deficit_mean` (`vapor_pressure_deficit_mean`).

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
