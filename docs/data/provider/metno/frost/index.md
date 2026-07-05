# Frost

## Overview

The Frost API provides access to historical and recent observations from the Norwegian
Meteorological Institute's station network. An API client ID is required; register for
free at [frost.met.no](https://frost.met.no/auth/requestCredentials.html).

Set the client ID via the `WD_AUTH__METNO_FROST=<client_id>` environment variable or the
`Settings(auth={"metno_frost": "<client_id>"})` argument.

## License

Data is © Norwegian Meteorological Institute (MET Norway). See
[license terms](https://www.met.no/en/free-meteorological-data/Licensing-and-crediting).

```{toctree}
:hidden:

10_minutes.md
hourly.md
6_hour.md
daily.md
monthly.md
annual.md
```
