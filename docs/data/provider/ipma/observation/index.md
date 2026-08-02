# Observation

## Overview

IPMA's open-data API provides near-real-time hourly observations from the Portuguese automatic
weather station network (~222 stations across mainland Portugal, the Azores and Madeira). No API key
or registration is required — the feed is fully public.

Two JSON feeds are used: a station catalogue (`stations.json`, a bare array of GeoJSON Feature objects giving
each station's id, name and coordinates) and a single all-stations observation feed
(`observations.json`) holding roughly the last day of hourly readings. Because the feed is a rolling
window, only the `recent` period is available — there is no historical archive, so a date range
within roughly the last 24 hours must be given.

The catalogue exposes no elevation, so `height` is always null, and — being a live feed — there is
no operational start/end date per station. Wind direction is published as an 8-point code and is
converted to degrees; pressure is reduced to mean sea level; radiation is global solar radiation in
kJ/m². The value `-99.0` marks missing data and becomes null. The `intensidadeVentoKM` field (the
same wind speed in km/h) is not exposed, as it duplicates `intensidadeVento` (m/s).

## License

Data is © IPMA (Instituto Português do Mar e da Atmosfera). See the [IPMA API](https://api.ipma.pt/)
for further information and usage conditions.

```{toctree}
:hidden:

hourly.md
```
