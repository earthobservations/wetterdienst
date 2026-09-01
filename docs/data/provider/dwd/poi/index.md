# POI

## Overview

POI ("Point Of Interest") is the DWD's set of **current weather reports**: for every station it
forecasts for, it publishes the hourly observations of roughly the last day — air temperature,
dew point, humidity, pressure, wind, gusts, precipitation, cloud cover and base, visibility,
sunshine, snow depth and the coded present and past weather, plus the previous day's temperature
and wind extremes.

The data is published as one CSV file per station under
[weather_reports/poi](https://opendata.dwd.de/weather/weather_reports/poi/)
(`<station_id>-BEOB.csv`, the station id padded to five characters with underscores). Files are
latin-1 encoded, use `,` as the decimal separator and `---` for a missing value, and are timestamped
in UTC. No authentication is required.

This is the observed counterpart to [MOSMIX](../mosmix/index.md): the two share the MOSMIX station
catalogue, and a station keeps the same id in both, so a forecast can be compared against what was
actually measured. About 970 of the catalogue's ~5600 stations report, in Germany and abroad.

Two of the file's 41 columns are not served: the 24-hour global and direct radiation. They are
declared in W/m², which a 24-hour figure cannot be, and measured against the daily total the hourly
column sums to they come out proportional with a factor of 1.573 — a real daily total in a unit
that is neither J/cm², kJ/m² nor W/m². Sum `radiation_global_intensity` over a day for the daily
total, or take it from [Observation](../observation/index.md).

Only the last day is served. Older values come from
[Observation](../observation/index.md) once the DWD has quality-checked them; the `present_weather`
code table is documented
[here](https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/csv/poi_present_weather_zuordnung_pdf.pdf).

```{toctree}
:hidden:

hourly.md
```
