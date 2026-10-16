# KNMI

Royal Netherlands Meteorological Institute (Koninklijk Nederlands Meteorologisch
Instituut)

## Overview

KNMI publishes observations from the Dutch weather station network through its Data
Platform, covering 10-minute, hourly and daily resolution. Access requires a free API key,
which you can request at
[developer.dataplatform.knmi.nl](https://developer.dataplatform.knmi.nl/) and provide via
the `WD_AUTH__KNMI` environment variable (or `Settings(auth={"knmi": "<api_key>"})`).

## License

KNMI data is published as open data through the
[KNMI Data Platform](https://dataplatform.knmi.nl/), where each of the three datasets read here
(10-minute, hourly and daily in-situ observations) lists its licence as
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

```{toctree}
:hidden:

observation/index.md
```
