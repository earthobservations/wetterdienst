# SYNOP

## Overview

SYNOP observation data at the native 3-hourly reporting interval ("subdaily" resolution), covering the ~190 SYNOP
stations from 1996 to present. Historical and current-year data are downloaded transparently as needed.

## Plausibility checks

Three [checks](../../../plausibility.md) judge values here, all hard by default. `range`: a pressure, temperature, dew
point or amount of rain beyond the records (the `369.15` K of a temperature, the `11170` Pa of a station pressure), and a
temperature below 0 °C at a station without frost (Guadeloupe, Martinique, Guyane, Mayotte, Wallis-et-Futuna, French
Polynesia, the Îles Éparses). `elevation`: a station pressure `pres` more than 7,500 Pa from what the barometric formula
of the standard atmosphere expects at the station's elevation in the station list. `consistency`: the humidity `u` of a
row whose `td` is below 0 °C at a station without frost, and a `tn12` that is the text of the `tx12` beside it (a copy,
no minimum); both second values are read from the same file. A rejected value is `rejected:<check>,raw:<number>`, and
is kept as `suspect:<check>` where the check is soft.

```{toctree}
:hidden:

subdaily.md
```
