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

The legal notice (read 2026-11-06; the OpenAPI document of the portal names it as the licence, "Condiciones de uso de
reutilización") lists the conditions of reuse: "1. Distortion of the information is forbidden."; AEMET is cited as
the source, with "© AEMET" where only the presentation changes and "Source: AEMET" "if the reuse includes value-added
services"; "3. The date of the last update of the documents being reused must be mentioned, provided this date was
included in the original document."; "4. Declaration, insinuation, or suggestion that AEMET ... participates, sponsors,
or supports this information's reuse is forbidden."; and "5. The integrity of the metadata on the date of update and the
applicable reuse conditions that, if applicable, were included in the document ... must be retained." Wetterdienst
reshapes the data into one table and converts units, which changes presentation and not the numbers; whether that keeps
the "technical content" intact is for AEMET to say. The pages read state no number of requests (the OpenAPI document
lists a 429 for "a request that exceeds the limits of the service"), and say of the API key only that it identifies the
user ("an identifier by which the accesses a user makes to the API are counted and attributed", our translation), that
as many can be created as needed, and that it is requested with an e-mail address. They say nothing about sharing a key
or serving others with it.

```{toctree}
:hidden:

observation/index.md
```
