# SWSMOS

## Overview

SWSMOS (Straßenwetter-MOS) is the DWD's **road weather forecast** for its network of ~1800 road
weather stations ("Straßenwetterstationen"). For each model run it provides an hourly forecast out
to +167 hours (roughly seven days) of air temperature, dew point, road surface temperature, liquid
precipitation and precipitation probabilities, and the road surface condition. Most variables come
from a Model Output Statistics (MOS) post-processing; the road surface temperature and road
condition come from the METRo road-weather model.

The data is published as one CSV file per model run under
[local_forecasts/swsmos](https://opendata.dwd.de/weather/local_forecasts/swsmos/)
(`swsmos_<YYYYMMDDHH0000>_opendata.csv.bz2`), with the station catalogue in `swsKatalog.csv.bz2`.
The `issue` argument selects the model run (default: the latest available). No authentication is
required.

This is the forecast counterpart to the DWD `road` **observation** network, sharing the road surface
temperature and road condition variables. See
[SWSMOS at the DWD](https://www.dwd.de/DE/leistungen/swis_swsmos/swis_swsmos.html).

```{toctree}
:hidden:

hourly.md
```
