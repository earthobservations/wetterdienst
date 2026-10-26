# MeteoSwiss

Federal Office of Meteorology and Climatology MeteoSwiss / MétéoSuisse / MeteoSvizzera

## Overview

MeteoSwiss publishes observation data of the SwissMetNet automatic weather station network (~158 stations) as part of
its Open Government Data (OGD) offering, accessible through a STAC API.

## License

MeteoSwiss data is published under the [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en) license.
Check out the [Open Data Documentation](https://opendatadocs.meteoswiss.ch/) for further information.

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is when
MeteoSwiss last wrote the file or files the values were read from (their `Last-Modified`), the newest of those that
gave a reading.

```{toctree}
:hidden:

observation/index.md
```
