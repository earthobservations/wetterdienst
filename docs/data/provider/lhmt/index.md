# LHMT

Lietuvos hidrometeorologijos tarnyba (Lithuanian Hydrometeorological Service)

## Overview

LHMT publishes hourly observations from the Lithuanian station network through the key-less
`api.meteo.lt` JSON REST API. No authentication is required.

## License

LHMT data is provided as open data through [api.meteo.lt](https://api.meteo.lt/), "unless stated
otherwise" under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), which asks for the source
(the Lithuanian Hydrometeorological Service) to be named and for derived data to be shared alike.

The conditions of use on the [portal](https://api.meteo.lt/) (Lithuanian, read 2026-11-06; translated by us) also say
the data may be used "only for lawful and defined purposes", are given "as they are, without any guarantees", and that
"when publishing, reproducing or otherwise using the data, it is necessary to state that the source of the data is the
Service. If the source of the data is not stated, access to the data may be ended." They limit the requests: "The number
of requests from one IP address is limited to 180 requests per minute. Please do not generate more than 20,000 requests
per day from one IP address, because if the stated limit is exceeded your IP address may be blocked without warning."
The limit is per address, so an instance that answers many callers counts as one.

```{toctree}
:hidden:

observation/index.md
```
