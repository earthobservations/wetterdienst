# Observation

## Overview

"Données climatologiques de base", covering a much larger network of several thousand stations across
metropolitan France and overseas territories, sharded by French department. Station identity, coordinates and
start/end dates are sourced from Météo-France's canonical station metadata registry rather than the (much
larger) per-department archives themselves; a small fraction of listed stations may not actually have
downloadable daily/monthly records.

A station's `region` is the code of its département, as the registry lists it and written with two digits
(`09` for the Ariège, `29` for Finistère), or three for an overseas one (`972` for Martinique). It is the code
and not the name, and the registry does not tell Corsica's two départements apart: both are `20`, not `2A` and
`2B`. The `meteofrance/synop` list gives no region.

- **daily**: split into a `core` dataset (precipitation, temperature, wind) and an `others` dataset (pressure,
  radiation, humidity, snow) — roughly balanced in size, so neither gets the generic name
- **monthly**: a single dataset, so it keeps the generic `data` name
- **hourly**: also split into `core`/`others`, though this split only exists at the wetterdienst level — the
  source publishes one unsplit file per department/period covering all ~100 parameters
- **6_minutes**: a single dataset, covering only precipitation (the only parameter published at this resolution)

## Plausibility checks

Three [checks](../../../plausibility.md) judge values here, all hard by default: `range`, the one table of bounds of
every provider and a temperature below 0 °C (the air at 2 m, its extremes and the dew point) at a station of Guadeloupe,
Martinique, Guyane, Mayotte, Wallis-et-Futuna, French Polynesia or the Îles Éparses, where there is no frost
(`rejected:range,raw:-20.0`; the datasets `hourly/core`, `hourly/others`, `daily/core` and `monthly/data`);
`elevation`, the hourly station pressure `PSTAT` of a station with an elevation in the list, which the standard
atmosphere does not allow, from 870/1013.25 of it (143 hPa below at sea level) to 75 hPa above it (`rejected:elevation,raw:1093.3`:
Hurricane Irma's 917.4 hPa at St-Barthélemy, 3 m, 2017-09-06, is kept; 14.6 million readings of the files of 2025 and
2026 and of 77 of the 210 department files of 2010 to 2024 held none that the rule rejects; `hourly/others`); and `consistency`, the hourly humidity `U` of an hour whose dew point
`TD` is such a temperature (`rejected:consistency,raw:15`; `hourly/others`). The dew point is read from the same dataset (collected whole), whether it is asked for or not, and nothing is
downloaded for the check. With `plausibility={"range":
"soft"}` the value is kept and flagged `suspect:range`.

```{toctree}
:hidden:

daily.md
hourly.md
6_minutes.md
monthly.md
```
