# DWD (Deutscher Wetterdienst)

## Overview

The data as offered by the DWD through ``wetterdienst`` includes:

- Historical Weather Observations
    - Historical (last ~300 years), recent (500 days to yesterday), now (yesterday up to last hour)
    - every minute to yearly resolution
    - Time series of stations in Germany
- Mosmix 
    - statistical optimized scalar forecasts extracted from weather models
    - Point forecast
    - 5400 stations worldwide
    - Both MOSMIX-L and MOSMIX-S is supported
    - Up to 115 parameters
- DMO
    - scalar forecasts extracted from weather models
    - Point forecast
    - ICON and ICON-EU model
    - 78 hours lead time
    - Hourly and 3-hourly resolution
    - 115 parameters
    - 5400 stations worldwide
- Radar
    - 16 locations in Germany
    - All of composite, radolan, radvor, sites and radolan_cdc
    - Radolan: calibrated radar precipitation
    - Radvor: radar precipitation forecast

For a quick overview of the work of the DWD check the current 
[dwd report](https://www.dwd.de/SharedDocs/downloads/DE/allgemein/zahlen_und_fakten.pdf?__blob=publicationFile&v=14) 
(only in german language).

## License

The German Weather Service specified their data as being open though they ask you to
reference them as copyright owner. Take a look at the 
[Open Data Strategy at the DWD](https://www.dwd.de/EN/ourservices/opendata/opendata.html)
and the [Official Copyright](https://www.dwd.de/EN/service/copyright/copyright_artikel.html?nn=495490&lsbId=627548) 
statements before using the data.
