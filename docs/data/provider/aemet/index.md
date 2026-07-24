# AEMET

State Meteorological Agency of Spain (Agencia Estatal de Meteorología)

## Overview

AEMET publishes climatological data from the Spanish weather station network through its
OpenData portal, covering hourly, daily, monthly and annual resolution. Access requires a
free API key, which you can request at
[opendata.aemet.es](https://opendata.aemet.es/centrodedescargas/altaUsuario) and provide via
the `WD_AUTH__AEMET` environment variable (or `Settings(auth={"aemet": "<api_key>"})`).

## License

AEMET provides its data as open data; please attribute AEMET as the source. See the
[legal notice](https://www.aemet.es/en/nota_legal) and the
[OpenData portal](https://opendata.aemet.es/) for the applicable terms.

```{toctree}
:hidden:

observation/index.md
```
