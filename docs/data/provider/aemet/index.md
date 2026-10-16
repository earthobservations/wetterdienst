# AEMET

State Meteorological Agency of Spain (Agencia Estatal de Meteorología)

## Overview

AEMET publishes climatological data from the Spanish weather station network through its
OpenData portal, covering hourly, daily, monthly and annual resolution. Access requires a
free API key, which you can request at
[opendata.aemet.es](https://opendata.aemet.es/centrodedescargas/altaUsuario) and provide via
the `WD_AUTH__AEMET` environment variable (or `Settings(auth={"aemet": "<api_key>"})`).

## License

AEMET allows the reuse of its data for commercial and non-commercial purposes if AEMET is cited as the
source ("© AEMET", or "Source: AEMET" for value-added services) and its data is not distorted. See the
[legal notice](https://www.aemet.es/en/nota_legal) and the
[OpenData portal](https://opendata.aemet.es/) for the applicable terms.

```{toctree}
:hidden:

observation/index.md
```
