# Météo-France

French National Meteorological Service

## Overview

Météo-France publishes two distinct open data products as part of its Open Government Data offering on
[meteo.data.gouv.fr](https://meteo.data.gouv.fr/):

- **synop**: SYNOP (surface synoptic observation) data of about 190 stations across metropolitan France and its
  overseas territories, at their native 3-hourly reporting interval, from 1996 to present.
- **observation**: "Données climatologiques de base", daily and monthly climatological summaries from a much
  larger network of several thousand stations, sharded by French department.

## License

Météo-France data is published under the [Etalab Open License 2.0](https://www.data.gouv.fr/pages/legal/licences/etalab-2.0),
which asks for the source and the date of the most recent update of the information reused. The answers of
`observation` report that date as `data_updated_at` of their [`metadata`](../../../usage/restapi.md#response-metadata)
(the newest `last_modified` data.gouv.fr gives the files read) and in the `X-Wetterdienst-Data-Updated-At` header; those
of `synop` do not yet, and say `null`.

```{toctree}
:hidden:

synop/index.md
observation/index.md
```
