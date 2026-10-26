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

## Update date

A forecast is dated by its model run: the `data_updated_at` of the
[`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is the run the forecast is of (the one that the name of its file gives), not the time DWD published the file, so it
is the same however often the run is read, and `retrieved_at` less `data_updated_at` is how old the forecast is.

```{toctree}
:hidden:

hourly.md
```
