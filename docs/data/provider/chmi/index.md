# CHMI

Czech Hydrometeorological Institute (Český hydrometeorologický ústav)

## Overview

CHMI publishes observations from the Czech weather station network as open CSV data,
covering 10-minute, hourly, daily, monthly and annual resolution. No authentication is
required.

## License

CHMI data is provided as open data through the [CHMI open data portal](https://opendata.chmi.cz/) under the
[Creative Commons Attribution 4.0 International licence (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/):
"Otevřená data ČHMÚ můžete využívat bezplatně při respektování licence Creative Commons BY 4.0"
(CHMI's FAQ, a page that is no longer online). The portal's listing itself says
nothing; the national open data catalogue (data.gov.cz) names the licence and the author, "Český hydrometeorologický
ústav", for each dataset. CHMI gives no credit line of its own: name the author, link the licence and say if you
changed the data.

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is when CHMI
last wrote the file or files the values were read from (their `Last-Modified`), the newest of those that gave a
reading.

```{toctree}
:hidden:

observation/index.md
```
