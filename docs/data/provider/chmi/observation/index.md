# Observation

## Overview

CHMI's open-data portal provides access to historical climate observations from the
Czech Hydrometeorological Institute's station network across Czechia at 10-minute, hourly,
daily, monthly and annual resolution. No API key or registration is required — the portal is
fully public.

Station metadata comes from `metadata/meta1.csv`. A station whose sensor was relocated appears
under several operational periods; these are collapsed to a single station using the most recent
position for the coordinates and the full extent for the operational dates. The catalogue does
not expose a region, so `region` is always null, and a station's `end_timestamp` is null while it
is still active. The catalogue is one list for every resolution and element, so for the `daily`,
`monthly` and `annual` resolutions a stations request lists only the stations that have a file of
one of the requested parameters (each parameter is one element, such as `T` or `SRA`; a whole
dataset requests them all), read from the directories of the portal, one per category of the
requested elements. The `10_minutes` and `hourly` resolutions list the stations that can have files
there. Their files are one per month under a directory per year (about 1.6 MB each, eight years),
which every request would have to read, so the list is cut by what is known without them: the files
begin with 2018, so a station whose period ended before it is left out, and so is one with no daily
file of an element that is read (the daily directories are cached, as a daily request reads them).
Every station with a 10 minute or hourly file passes both, which a live test holds. Of the 1,603
stations of `meta1.csv`, 767 are listed (read 2026-10-30). Every file of the
`daily`, `monthly` and `annual` directories has a station in `meta1.csv` (read 2026-10-30; before
CHMI updated it, the files of 29 monthly and 22 annual stations had none).

Observations are addressed per station and element. The `daily`, `monthly` and `annual`
resolutions store one flat CSV per station/element (e.g. `dly-<WSI>-T.csv`); the `10_minutes`
and `hourly` resolutions store one CSV per station/element/month under a year sub-directory, so
they require a date range. The 10-minute and hourly files only reach back to 2018.

The hourly files are the SYNOP reports. CHMI publishes the station-level pressure `P` there for 2018
to 2024 only; the files of 2025 hold the pressure reduced to sea level (`P_hm`, the
parameter `pressure_air_sea_level`, which the older years hold too) and the three-hour pressure
tendency `ppp` (not read). `P_hm` is another quantity than `P`, not its successor. A window that
reaches past 2024 warns (`parameter-ended`) that the hourly `pressure_air_site` has no values from
2025 on; the `10_minutes` resolution still publishes it.

The `daily` files may hold several time functions — the daily mean (`AVG`) alongside fixed-term
readings — so the appropriate one is selected per parameter and timestamps are normalised to the
calendar day. The `monthly`/`annual` files additionally carry an aggregation function, so the
climatological mean of daily means/maxima/minima is used for temperature and the total for
precipitation.

Not every station measures every parameter — a station/parameter combination that CHMI doesn't
have simply contributes no rows.

CHMI's station catalogue (`meta1.csv`) also lists two stations abroad, Reykjavik
(`0-20000-0-04030`) and Marambio Base in Antarctica (`0-20000-0-89055`). The portal has no file
for them in any resolution (checked 2026-10-29), so they are left out of the station lists.

## License

Data is © Czech Hydrometeorological Institute (CHMI), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See
[CHMI open data](https://opendata.chmi.cz/) and the [provider page](../index.md) for the sources of the licence.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
monthly.md
annual.md
```
