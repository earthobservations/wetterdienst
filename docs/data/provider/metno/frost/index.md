# Frost

## Overview

The Frost API provides access to historical and recent observations from the Norwegian
Meteorological Institute's station network. An API client ID is required; register for
free at [frost.met.no](https://frost.met.no/auth/requestCredentials.html).

Set the client ID via the `WD_AUTH__METNO_FROST=<client_id>` environment variable or the
`Settings(auth={"metno_frost": "<client_id>"})` argument.

## Stations

The station list is Frost's catalogue of `SensorSystem` sources, about 2,200 entries. 24 of
them have no position: Frost gives them no `geometry`, and no latitude or longitude in any other
field. They are mobile platforms, such as ships (`SN76999` SCARABEO 8, `SN77049` MS ASTERIX,
`SN20930` POLARSTERN), rigs (`SN76946` ROSS RIG) and gliders (`SN20957` SG644 GLIDER), 20 of them
with ship codes, so there is no fixed place to state. They stay in the list with a null
`latitude` and `longitude`, and a search by distance or bounding box, an interpolation or a
summary never picks them.

The list also holds about 237 foreign SYNOP stations, with ids made of `SN` and the WMO number
times 100 (`SN743400` is Limoges-Bellegarde in France, `SN623500` De Kooy in the Netherlands,
`SN848200` Malaga in Spain). Frost serves observations for them, but mostly with short, recent
series: those of Limoges and De Kooy start on 2026-10-26. They show up in `stations`, so
check the dates a station has values for before relying on a long record.

## Time window

Every resolution needs a window, because Frost is asked for one reference time range. The REST
API, the CLI and MCP refuse a request for values without a start and end date (REST API: 400,
`timestamp` is required), and so does the Python API: `stations.values()` raises `DateRequiredError`
(a `ValueError`) naming the dataset. Pass `start` and `end` to the request. Stations can be listed
without a window.

## The source's own verdict (`source`)

Every value carries Frost's `qualityCode` as the plain flag of `quality_flags`. The check `source` reads the one code that
Frost's [data clarifications](https://frost.met.no/dataclarifications.html#quality-code) word as a verdict: `7`,
"Erroneous, value is not corrected". The page says "Frost tries to give the user a single value to represent the general
quality of the observation. This value is set in the field qualityCode", and lists `0` "OK, value is controlled and found
O.K.", `1` "OK, value is controlled and corrected, or value is missing and interpolated", `2` "Slightly uncertain, value
is not controlled", `4` "Slightly uncertain, value is not corrected", `5` "Very uncertain, value is not corrected" and
`6` "Very uncertain, model data. Value is controlled and corrected, or value is missing and is interpolated - automatic".
Those are a degree of confidence, a treatment or a model, no verdict, and are not read. Frost needs a client id, so this
mapping rests on the documentation and was not probed live.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the
default is `soft`, which keeps the value and writes `suspect:source`, so interpolation, summaries and climate stripes leave it
out. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

## License

Data is © Norwegian Meteorological Institute (MET Norway). See
[license terms](https://www.met.no/en/free-meteorological-data/Licensing-and-crediting).

```{toctree}
:hidden:

10_minutes.md
hourly.md
6_hours.md
daily.md
monthly.md
annual.md
```
