Wetterdienst - Open weather data for humans
###########################################

.. container:: align-center

    .. figure:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/temperature_ts.png
        :alt: temperature timeseries of Hohenpeissenberg/Germany

    *"Three things are (almost) infinite: the universe, human stupidity and the temperature time series of
    Hohenpeissenberg I got with the help of wetterdienst; and I'm not sure about the universe." - Albert Einstein*


.. overview_start_marker

Overview
########

.. image:: https://github.com/earthobservations/wetterdienst/workflows/Tests/badge.svg
   :target: https://github.com/earthobservations/wetterdienst/actions?workflow=Tests
.. image:: https://codecov.io/gh/earthobservations/wetterdienst/branch/main/graph/badge.svg
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
   :target: https://github.com/earthobservations/wetterdienst/blob/main/LICENSE
.. image:: https://zenodo.org/badge/160953150.svg
   :target: https://zenodo.org/badge/latestdoi/160953150
.. image:: https://img.shields.io/discord/704622099750191174.svg?label=&logo=discord&logoColor=ffffff&color=7389D8&labelColor=6A7EC2
   :target: https://discord.gg/8sCb978a

Introduction
************

Welcome to Wetterdienst, your friendly weather service library for Python.

We are a group of like-minded people trying to make access to weather data in
Python feel like a warm summer breeze, similar to other projects like
rdwd_ for the R language, which originally drew our interest in this project.
Our long-term goal is to provide access to multiple weather services as well as other
related agencies such as river measurements. With ``wetterdienst`` we try to use modern
Python technologies all over the place. The library is based on pandas_ across the board,
uses Poetry_ for package administration and GitHub Actions for all things CI.
Our users are an important part of the development as we are not currently using the
data we are providing and only implement what we think would be the best. Therefore
contributions and feedback whether it be data related or library related are very
welcome! Just hand in a PR or Issue if you think we should include a new feature or data
source.

.. _rdwd: https://github.com/brry/rdwd
.. _pandas: https://pandas.pydata.org/
.. _Poetry: https://python-poetry.org/

Acknowledgements
****************

We want to acknowledge all environmental agencies which provide their data open and free
of charge first and foremost for the sake of endless research possibilities.

We want to acknowledge Jetbrains_ and their `open source team`_ for providing us with
licenses for Pycharm Pro, which we are using for the development.

We want to acknowledge all contributors for being part of the improvements to this
library that make it better and better every day.

.. _Jetbrains: https://www.jetbrains.com/
.. _open source team: https://github.com/JetBrains

Coverage
********

DWD (German Weather Service / Deutscher Wetterdienst / Germany)
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
        - All of Composite, Radolan, Radvor, Sites and Radolan_CDC
        - Radolan: calibrated radar precipitation
        - Radvor: radar precipitation forecast

To get better insight on which data we have currently made available and under which
license those are published take a look at the data_ section.

.. _data: https://wetterdienst.readthedocs.io/en/latest/data/index.html

Features
********

- API(s) for stations (metadata) and values
- Get station(s) nearby a selected location
- Define your request by arguments such as `parameter`, `period`, `resolution`,
  `start date`, `end date`
- Command line interface
- Web-API via FastAPI
- Run SQL queries on the results
- Export results to databases and other data sinks
- Public Docker image

Setup
*****

``wetterdienst`` can be used by either installing it on your workstation or within a Docker
container.

Native
======

Via PyPi (standard):

.. code-block:: bash

    pip install wetterdienst

Via Github (most recent):

.. code-block:: bash

    pip install git+https://github.com/earthobservations/wetterdienst

There are some extras available for ``wetterdienst``. Use them like:

.. code-block:: bash

    pip install wetterdienst[http,sql]

- docs: Install the Sphinx documentation generator.
- ipython: Install iPython stack.
- excel: Install openpyxl for Excel export.
- http: Install HTTP API prerequisites.
- sql: Install DuckDB for querying data using SQL.
- duckdb: Install support for DuckDB.
- influxdb: Install support for InfluxDB.
- cratedb: Install support for CrateDB.
- mysql: Install support for MySQL.
- postgresql: Install support for PostgreSQL.

In order to check the installation, invoke:

.. code-block:: bash

    wetterdienst --help

.. _run-in-docker:

Docker
======

Docker images for each stable release will get pushed to GitHub Container Registry.

There are images in two variants, ``wetterdienst-standard`` and ``wetterdienst-full``.

``wetterdienst-standard`` will contain a minimum set of 3rd-party packages,
while ``wetterdienst-full`` will try to serve a full environment by also
including packages like GDAL and wradlib.

Pull the Docker image:

.. code-block:: bash

    docker pull ghcr.io/earthobservations/wetterdienst-standard

Library
-------
Use the latest stable version of ``wetterdienst``:

.. code-block:: bash

    $ docker run -ti ghcr.io/earthobservations/wetterdienst-standard
    Python 3.8.5 (default, Sep 10 2020, 16:58:22)
    [GCC 8.3.0] on linux

.. code-block:: python

    import wetterdienst
    wetterdienst.__version__

Command line script
-------------------
The ``wetterdienst`` command is also available:

.. code-block:: bash

    # Make an alias to use it conveniently from your shell.
    alias wetterdienst='docker run -ti ghcr.io/earthobservations/wetterdienst-standard wetterdienst'

    wetterdienst --version
    wetterdienst --help

Example
********

Acquisition of historical data for specific stations using ``wetterdienst`` as library:

.. code-block:: python

    >>> from wetterdienst.dwd.observations import (
    ...     DWDObservationValues,
    ...     DWDObservationParameterSet,
    ...     DWDObservationPeriod,
    ...     DWDObservationResolution
    ... )
    >>> observations = DWDObservationValues(
    ...    station_id=[1048,4411],
    ...    parameter=[DWDObservationParameterSet.CLIMATE_SUMMARY,
    ...                DWDObservationParameterSet.SOLAR],
    ...    resolution=DWDObservationResolution.DAILY,
    ...    start_date="1990-01-01",  # Timezone: UTC
    ...    end_date="2020-01-01",  # Timezone: UTC
    ...    tidy_data=True,  # default
    ...    humanize_parameters=True,  # default
    ... )
    >>> df = observations.all()

Receiving of stations for defined parameters using the ``wetterdienst`` client:

.. code-block:: bash

    # Get list of all stations for daily climate summary data in JSON format
    wetterdienst dwd observations stations --parameter=kl --resolution=daily --period=recent

    # Get daily climate summary data for specific stations
    wetterdienst dwd observations values --station=1048,4411 --parameter=kl --resolution=daily --period=recent

Further examples (code samples) can be found in the `examples`_ folder.

.. _examples: https://github.com/earthobservations/wetterdienst/tree/main/example

.. overview_end_marker

Documentation
*************

We strongly recommend reading the full documentation, which will be updated continuously
as we make progress with this library:

https://wetterdienst.readthedocs.io/

For the whole functionality, check out the `Wetterdienst API`_ section of our
documentation, which will be constantly updated. To stay up to date with the
development, take a look at the changelog_. Also, don't miss out our examples_.

Data license
************

Licenses of the available data can be found in our documentation at the `data license`_
section. Licenses and usage requirements may differ so check this out before including
the data in your project to be sure to fulfill copyright issues beforehand.

.. _data license: https://wetterdienst.readthedocs.io/en/latest/pages/data_license.html

.. contribution_development_marker

Contribution
************

There are different ways in which you contribute to this library:

- by handing in a PR which describes the feature/issue that was solved including tests
  for newly added features
- by using our library and reporting bugs to us either by mail or by creating a new
  Issue
- by letting us know either via issue or discussion what function or data source we may
  include into this library describing possible solutions or acquisition
  methods/endpoints/APIs

Development
***********

1. Clone the library and install the environment

.. code-block:: bash

    git clone https://github.com/earthobservations/wetterdienst
    cd wetterdienst

    pip install . # or poetry install

2. Add required libraries e.g.

.. code-block:: bash

    poetry add pandas

3. Apply your changes

4. Add tests and documentation for your changes

5. Clean up and run tests

.. code-block:: bash

    poe format  # black code formatting
    poe lint  # lint checking
    poe export  # export of requirements (for Github Dependency Graph)
    poe test  # for quicker tests run: poe test -vvvv -m "not (remote or slow)"

6. Push your changes and setup PR

Important Links
***************

`Wetterdienst API`_

Changelog_

.. _Wetterdienst API: https://wetterdienst.readthedocs.io/en/latest/usage/api.html
.. _Changelog: https://wetterdienst.readthedocs.io/en/latest/changelog.html
