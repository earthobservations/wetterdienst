# Observation

## Overview

CHMI's open-data portal provides access to historical climate observations from the
Czech Hydrometeorological Institute's station network across Czechia at 10-minute, hourly,
daily, monthly and annual resolution. No API key or registration is required — the portal is
fully public.

Station metadata comes from `metadata/meta1.csv`. A station whose sensor was relocated appears
under several operational periods; these are collapsed to a single station using the most recent
position for the coordinates and the full extent for the operational dates. The catalogue does
not expose a region, so `state` is always null, and a station's `end_date` is null while it is
still active.

Observations are addressed per station and element. The `daily`, `monthly` and `annual`
resolutions store one flat CSV per station/element (e.g. `dly-<WSI>-T.csv`); the `10_minutes`
and `hourly` resolutions store one CSV per station/element/month under a year sub-directory, so
they require a date range. The 10-minute and hourly files only reach back to 2018.

The `daily` files may hold several time functions — the daily mean (`AVG`) alongside fixed-term
readings — so the appropriate one is selected per parameter and timestamps are normalised to the
calendar day. The `monthly`/`annual` files additionally carry an aggregation function, so the
climatological mean of daily means/maxima/minima is used for temperature and the total for
precipitation.

Not every station measures every parameter — a station/parameter combination that CHMI doesn't
have simply contributes no rows.

## License

Data is © Czech Hydrometeorological Institute (CHMI). See
[CHMI open data](https://opendata.chmi.cz/) for further information and usage conditions.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
monthly.md
annual.md
```
