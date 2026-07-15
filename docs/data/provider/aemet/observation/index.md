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

AEMET enforces a strict per-minute rate limit (HTTP 429) and has also been observed to
intermittently drop connections outright. Requests hitting either are retried
automatically with a growing backoff (a few seconds up to roughly a minute), so a single
call can take noticeably longer than usual — up to a few minutes in the worst case —
if AEMET is rate limiting or having connectivity issues, rather than failing outright.

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
