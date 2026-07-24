# DWD

## Overview

The data as offered by the DWD through ``wetterdienst`` includes:

- [Observation](observation/index.md) — historical weather observations
    - historical (reaching back to the 19th century), recent (~500 days to yesterday) and now
      (yesterday up to the last hour) periods
    - every minute to yearly resolution
    - time series of over 1000 stations in Germany
- [Mosmix](mosmix/index.md) — statistically optimized point forecasts derived from weather models
    - MOSMIX-S (~40 parameters, updated hourly) and MOSMIX-L (~115 parameters, updated every 6 hours)
    - over 5000 stations worldwide, forecast horizon up to 240 hours
- [DMO](dmo/index.md) — raw point forecasts extracted from weather models (no statistical postprocessing)
    - ICON (global) and ICON-EU (regional) models
    - hourly resolution (78 h lead time) and, for ICON, additional 3-hourly resolution (168 h lead time)
    - over 5000 stations worldwide
- [Road](road/index.md) — weather observations from German motorway ("road") stations
    - 15-minute resolution, distributed in BUFR format
- [Radar](radar/index.md) — radar-based precipitation products
    - composite, radolan, radvor, sites and radolan_cdc
    - RADOLAN: gauge-calibrated areal precipitation; RADVOR: radar-based precipitation forecast
- [Derived products](derived/index.md) — secondary products computed from primary observations
    - technical products (heating/cooling degree days, climate correction factor) and climate
      products (radiation & sunshine duration, soil data)
    - hourly, daily and monthly resolution, for stations in Germany

For a quick overview of the work of the DWD check the current 
[dwd report](https://www.dwd.de/SharedDocs/downloads/DE/allgemein/zahlen_und_fakten.pdf?__blob=publicationFile&v=14) 
(only in german language).

## License

The German Weather Service specified their data as being open though they ask you to
reference them as copyright owner. Take a look at the 
[Open Data Strategy at the DWD](https://www.dwd.de/EN/ourservices/opendata/opendata.html)
and the [Official Copyright](https://www.dwd.de/EN/service/copyright/copyright_artikel.html?nn=495490&lsbId=627548) 
statements before using the data.

```{toctree}
:hidden:

dmo/index.md
mosmix/index.md
observation/index.md
road/index.md
radar/index.md
derived/index.md
```