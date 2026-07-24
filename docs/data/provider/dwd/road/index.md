# Road

## Overview

The DWD operates a network of road weather stations along German motorways ("Straßenwetter")
that report conditions relevant to traffic and road safety. Wetterdienst exposes their
observations at 15-minute resolution.

The data is published as
[weather reports](https://opendata.dwd.de/weather/weather_reports/road_weather_stations/) in
BUFR format, so parsing requires the optional `eccodes`/`bufr` dependency extras. Station
metadata is resolved from the DWD
[station list](https://www.dwd.de/DE/leistungen/opendata/help/stationen/sws_stations_xls.xlsx).
No authentication is required.

```{toctree}
:hidden:

15_minutes.md
```