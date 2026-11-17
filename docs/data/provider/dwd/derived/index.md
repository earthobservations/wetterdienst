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
once a process, when the stations are read for all periods ([GH-3258](https://github.com/earthobservations/wetterdienst/issues/3258)).

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
