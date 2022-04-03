Wetterdienst - Open weather data for humans
###########################################

.. container:: align-center

    .. figure:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/german_weather_stations.png
        :alt: German weather stations managed by Deutscher Wetterdienst

    *“You must be the change you wish to see in the world.” — Gandhi*

    .. figure:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/temperature_ts.png
        :alt: temperature timeseries of Hohenpeissenberg/Germany

    *"Three things are (almost) infinite: the universe, human stupidity and the temperature time series of
    Hohenpeissenberg I got with the help of wetterdienst; and I'm not sure about the universe." - Albert Einstein*

    .. figure:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/hohenpeissenberg_warming_stripes.png
        :alt: warming stripes of Hohenpeissenberg/Germany

    *"We are the first generation to feel the effect of climate change and the last generation who can do something about it." - Barack Obama*

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
   :target: https://pepy.tech/project/wetterdienst
.. image:: https://img.shields.io/github/license/earthobservations/wetterdienst
   :target: https://github.com/earthobservations/wetterdienst/blob/main/LICENSE
.. image:: https://zenodo.org/badge/160953150.svg
   :target: https://zenodo.org/badge/latestdoi/160953150

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

DWD (Deutscher Wetterdienst / German Weather Service / Germany)
    - Historical Weather Observations
        - Historical (last ~300 years), recent (500 days to yesterday), now (yesterday up to last hour)
        - Every minute to yearly resolution
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

ECCC (Environnement et Changement Climatique Canada / Environment and Climate Change Canada / Canada)
    - Historical Weather Observations
        - Historical (last ~180 years)
        - Hourly, daily, monthly, (annual) resolution
        - Time series of stations in Canada

NOAA (National Oceanic And Atmospheric Administration / National Oceanic And Atmospheric Administration / United States Of America)
    - Global Historical Climatology Network
        - Historical, daily weather observations from around the globe
        - more then 100k stations
        - data for weather services which don't publish data themselves

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
- export: Install openpyxl for Excel export and pyarrow for writing files in Feather- and Parquet-format.
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

    wetterdienst --help
    wetterdienst version
    wetterdienst info

Example
*******

Acquisition of historical data for specific stations using ``wetterdienst`` as library:

Load required request class:

.. code-block:: python

    >>> import pandas as pd
    >>> pd.options.display.max_columns = 8
    >>> from wetterdienst.provider.dwd.observation import DwdObservationRequest
    >>> from wetterdienst import Settings

Alternatively, though without argument/type hinting:

.. code-block:: python

    >>> from wetterdienst import Wetterdienst
    >>> API = Wetterdienst("dwd", "observation")

Get data:

.. code-block:: python

    >>> Settings.tidy = True  # default, tidy data
    >>> Settings.humanize = True  # default, humanized parameters
    >>> Settings.si_units = True  # default, convert values to SI units
    >>> request = DwdObservationRequest(
    ...    parameter=["climate_summary"],
    ...    resolution="daily",
    ...    start_date="1990-01-01",  # if not given timezone defaulted to UTC
    ...    end_date="2020-01-01",  # if not given timezone defaulted to UTC
    ... ).filter_by_station_id(station_id=(1048, 4411))
    >>> request.df.head()  # station list
        station_id                 from_date                   to_date  height  \
    ...      01048 1934-01-01 00:00:00+00:00 ... 00:00:00+00:00   228.0
    ...      04411 1979-12-01 00:00:00+00:00 ... 00:00:00+00:00   155.0
    <BLANKLINE>
         latitude  longitude                    name    state
    ...   51.1278    13.7543       Dresden-Klotzsche  Sachsen
    ...   49.9195     8.9671  Schaafheim-Schlierbach   Hessen

    >>> request.values.all().df.head()  # values
      station_id          dataset      parameter                      date  value  \
    0      01048  climate_summary  wind_gust_max 1990-01-01 00:00:00+00:00    NaN
    1      01048  climate_summary  wind_gust_max 1990-01-02 00:00:00+00:00    NaN
    2      01048  climate_summary  wind_gust_max 1990-01-03 00:00:00+00:00    5.0
    3      01048  climate_summary  wind_gust_max 1990-01-04 00:00:00+00:00    9.0
    4      01048  climate_summary  wind_gust_max 1990-01-05 00:00:00+00:00    7.0
    <BLANKLINE>
       quality
    0      NaN
    1      NaN
    2     10.0
    3     10.0
    4     10.0

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

For the whole functionality, check out the `Usage documentation and examples`_ section of our
documentation, which will be constantly updated. To stay up to date with the
development, take a look at the changelog_. Also, don't miss out our examples_.

Data license
************

Licenses of the available data can be found in our documentation at the `data license`_
section. Licenses and usage requirements may differ so check this out before including
the data in your project to be sure to fulfill copyright issues beforehand.

.. _data license: https://wetterdienst.readthedocs.io/en/latest/data/license.html

.. contribution_development_marker

Contribution
************

There are different ways in which you can contribute to this library:

- by handing in a PR which describes the feature/issue that was solved including tests
  for newly added features
- by using our library and reporting bugs to us either by mail or by creating a new
  Issue
- by letting us know either via issue or discussion what function or data source we may
  include into this library describing possible solutions or acquisition
  methods/endpoints/APIs

Development
***********

1. Clone the library and install the environment.

   This setup procedure will outline how to install the library and the minimum
   dependencies required to run the whole test suite. If, for some reason, you
   are not available to install all the packages, just leave out some of the
   "extras" dependency tags.

.. code-block:: bash

    git clone https://github.com/earthobservations/wetterdienst
    cd wetterdienst

    # Prerequisites
    brew install --cask firefox
    brew install git python geckodriver

    # Option 1: Basic
    git clone https://github.com/earthobservations/wetterdienst
    cd wetterdienst
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --requirement=requirements.txt
    python setup.py develop

    # (Option 2: Install package with extras)
    pip install ".[sql,export,restapi,explorer]"

    # Option 3: Install package with extras using poetry.
    poetry install --extras=sql --extras=export --extras=restapi --extras=explorer
    poetry shell

2. For running the whole test suite, you will need to have Firefox and
   geckodriver installed on your machine. Install them like::

       # macOS
       brew install --cask firefox
       brew install geckodriver

       # Other OS
       # You can also get installers and/or release archives for Linux, macOS
       # and Windows at
       #
       # - https://www.mozilla.org/en-US/firefox/new/
       # - https://github.com/mozilla/geckodriver/releases

   If this does not work for some reason and you would like to skip ui-related
   tests on your machine, please invoke the test suite with::

       poe test -m "not ui"

3. Edit the source code, add corresponding tests and documentation for your
   changes. While editing, you might want to continuously run the test suite
   by invoking::

       poe test

   In order to run only specific tests, invoke::

       # Run tests by module name or function name.
       poe test -k test_cli

       # Run tests by tags.
       poe test -m "not (remote or slow)"

4. Before committing your changes, please als run those steps in order to make
   the patch adhere to the coding standards used here.

.. code-block:: bash

    poe format  # black code formatting
    poe lint    # lint checking
    poe export  # export of requirements (for Github Dependency Graph)

5. Push your changes and submit them as pull request

   Thank you in advance!


.. note::

    If you need to extend the list of package dependencies, invoke:

    .. code-block:: bash

        # Add package to runtime dependencies.
        poetry add new-package

        # Add package to development dependencies.
        poetry add --dev new-package



Known Issues
************

MAC ARM64 (M1)
==============

You need to install **pandas, numpy and scipy** as follows before continuing with the regular setup:

.. code-block:: bash

    pip install pandas --no-use-pep517
    pip install numpy --no-use-pep517
    pip install --no-binary :all: --no-use-pep517 scipy

Further additional libraries are affected and have to be installed in a similar manner:

.. code-block:: bash

    # SQL related
    brew install postgresql
    brew link openssl (and export ENVS as given)
    pip install psycopg2-binary --no-use-pep517

LINUX ARM (Raspberry Pi)
========================

Running wetterdienst on Raspberry Pi, you need to install **numpy**
and **lxml** prior to installing wetterdienst running the following
lines:

.. code-block:: bash

    sudo apt-get install libatlas-base-dev
    sudo apt-get install python3-lxml

Important Links
***************

- `Usage documentation and examples`_
- `Changelog`_

.. _Usage documentation and examples: https://wetterdienst.readthedocs.io/en/latest/usage/
.. _Changelog: https://wetterdienst.readthedocs.io/en/latest/changelog.html
