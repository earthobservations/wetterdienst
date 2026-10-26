# MET Norway

Norwegian Meteorological Institute (Meteorologisk institutt)

## Overview

MET Norway publishes historical and recent observations from the Norwegian station network
(~2200 stations) through its Frost API, covering 10-minute, hourly, 6-hourly (historical
only), daily, monthly and annual resolution. Access requires free client credentials, which
you can request at [frost.met.no](https://frost.met.no/auth/requestCredentials.html) and
provide via the `WD_AUTH__METNO_FROST` environment variable.

## License

MET Norway states that its data are licensed under the
[Norwegian Licence for Open Government Data (NLOD) 2.0](https://data.norge.no/nlod/en/2.0) and
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (the sentence on its
[licensing page](https://api.met.no/doc/License) says "and", so answers report `CC-BY-4.0 AND NLOD-2.0`:
the conditions of both apply. Both ask for credit to MET Norway and a reference to the licence; NLOD 2.0
also asks for a link to the licence and the source where practical and forbids misleading use or implying
endorsement, CC BY 4.0 a link to the licence and a note of changes), and asks to be credited as the source ("Data from
MET Norway"); see its [licensing and data policy](https://api.met.no/doc/License) and the
[free meteorological data](https://www.met.no/en/free-meteorological-data) page. See the
[Frost API](https://frost.met.no/) documentation for details.

```{toctree}
:hidden:

frost/index.md
```
