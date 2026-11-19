# Geosphere

Previously: Zentralanstalt für Meteorologie und Geodynamik / Zentral Agency for Meteorology and Geodynamics

## Overview

## License

GeoSphere Austria publishes the datasets read here under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (the licence is part of each dataset's metadata on the
[data hub](https://data.hub.geosphere.at/)), so GeoSphere Austria has to be credited as the source.
Check out [Geosphere Nutzungsbedingungen](https://data.hub.geosphere.at/about) for further information.

What the API documentation asks of a caller (read 2026-11-06): "A users requests are limited to 5 requests per second
and 240 requests per hour", with the headers `x-ratelimit-remaining-hour` and `ratelimit-reset`, "The server responses
with status code 429 when the rate limit is exceeded"; a request may hold at most 1,000,000 values as JSON or CSV
(10,000,000 as NetCDF) ([request limit](https://dataset.api.hub.geosphere.at/v1/docs/user-guide/request-limit.html)).
The documentation does not say what "a user" is: where an instance answers many callers from one address, the 240
requests an hour are probably shared by all of them, which is a reading. "All data that is publicly accessible without
authentication is licensed under Creative Commons Attribution 4.0"
([license](https://dataset.api.hub.geosphere.at/v1/docs/)), and the data hub says the licence of each dataset is in its
metadata. Wetterdienst does not retry a 429, which is a `ProviderRateLimitError` with the wait the hub sent, else a minute.

```{toctree}
:hidden:

observation/index.md
```