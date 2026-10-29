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

The stations come from IMGW's
[station-code list](https://dane.imgw.pl/datastore/getfiledown/Arch/Telemetria/Hydro/kody_stacji.csv).
Besides the core columns, each station names the river the gauge is on, with its hydrographic code
as IMGW lists it (`Odra (1)`), as `river`, and the gauge's position along it, in kilometres from the
river's mouth, as `river_kilometer`; the Baltic coast gauges are on the sea (`Morze Bałtyckie (0)`)
and have kilometre `0` or none. The altitude of the gauge's zero, in metres above sea level and
negative for some coastal gauges, is `gauge_zero`. The list does not state which vertical datum
that altitude refers to, so `gauge_zero_datum` is null. Each of them is null for a station whose
field IMGW leaves empty. These are the columns `wsv/pegel` names the same things by.

```{toctree}
:hidden:

daily.md
monthly.md
```