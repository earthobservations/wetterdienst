# Observation

## Overview

"Données climatologiques de base", covering a much larger network of several thousand stations across
metropolitan France and overseas territories, sharded by French department. Station identity, coordinates and
start/end dates are sourced from Météo-France's canonical station metadata registry rather than the (much
larger) per-department archives themselves; a small fraction of listed stations may not actually have
downloadable daily/monthly records.

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
