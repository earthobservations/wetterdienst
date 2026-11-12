# SYNOP

## Overview

SYNOP observation data at the native 3-hourly reporting interval ("subdaily" resolution), covering the ~190 SYNOP
stations from 1996 to present. Historical and current-year data are downloaded transparently as needed.

## Plausibility checks

Three [checks](../../../plausibility.md) judge values here that are hard by default. `range`: a pressure, temperature, dew
point or amount of rain beyond the records, by the one table of bounds of every provider (the `369.15` K of a temperature,
the `11170` Pa of a station pressure), and a temperature below 0 °C at a station without frost (Guadeloupe, Martinique,
Guyane, Mayotte, Wallis-et-Futuna, French Polynesia, the Îles Éparses). `elevation`: a station pressure `pres` that the
standard atmosphere does not allow at the station's elevation in the station list, from 870/1013.25 of it (143 hPa below
at sea level) to 75 hPa above it. `consistency`: the humidity `u` of a
row whose `td` is below 0 °C at a station without frost, and a `tn12` that is the text of the `tx12` beside it (a copy,
no minimum); both second values are in the same dataset, which is collected whole. A rejected value is `rejected:<check>,raw:<number>`, and
is kept as `suspect:<check>` where the check is soft. The checks that are soft by default also judge it: [`relations`](../../../plausibility.md#the-relations-of-one-row-relations) flags **both** readings of a dew point more than 0.2 K above the air temperature and of a gust of the last ten minutes below the mean wind of the same ten minutes.

```{toctree}
:hidden:

subdaily.md
```
