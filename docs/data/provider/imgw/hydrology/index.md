# Hydrology

## Overview

IMGW publishes hydrological observations for the Polish river-gauge network at daily and monthly
resolution, as open data from the
[public data portal](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/).
No authentication is required.

Values are downloaded as zipped CSV archives and decoded as `latin-1`. The archive layout has
changed over time — daily data is split into per-month files (`codz_YYYY_MM.zip`) historically
and consolidated into a single per-year file (`codz_YYYY.zip`) from 2023 onwards — which
wetterdienst normalizes transparently.

```{toctree}
:hidden:

daily.md
monthly.md
```