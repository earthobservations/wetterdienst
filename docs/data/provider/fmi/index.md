# FMI

Finnish Meteorological Institute (Ilmatieteen laitos)

## Overview

FMI publishes observations from the Finnish weather station network through its open WFS
interface, covering hourly and daily resolution. No authentication is required.

## License

FMI open data is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), as FMI's
[open data licence](https://en.ilmatieteenlaitos.fi/open-data-licence) page states. FMI names no
wording for the credit; CC BY asks for appropriate credit, a link to the licence and a note of
changes.

What the [open data manual](https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services) asks of a caller (read
2026-11-06): "User must accept Creative Commons license before using the open data service interfaces." and "Services
contain user specific request limitations: Download Service has limit of 20000 requests per day, View Service has limit
of 10000 requests per day, Download and View Services have combined limit of 600 requests per 5 minutes". The manual does
not say what a "user" is; where an instance answers many callers from one address they probably share these limits,
which is a reading. Wetterdienst reads the Download Service, with windows of at most 168 hours per request for the
sub-daily data, and caches a request for five minutes.

```{toctree}
:hidden:

observation/index.md
```
