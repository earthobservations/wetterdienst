# Observation

## Overview

LHMT's `api.meteo.lt` REST API provides hourly observations from the Lithuanian automatic weather
station network (~52 stations). No API key or registration is required — the API is fully public.

Two endpoints are used: a station list (`/v1/stations`, giving each station's code, name and
coordinates) and per-station, per-day observation days
(`/v1/stations/{code}/observations/{YYYY-MM-DD}`, one entry per hour). Unlike a rolling now-cast
feed, the API serves historical data — reaching back to roughly 2016 — so a date range must be
given and the provider fetches one day per station per day in the range.

Values are already published in canonical units (temperature °C, wind m/s, direction in degrees,
sea-level pressure hPa, humidity and cloud cover %, precipitation mm, snow depth cm) with `null` for
missing data — there is no sentinel. The API also returns `feelsLikeTemperature` (apparent
temperature) and a textual `conditionCode`, which are not exposed as they have no clean numeric
canonical parameter. The catalogue carries no elevation, so `height` is always null, and — being a
live API — there is no operational start/end date per station.

## License

Data is © LHMT (Lietuvos hidrometeorologijos tarnyba). See [api.meteo.lt](https://api.meteo.lt/) for
further information and usage conditions.

```{toctree}
:hidden:

hourly.md
```
