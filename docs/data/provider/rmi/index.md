# RMI

Royal Meteorological Institute of Belgium (Koninklijk Meteorologisch Instituut / Institut
Royal Météorologique)

## Overview

RMI publishes observations from the automatic weather station (AWS) network in Belgium
(~14 stations, back to 1995) through its open GeoServer WFS, covering 10-minute, hourly and
daily resolution. No authentication is required.

## License

RMI AWS open data is published under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); RMI's own
catalogue records of the 10-minute, hourly and daily data
([`RMI_DATASET_AWS_10MIN`](https://opendata.meteo.be/geonetwork/srv/api/records/RMI_DATASET_AWS_10MIN/formatters/xml),
[`_1HOUR`](https://opendata.meteo.be/geonetwork/srv/api/records/RMI_DATASET_AWS_1HOUR/formatters/xml),
[`_1DAY`](https://opendata.meteo.be/geonetwork/srv/api/records/RMI_DATASET_AWS_1DAY/formatters/xml))
all say so. The terms of the [opendata.meteo.be](https://opendata.meteo.be/) platform ask
that RMI is named as the source of the raw data, next to the information.

The agreement text of the platform (a message inside the page's script, read 2026-11-06) says what the terms ask of
you. All its content "may be re-used, distributed or presented publicly, midst the user explicitly refers to the RMI as
the official source of the raw data". The open data "defined as high-value datasets (HVD) may be re-used under the
Creative Commons licence conditions CC BY 4.0 provided that the source is acknowledged". The credit rules say source
details are due "even if extracts of the data/services are used or if the data format is changed", and that for "more
advanced alterations or any processing" RMI "at least expects to be mentioned in a central list of references or in
the imprint/publishing details". The platform's climate gridded data (5 x 5 km, for registered academic users) "are not
part of the HVD datasets and therefore may not be re-used, distributed or presented publicly"; the library reads none
of it, only the automatic weather stations.

Whether RMI counts those stations as high-value data is not stated on its pages. Our reading: it does not change what
you may do. Weather-station observations are one of the meteorological categories of the regulation that defines
high-value datasets (EU 2023/138; the Annex itself was not read, EUMETNET's
[summary](https://www.eumetnet.eu/rodeo-project-launch/) says the regulation "defines requirements for surface weather observations"), the
catalogue record states CC BY 4.0, and the platform text allows re-use with the source named either way. Only RMI can
settle it for certain.

```{toctree}
:hidden:

observation/index.md
```
