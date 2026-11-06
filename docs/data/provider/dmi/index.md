# DMI

Danish Meteorological Institute (Danmarks Meteorologiske Institut)

## Overview

DMI publishes quality-controlled climate data from stations in Denmark, Greenland and the
Faroe Islands (~1060 stations), covering hourly, daily, monthly and annual resolution,
through its Open Data climateData API. No authentication is required.

## License

DMI's open data are distributed under the Creative Commons Attribution 4.0 licence (CC BY 4.0), as the
[terms of use](https://www.dmi.dk/friedata/dokumentation/terms-of-use) say: give appropriate credit, link the
licence and say if you changed the data. DMI prescribes no wording; the
[DMI Open Data documentation](https://www.dmi.dk/friedata/dokumentation/basics) and the
[DMI frie data](https://www.dmi.dk/friedata/) pages have the rest.

The terms page was read live on 2026-11-06 (it had only been reachable through an archive copy before); it still says
"The license terms were changed November 30th 2023." What it asks of a caller: "Use of DMI's API's and Bulk Download
Services retrieval of data is open and user registration is no longer required"; DMI "reserves the right to set up
detailed terms in relation to 'fair use' ... including the right to adjust the bandwidth for individual IP addresses if
these strain DMI's services to a disproportionately wide extent"; and the fair use guidelines ask to "Use filtering and
query parameters to request only the the data you actually need", to "Avoid unnecessary polling" and to "Cache your API
requests where possible". It also says the observations "are raw, not quality assured meassurements, which may be
faulty", and that its logs of requests (IP address, URL, time) are kept for up to 60 months. Wetterdienst caches a
request for five minutes and filters by station and time window.

```{toctree}
:hidden:

observation/index.md
```
