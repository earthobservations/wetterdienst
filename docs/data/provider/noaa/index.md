# NOAA (National Oceanic and Atmospheric Administration)

## Overview

NOAA's Global Historical Climatology Network (GHCN) provides hourly (GHCNh) and daily
weather observations from more than 100,000 stations around the globe, making it a valuable
source for weather services that do not publish their data themselves. No authentication is
required.

## License

GHCN data is provided by NOAA's National Centers for Environmental Information (NCEI) as
open data under CC0 1.0 (see [GHCN](ghcn/index.md#license)). See the
[GHCN daily product page](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily)
for citation and usage information.

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is when NCEI
last wrote the file of the station the values were read from (its `Last-Modified`).

```{toctree}
:hidden:

ghcn/index.md
```