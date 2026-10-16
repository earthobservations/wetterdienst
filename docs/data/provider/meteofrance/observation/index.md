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

```{toctree}
:hidden:

daily.md
hourly.md
6_minutes.md
monthly.md
```
