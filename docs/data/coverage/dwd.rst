DWD
###

Deutscher Wetterdient / German Weather Service

Overview
********

The data as offered by the DWD through ``wetterdienst`` includes:

- Historical Weather Observations
    - Historical (last ~300 years), recent (500 days to yesterday), now (yesterday up to last hour)
    - every minute to yearly resolution
    - Time series of stations in Germany
- Mosmix - statistical optimized scalar forecasts extracted from weather models
    - Point forecast
    - 5400 stations worldwide
    - Both MOSMIX-L and MOSMIX-S is supported
    - Up to 115 parameters
- Radar
    - 16 locations in Germany
    - All of composite, radolan, radvor, sites and radolan_cdc
    - Radolan: calibrated radar precipitation
    - Radvor: radar precipitation forecast

For a quick overview of the work of the DWD check the current `dwd report`_ (only in
german language).

.. _dwd report: https://www.dwd.de/SharedDocs/downloads/DE/allgemein/zahlen_und_fakten.pdf?__blob=publicationFile&v=14

License
*******

The German Weather Service specified their data as being open though they ask you to
reference them as copyright owner. Take a look at the `Open Data Strategy at the DWD`_
and the `Official Copyright`_ statements before using the data.

.. _Open Data Strategy at the DWD: https://www.dwd.de/EN/ourservices/opendata/opendata.html
.. _Official Copyright: https://www.dwd.de/EN/service/copyright/copyright_artikel.html?nn=495490&lsbId=627548

Products
********

.. toctree::
   :maxdepth: 1

   dwd/observation
   dwd/mosmix
   dwd/dmo
   dwd/road
   dwd/radar
