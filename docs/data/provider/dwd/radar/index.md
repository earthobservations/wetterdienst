# Radar

## Overview

The DWD provides several data products produced by radar for different 
[radar sites](https://opendata.dwd.de/weather/radar/sites/).
Those are not further explained as of their complexity. The DWD also offers 
[Radolan](https://www.dwd.de/DE/leistungen/radolan/radolan.html),
an advanced radar product with calibrated areal precipitation, and 
[Radvor](https://www.dwd.de/DE/leistungen/radvor/radvor.html), a
precipitation forecast based on radar. Further information on radar products can be
found their 
[radar products overview](https://www.dwd.de/DE/leistungen/radolan/produktuebersicht/radolan_produktuebersicht_pdf.pdf?__blob=publicationFile).

Radolan offers the user radar precipitation measurements that are calibrated with
ground based measurements. The data is offered in hourly and daily versions, both
being frequently updated for the recent version and data for each concluded year is
stored in the historical version. The daily version offers gliding sums of the last 24
hours while the hourly version offers hourly sums of precipitation. The precipitation
amount is given in 1/10 mm.

## BUFR products as DataFrame

Site products published in BUFR format (echo top, reflectivity) can optionally be parsed
into a [polars](https://pola.rs/) DataFrame. Enable the `read_bufr` setting and each
`RadarResult` returned by `query()` will carry the parsed data on its `.df` attribute (a long
frame with one row per grid pixel: station/grid metadata plus the pixel `value`, with missing
pixels as null); the raw payload remains available on `.data`. This requires the optional
`eccodes` and `bufr` dependency extras — without them, or with `read_bufr` disabled, `.df`
stays `None`.

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import DwdRadarParameter, DwdRadarDataFormat, DwdRadarValues
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite

request = DwdRadarValues(
    parameter=DwdRadarParameter.PE_ECHO_TOP,
    site=DwdRadarSite.BOO,
    fmt=DwdRadarDataFormat.BUFR,
    settings=Settings(read_bufr=True),
)
for result in request.query():
    print(result.df)
```
