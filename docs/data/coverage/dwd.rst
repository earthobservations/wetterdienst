DWD (German Weather Service)
****************************

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

Historical Weather Observations
===============================

Overview
________

The big treasure of the DWD is buried under a clutter of a file_server_.
The data you find here can reach back to 19th century and is represented by over 1000
stations in Germany according to the report referenced above. The amount of stations
that cover a specific parameter may differ strongly, so don't expect the amount of data
to be that generous for all the parameters.

Available dataa/parameters on the file server is sorted in different time resolutions:

- **1_minute** - measured every minute
- **10_minutes** - measured every 10 minutes
- **hourly** - measured every hour
- **subdaily** - measured 3 times a day
- **daily** - measured once a day
- **monthly** - measured/summarized once a month
- **annual** - measured/summarized once a year

Depending on the time resolution of the parameter you may find different periods that
the data is offered in:

- **historical** - values covering all the measured data
- **recent** - recent values covering data from latest plus a certain range of historical data
- **now** - current values covering only latest data

The period relates to the amount of data that is measured, so measuring a parameter
every minute obviously results an a much bigger amount of data and thus smaller chunks
of data are needed to lower the stress on data transfer, e.g. when updating your
database you probably won't need to stream all the historical data every day. On the
other hand this will also save you a lot of time as the size relates to the processing
time your machine will require.

The table below lists every (useful) parameter on the file server with its combinations
of available time resolutions. In general only 1-minute and 10-minute data is offered
in the "now" period, although this may change in the future.

The two parameter strings reflect on how we call a parameter e.g. "PRECIPITATION" and
how the DWD calls the parameter e.g. "precipitation".

+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
|Parameter\Granularity                              | 1_minute              | 10_minutes            | hourly                | subdaily              | daily                 | monthly               | annual                |
+===================================================+=======================+=======================+=======================+=======================+=======================+=======================+=======================+
| `PRECIPITATION = "precipitation"`                 | |check|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `TEMPERATURE_AIR = "air_temperature"`             | |cross|               | |check|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `TEMPERATURE_EXTREME = "extreme_temperature"`     | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WIND_EXTREME = "extreme_wind"`                   | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `SOLAR = "solar"`                                 | |cross|               | |check|               | |check|               | |cross|               | |check|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WIND = "wind"`                                   | |cross|               | |check|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `CLOUD_TYPE = "cloud_type"`                       | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `CLOUDINESS = "cloudiness"`                       | |cross|               | |cross|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `DEW_POINT = "dew_point"`                         | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `PRESSURE = "pressure"`                           | |cross|               | |cross|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `TEMPERATURE_SOIL = "soil_temperature"`           | |cross|               | |cross|               | |check|               | |cross|               | |check|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `SUNSHINE_DURATION = "sun"`                       | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `VISBILITY = "visibility"`                        | |cross|               | |cross|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WIND_SYNOPTIC = "wind_synop"`                    | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `MOISTURE = "moisture"`                           | |cross|               | |cross|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `CLIMATE_SUMMARY = "kl"`                          | |cross|               | |cross|               | |cross|               | |check|               | |check|               | |check|               | |check|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `PRECIPITATION_MORE = "more_precip"`              | |cross|               | |cross|               | |cross|               | |cross|               | |check|               | |check|               | |check|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WATER_EQUIVALENT = "water_equiv"`                | |cross|               | |cross|               | |cross|               | |cross|               | |check|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WEATHER_PHENOMENA = "weather_phenomena"`         | |cross|               | |cross|               | |cross|               | |cross|               | |check|               | |check|               | |check|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+

.. |check| unicode:: + .. check
.. |cross| unicode:: - .. cross

This table and subsets of it can be printed with a function call of
``.discover()`` as described in the API section. Furthermore individual
parameters can be queried. Take a look at the massive amount of data:

.. ipython:: python

    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    meta = DwdObservationRequest.discover(flatten=False)

    # Selection of daily historical data
    print(meta)

.. _file_server: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/

Quality
_______

The DWD designates its data points with specific quality levels expressed as "quality bytes".

- The "recent" data have not completed quality control yet.
- The "historical" data are quality controlled measurements and observations.

The following information has been taken from PDF documents on the DWD open data
server like `data set description for historical hourly station observations of precipitation for Germany <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/historical/DESCRIPTION_obsgermany_climate_hourly_precipitation_historical_en.pdf>`_.
Wetterdienst provides convenient access to the relevant details
by using routines to parse specific sections of the PDF documents.

For example, use commands like these for accessing this information::

    # Historical hourly station observations of precipitation for Germany.
    # English language.
    wetterdienst dwd about fields --parameter=precipitation --resolution=hourly --period=historical

    # Historical 10-minute station observations of pressure, air temperature (at 5cm and 2m height), humidity and dew point for Germany.
    # German language.
    wetterdienst dwd about fields --parameter=air_temperature --resolution=10_minutes --period=historical --language=de

or have a look at the example program `dwd_describe_fields.py <https://github.com/earthobservations/wetterdienst/blob/main/example/dwd_describe_fields.py>`_.

Details
^^^^^^^

Validation and uncertainty estimate
"""""""""""""""""""""""""""""""""""
Considerations of quality assurance are explained in Kaspar et al., 2013.

Several steps of quality control, including automatic tests for completeness,
temporal and internal consistency, and against statistical thresholds based
on the software QualiMet (see Spengler, 2002) and manual inspection had been
applied.

Data are provided "as observed", no homogenization has been carried out.

The history of instrumental design, observation practice, and possibly changing
representativity has to be considered for the individual stations when interpreting
changes in the statistical properties of the time series. It is strongly suggested
to investigate the records of the station history which are provided together with
the data. Note that in the 1990s many stations had the transition from manual to
automated stations, entailing possible changes in certain statistical properties.

Additional information
""""""""""""""""""""""
When data from both directories "historical" and "recent" are used together,
the difference in the quality control procedure should be considered.
There are still issues to be discovered in the historical data.
The DWD welcomes any hints to improve the data basis (see contact).


Examples
^^^^^^^^
As an example, these sections display different means of
quality designations related to ``daily``/``hourly`` and
``10_minutes`` resolutions/products.

Daily and hourly quality
""""""""""""""""""""""""

The quality levels "Qualitätsniveau" (QN) given here
apply for the respective following columns. The values
are the minima of the QN of the respective daily
values. QN denotes the method of quality control,
with which erroneous values are identified and apply
for the whole set of parameters at a certain time.

For the individual parameters there exist quality bytes
in the internal DWD data base, which are not published here.
Values identified as wrong are not published.

Various methods of quality control (at different levels) are
employed to decide which value is identified as wrong. In the
past, different procedures have been employed.
The quality procedures are coded as following.

Quality level (column header: ``QN_``):

.. code-block:: text

    1- Only formal control during decoding and import
    2- Controlled with individually defined criteria
    3- ROUTINE control with QUALIMET and QCSY
    5- Historic, subjective procedures
    7- ROUTINE control, not yet corrected
    8- Quality control outside ROUTINE
    9- ROUTINE control, not all parameters corrected
    10- ROUTINE control finished, respective corrections finished

10 minutes quality
""""""""""""""""""

The quality level "Qualitätsniveau" (QN) given here
applies for the following columns. QN describes
the method of quality control applied to a complete
set of parameters, reported at a common time.

The individual parameters of the set are connected with
individual quality bytes in the DWD data base, which are
not given here. Values marked as wrong are not given here.

Different quality control procedures (and at different
levels) have been applied to detect which values are
identified as erroneous or suspicious. Over time,
these procedures have changed.

Quality level (column header: ``QN``):

.. code-block:: text

    1- Only formal control during decoding and import
    2- Controlled with individually defined criteria
    3- ROUTINE automatic control and correction with QUALIMET

Mosmix
======

Mosmix_ is a forecast product of the DWD that is based on global weather models and that
uses statistical downscaling for land-based climate stations based on their historical
observations to provide more precise, local forecast. Mosmix is available for over 5000
stations worldwide and is available in two versions, Mosmix-S and Mosmix-L. Mosmix-S
comes with a set of 40 parameters and is published every hour while MOSMIX-L has a set
of about 115 parameters and is released every 6 hours (3am, 9am, 3pm, 9pm). Both
versions have a forecast limit of 240h.

.. ipython:: python

    from wetterdienst.provider.dwd.forecast import DwdMosmixRequest

    meta = DwdMosmixRequest.discover(flatten=False)

    # Selection of daily historical data
    print(meta)

.. _Mosmix: https://www.dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html

Radar
=====

The DWD provides several data products produced by radar for different `radar sites`_.
Those are not further explained as of their complexity. The DWD also offers Radolan_,
an advanced radar product with calibrated areal precipitation, and Radvor_, a
precipitation forecast based on radar. Further information on radar products can be
found their `radar products overview`_.

Radolan offers the user radar precipitation measurements that are calibrated with
ground based measurements. The data is offered in hourly and daily versions, both
being frequently updated for the recent version and data for each concluded year is
stored in the historical version. The daily version offers gliding sums of the last 24
hours while the hourly version offers hourly sums of precipitation. The precipitation
amount is given in 1/10 mm.

.. _radar sites: https://opendata.dwd.de/weather/radar/sites/
.. _Radolan: https://www.dwd.de/DE/leistungen/radolan/radolan.html
.. _Radvor: https://www.dwd.de/DE/leistungen/radvor/radvor.html
.. _radar products overview: https://www.dwd.de/DE/leistungen/radolan/produktuebersicht/radolan_produktuebersicht_pdf.pdf?__blob=publicationFile
