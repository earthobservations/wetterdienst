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
(the newest `last_modified` data.gouv.fr gives the files that hold a row of the answer, as the listing said when it
was read, which is cached for 12 hours) and in the `X-Wetterdienst-Data-Updated-At` header. A copy of a file made
before the date the listing gives it is downloaded again, and replaced once the new one has arrived: if the file host
does not answer, an archive file that is cached for good (the years before last) is read from the copy from before
and dated as of the time it was made. A file of the current period, whose copy is kept for 5 minutes, is not served
stale once that has passed: the download error is raised.

The answers of `synop` report the `Last-Modified` of the year files whose rows the answer keeps, which is when
Météo-France last wrote them. A finished year cached before the library kept that date is downloaded once more, which
dates it, in one attempt (a few megabytes to some twenty per year). If the host does not answer, the copy that is held
is read with no date and a warning says so. A copy made since is not downloaded again, whether the file had a date or
not.

```{toctree}
:hidden:

synop/index.md
observation/index.md
```
