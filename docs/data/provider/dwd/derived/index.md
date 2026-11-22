# Derived

## Overview

The DWD provides several [data products](https://opendata.dwd.de/climate_environment/CDC/derived_germany/) that are derived from weather data.

The following resolutions are supported for the derived data/parameters on the file server
- **hourly** - measured once per hour
- **daily** - measured/summarized once per day
- **monthly** - measured/summarized once a month

Depending on the parameter selected following periods are supported:
- **historical** - values based on data which have completed quality control
- **recent** - newer values based on data which have not passed the full quality control yet

For a timestamp that both periods hold, the answer takes the reading of the preferred period (historical over
recent), even where that file has a missing-value marker (`-999`) and the other a value, as in
[`dwd/observation`](../observation/index.md). None was found in a measurement of 2026-10 (480,880 readings
of the hourly radiation and sunshine duration products).

The derived products currently supported are:

**Technical Products:**
- [heating degreedays](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/heating_degreedays/hdd_3807/) for weather stations
- [cooling degreehours](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/cooling_degreehours/) for weather stations
- [climate correction factor](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/climate_correction_factor/) for postal codes

**Climate Products:**
- [radiation global and sunshine duration](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/) (hourly)
- [soil data](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/) (daily and monthly)

**Not yet implemented Products:**
- [heating degreedays daily](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/daily/heating_degreedays/hdd_3807/)
- [bad weather days](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/daily/bad_weather_days/)
- [heating degreedays daily](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/daily/heating_degreedays/hdd_3807/)
- [windroses](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/multi_annual/windroses/)
- [soil multiannual](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/multi_annual/)
- [fire danger index](https://opendata.dwd.de/climate_environment/CDC/derived_germany/fire_danger_index/)

**Stations without a line in the station list:** the `soil` directories hold files of nine stations that
`stations_list_soil.txt` does not carry (01584, 02110, 02814, 02968, 03612, 04261, 05941, 07350, 13710, read
2026-10-22). They are not listed and their data cannot be requested; a warning that names them is logged,
once a process, when the stations are read for all periods. DWD was asked on 2026-11-07 to add the lines and has not
answered (2026-11-22); `dwd/derived` was not read again then ([GH-3258](https://github.com/earthobservations/wetterdienst/issues/3258)).

## Sheets of DWD that the data contradict

Three of DWD's description sheets of this network say something the files rule out. The questions were sent to DWD
on 2026-11-07 and are not answered (2026-11-22). Until DWD answers, wetterdienst changes no name and no value, and the
description of each parameter says what the data show:

- **The hour of DUETT** (`hourly/radiation_global`, `hourly/sunshine_duration`): the sheet calls the stamp the end of
  the synoptic hour and gives that hour as (HH-1):50 to HH:50 under DATA ORIGIN and as (HH-2):50 to (HH-1):50 under
  CONSIDERATIONS FOR APPLICATIONS. DWD's 10-minute station data fit (HH-2):50 to (HH-1):50 best, which is what the
  descriptions of the two parameters say.
- **The English sheet of the cooling degree hours:** the English sheets in the `cdh_13`, `cdh_16` and `cdh_18`
  directories (`..._hdh_..._en.pdf`, in `recent/`) are the text of the heating degree days sheet (Monatsgradtage,
  Heiztage, 15 degree Celsius), not that of the cooling degree hours. The docs link the English sheet one directory up
  (`..._cdh_..._en.pdf`) instead.
- **The unit of `cooling_degree_hour`:** the sheet gives "Kelvin * day" for Kuehlgradstunden, where the values are K*h
  (2,562.3 for 545 cooling hours at the reference of 13 degree Celsius, Grossenkneten, September 2026). The unit
  returned is `°Ch`.

A late answer is a new issue.

## Positions of the stations

Every list of stations carries a latitude and longitude except one: the stations of `monthly/climate_correction_factor`
are the 100,000 postal codes, generated, with no position (checked 2026-11-18: no null position in any other dataset's
list, `latitude` and `longitude` null for all 100,000 postal codes). A postal code has no name either, so it is found
by its id (`stations`) alone, never by place or by name: a search by `latitude` and `longitude` with `rank` or
`distance`, a bounding box, or an estimate by `interpolate` or `summarize` finds none of them and answers an empty list
with the warning `positions-unavailable`, which names the dataset and the id as the way to find the codes. The stations
of the other datasets of the same request are found as before. A map of the postal codes (`html`, `png`, `svg`) cannot
be drawn: it is a 422, as for [`dwd/pollen`](../pollen/index.md)
([GH-4206](https://github.com/earthobservations/wetterdienst/issues/4206)).

## WIGOS ids of the stations

The datasets whose ids are DWD's station ids (the table below) also carry `wigos_id`, read from WMO's register
OSCAR/Surface by the rule of [`dwd/observation`](../observation/index.md#wigos-ids-of-the-stations): the DWD id is the
local part of `0-276-<issue number>-<id>` (`00044` Großenkneten is `0-276-3-44`). Read 2026-11-20, 304 of the 1,226
stations of the degree days and degree hours and 288 of the 484 of the soil have one. The other datasets have none and
do not read the register; where it cannot be read the stations come back with `wigos_id` null and the warning
`wigos-ids-unavailable`.

## WMO numbers of the stations

The station lists carry no WMO number. Where the ids of a dataset are DWD's station ids, `wmo_id` is read from DWD's
Stationslexikon, as for [`dwd/observation`](../observation/index.md#wmo-numbers-of-the-stations) (the same reader, the
same rule, the same warning `wmo-ids-unavailable` where the page cannot be read). The id scheme of each dataset was
checked against the table on 2026-11-16 (the names of the Stationslexikon agree with those of the lists for every
station that has a number):

| dataset | list of the stations | ids | in the Stationslexikon | `wmo_id` |
| --- | --- | --- | --- | --- |
| `monthly/heating_degreedays`, `monthly/cooling_degreehours_13`, `_16`, `_18` | `KL_Monatswerte_Beschreibung_Stationen.txt` | DWD station ids | all 1,226 | filled for 270 |
| `daily/soil`, `monthly/soil` | `stations_list_soil.txt` | DWD station ids | all 484 | filled for 198 |
| `hourly/radiation_global`, `hourly/sunshine_duration` | `fg_duett_Beschreibung_Stationen.txt`, `sd_duett_Beschreibung_Stationen.txt` | DUETT ids (`18xxx`) | none of 576 | null |
| `monthly/climate_correction_factor` | none: every postal code | postal codes | not station ids | null |

The other stations of the first two rows have no WMO number in the Stationslexikon (it gives them an id of DWD's own
such as `E426` for Großenkneten, or only the number of another product), so `wmo_id` is null for them as for
`dwd/observation`. A postal code that equals the id of a station with a number (314 of the 100,000 do) is no such
station, so the climate correction factor has no `wmo_id` whatever its codes are, and a request for the DUETT or
the postal-code datasets does not read the Stationslexikon at all.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
```
