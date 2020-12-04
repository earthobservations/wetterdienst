################
DWD data quality
################


************
Introduction
************
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

or have a look at the example program `dwd_describe_fields.py <https://github.com/earthobservations/wetterdienst/blob/master/example/dwd_describe_fields.py>`_.


*******
Details
*******

Validation and uncertainty estimate
===================================
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
======================
When data from both directories "historical" and "recent" are used together,
the difference in the quality control procedure should be considered.
There are still issues to be discovered in the historical data.
The DWD welcomes any hints to improve the data basis (see contact).


********
Examples
********
As an example, these sections display different means of
quality designations related to ``daily``/``hourly`` and
``10_minutes`` resolutions/products.

Daily and hourly quality
========================

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
==================

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
