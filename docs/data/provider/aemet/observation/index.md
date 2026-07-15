# Observation

## Overview

AEMET OpenData provides access to historical daily, monthly, and annual climatological
values, as well as real-time (observación convencional) hourly observations, from
AEMET's station network across Spain. A free API key is required; request one at
[opendata.aemet.es](https://opendata.aemet.es/centrodedescargas/altaUsuario).

Set the API key via the `WD_AUTH__AEMET=<api_key>` environment variable or the
`Settings(auth={"aemet": "<api_key>"})` argument.

AEMET limits each request to a date range of at most 6 months for daily values, or 3
years (36 months) for monthly/annual values; wider ranges are automatically split into
multiple requests under the hood.

The `hourly` resolution is real-time data: it does not accept a date range at all and
does not offer historical backfill — AEMET always returns whatever rolling window of
recent observations (typically the last ~24h) it currently holds for the station.

## License

Data is © AEMET. See
[AEMET OpenData](https://www.aemet.es/en/datos_abiertos/AEMET_OpenData) for further
information and usage conditions.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
annual.md
```
