# MET Norway

Norwegian Meteorological Institute (Meteorologisk institutt)

## Overview

MET Norway publishes historical and recent observations from the Norwegian station network
(~2200 stations) through its Frost API, covering 10-minute, hourly, 6-hourly (historical
only), daily, monthly and annual resolution. Access requires free client credentials, which
you can request at [frost.met.no](https://frost.met.no/auth/requestCredentials.html) and
provide via the `WD_AUTH__METNO_FROST` environment variable.

## License

MET Norway publishes its data under the
[Norwegian Licence for Open Government Data (NLOD) 2.0](https://data.norge.no/nlod/en/2.0) and
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and asks to be credited as the source ("Data from
MET Norway"); see its [licensing and data policy](https://api.met.no/doc/License) and the
[free meteorological data](https://www.met.no/en/free-meteorological-data) page. See the
[Frost API](https://frost.met.no/) documentation for details.

```{toctree}
:hidden:

frost/index.md
```
