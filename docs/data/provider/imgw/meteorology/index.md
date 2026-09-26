# Meteorology

## Overview

IMGW publishes meteorological observations for the Polish weather-station network at daily and
monthly resolution, as open data from the
[public data portal](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/).
No authentication is required.

Values are downloaded as zipped CSV archives (decoded as `latin-1`), with station metadata
resolved from the accompanying station-code list. Both daily and monthly summaries are provided.

Every measurement in these files is followed by a status column, and a measurement IMGW does not
have is written as a literal zero rather than left empty. The status is read, so a parameter a
station does not measure comes back with no values instead of reading zero throughout -- snow depth
at a rain gauge, for example. *Brak zjawiska*, the phenomenon not occurring, is kept as the real
zero it is: no snow cover, or a day without precipitation.

```{toctree}
:hidden:

daily.md
monthly.md
```