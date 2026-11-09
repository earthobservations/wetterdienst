# MeteoSwiss

Federal Office of Meteorology and Climatology MeteoSwiss / MétéoSuisse / MeteoSvizzera

## Overview

MeteoSwiss publishes observation data of the SwissMetNet automatic weather station network (~158 stations) as part of
its Open Government Data (OGD) offering, accessible through a STAC API.

## License

MeteoSwiss data is published under the [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en) license, and
the source must be acknowledged as "Source: MeteoSwiss" (or the German, French or Italian form), as the
[terms of use](https://opendatadocs.meteoswiss.ch/general/terms-of-use) say. They also forbid excessive use of the
infrastructure, in particular high-frequency downloading of the same content.
Check out the [Open Data Documentation](https://opendatadocs.meteoswiss.ch/) for further information.

What the terms ask of a caller (read 2026-11-06): the infrastructure "may only be used to the extent necessary to access
the data"; "excessive use in terms of access frequency or data volume (in particular the high-frequency downloading of
the same content) is prohibited and may result in your access being restricted or blocked"; and "By acknowledging the
source, you must ensure that it does not appear as if MeteoSwiss supports you or your use in particular." The general
terms of the Federal Spatial Data Infrastructure (swisstopo) and the usage policies of the Swiss National Supercomputing
Centre (CSCS), whose object storage serves the files, apply as well; they have not been read here. Wetterdienst keeps a
file for five minutes, so the same file is not asked for again within that time; a server shared by many callers has
one cache for all of them, and an instance that is run without a cache (`WD_CACHE_DISABLE`) asks for the file again
each time.

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is when
MeteoSwiss last wrote the file or files the values were read from (their `Last-Modified`), the newest of those that
gave a reading.

```{toctree}
:hidden:

observation/index.md
```
