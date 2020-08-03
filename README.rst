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
neighbourhood! We are an group of people, who try to make access to weather data in
Python feel like a warm summer breeze, similar to other projects like
`rdwd <https://github.com/brry/rdwd>`_ ,
which originally drew our interest in this project. As we reach to provide you with data
from multiple weather services, we are still stuck with this one weather service from
Germany, that has questioned our believe in humanity. But we think we are at good
condition to make further progress to soon fully cover the German weather service, right
after finishing this documentation. But now it's up to you to take a closer look at
what we did here.

**CAUTION**
Although the data is specified as being open, the DWD asks you to reference them as
Copyright owner. To check out further, take a look at
`Open Data at the DWD <https://www.dwd.de/EN/ourservices/opendata/opendata.html>`_
and the
`Official Copyright <https://www.dwd.de/EN/service/copyright/copyright_artikel.html?nn=495490&lsbId=627548>`_

The full documentation of wetterdienst is available at:
https://wetterdienst.readthedocs.io/en/latest/

To keep you updated about added features etc. we provide a
`Changelog <https://wetterdienst.readthedocs.io/en/latest/pages/development.html#current>`_
. Furthermore to get insight on which data we have made available the section
`Data Coverage <https://wetterdienst.readthedocs.io/en/latest/pages/data_coverage.html>`_
may be of special interest for you.

Getting started
***************

Run the following

.. code-block:: Python

    pip install wetterdienst

to make wetterdienst available in your current environment. To get some historical
observed station data call

.. code-block:: Python

    from wetterdienst import collect_dwd_data
    from wetterdienst import Parameter, PeriodType, TimeResolution

    station_data = collect_dwd_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

For other examples and functionality such getting metadata, running the library in a
Docker image and a client take a look at the
`API <https://wetterdienst.readthedocs.io/en/latest/pages/api.html>`_
section, which will be constantly updated with new functions. Also don't miss out our
`examples <https://github.com/earthobservations/wetterdienst/tree/master/example>`_
.



