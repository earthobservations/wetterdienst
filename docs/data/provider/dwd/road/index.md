# Road

## Overview

The DWD operates a network of road weather stations along German motorways ("Straßenwetter")
that report conditions relevant to traffic and road safety. Wetterdienst exposes their
observations at 15-minute resolution.

The data is published as
[weather reports](https://opendata.dwd.de/weather/weather_reports/road_weather_stations/) in
BUFR format, so parsing requires the optional `bufr` dependency extra. Station
metadata is resolved from the DWD
[station list](https://www.dwd.de/DE/leistungen/opendata/help/stationen/sws_stations_xls.xlsx).
No authentication is required.

## The source's own verdict (`source`)

The first token of `quality_flags` is the station's own verdict on the sensor of the reading (`1` suspect, `0` checked
and not suspect, null unknown; see {ref}`quality_flags <dwd-road-quality-flags>`), read from the BUFR flag table
`0 33 005`, "Quality information (AWS data)"
([WMO code and flag tables](https://github.com/wmo-im/BUFR4/blob/master/BUFRCREX_CodeFlag_en_33.csv), read 2026-11-02),
whose bits say: Wind data suspect, Air temperature data suspect, Humidity data suspect, Ground temperature data
suspect, Visibility data suspect, Precipitation data suspect. The check `source` reads `1` for the quantities
the table names: the wind (`wind_speed`, `wind_direction`, the gusts), `temperature_air`, `humidity_relative`, `visibility`
and the precipitation (`precipitation_amount`, `precipitation_intensity`, `precipitation_type_flags`). Not read:
`temperature_surface`, which the reader maps to "Ground temperature data suspect" because the data confirms it
({ref}`quality_flags <dwd-road-quality-flags>`) while the table does not word a road surface, and `temperature_dew_point`,
which has the humidity's bit because one probe measures both; their `1` stays the station's flag. It is the one level the table words, "suspect", so `hard` nulls it, as it does the "douteuse" of
Météo-France. `0` is no verdict, null says the station ran no automated checks, and "Pressure data suspect", "Wet-bulb
temperature data suspect" and the others are quantities the network does not report.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the default is
`soft`, which keeps the value and writes `1,suspect:source`, so interpolation, summaries and climate stripes leave it
out. The check `consistency` already leaves an air temperature that carries `1` out of its comparison with the road
surface. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

```{toctree}
:hidden:

15_minutes.md
```