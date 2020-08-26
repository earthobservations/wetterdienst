Introduction to wetterdienst
############################

.. image:: https://github.com/earthobservations/wetterdienst/workflows/Tests/badge.svg
   :target: https://github.com/earthobservations/wetterdienst/actions?workflow=Tests
.. image:: https://codecov.io/gh/earthobservations/wetterdienst/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/earthobservations/wetterdienst
.. image:: https://readthedocs.org/projects/wetterdienst/badge/?version=latest
    :target: https://wetterdienst.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status
.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black


.. image:: https://img.shields.io/pypi/pyversions/wetterdienst.svg
   :target: https://pypi.python.org/pypi/wetterdienst/
.. image:: https://img.shields.io/pypi/v/wetterdienst.svg
   :target: https://pypi.org/project/wetterdienst/
.. image:: https://img.shields.io/pypi/status/wetterdienst.svg
   :target: https://pypi.python.org/pypi/wetterdienst/
.. image:: https://pepy.tech/badge/wetterdienst/month
   :target: https://pepy.tech/project/wetterdienst/month
.. image:: https://img.shields.io/github/license/earthobservations/wetterdienst
   :target: https://github.com/earthobservations/wetterdienst/blob/master/LICENSE.rst
.. image:: https://zenodo.org/badge/160953150.svg
   :target: https://zenodo.org/badge/latestdoi/160953150


Welcome to wetterdienst, your friendly weather service library for Python from the
neighbourhood! We are a group of people, who try to make access to weather data in
Python feel like a warm summer breeze, similar to other projects like
`rdwd <https://github.com/brry/rdwd>`_
for the R language ,which originally drew our interest in this project. As we long-term
goal is to provide you with data from multiple weather services, we are still stuck with
the German Weather Service (DWD).

We currently cover

- historical weather data from ground stations
- RADOLAN fitted radar data for areal precipitation

and soon

- MOSMIX statistical optimized scalar forecasts extracted from weather models


To get better insight on which data we have currently made available, with this library
take a look at
`Data Coverage <https://wetterdienst.readthedocs.io/en/latest/pages/data_coverage.html>`_
.

**CAUTION**
Although the data is specified as being open, the DWD asks you to reference them as
Copyright owner. To check out further, take a look at the
`Open Data Strategy at the DWD <https://www.dwd.de/EN/ourservices/opendata/opendata.html>`_
and the
`Official Copyright <https://www.dwd.de/EN/service/copyright/copyright_artikel.html?nn=495490&lsbId=627548>`_

To keep you updated about added features etc. we provide a
`Changelog <https://wetterdienst.readthedocs.io/en/latest/pages/development.html#current>`_
.

We strongly recommend reading the full documentation, which will be updated continuously
as we make progress with this library:
https://wetterdienst.readthedocs.io/en/latest/

Getting started
***************

Run the following to make wetterdienst available in your current environment:

.. code-block:: Python

    pip install wetterdienst

To get some historical observed station data call

.. code-block:: Python

    from wetterdienst import collect_dwd_data
    from wetterdienst import Parameter, PeriodType, TimeResolution

    station_data = collect_dwd_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

Furthermore we currently offer:

- RADOLAN radar based precipitation for Germany
- getting metadata for a set of Parameter, PeriodType and TimeResolution
- getting station(s) nearby a selected location for a given set...

and also

- storing/recovering collected data
- a prepared Docker image to run the library dockerized
- a client to run the library from command line

For the whole functionality, check out the
`API <https://wetterdienst.readthedocs.io/en/latest/pages/api.html>`_
section of our documentation, which will be constantly updated. Also don't miss out our
`examples <https://github.com/earthobservations/wetterdienst/tree/master/example>`_
.



