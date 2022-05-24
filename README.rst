Wetterdienst - Open weather data for humans
###########################################

.. |pic1| image:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/german_weather_stations.png
    :alt: German weather stations managed by Deutscher Wetterdienst
    :width: 32 %

.. |pic2| image:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/temperature_ts.png
    :alt: temperature timeseries of Hohenpeissenberg/Germany
    :width: 32 %

.. |pic3| image:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/hohenpeissenberg_warming_stripes.png
    :alt: warming stripes of Hohenpeissenberg/Germany
    :width: 32 %

|pic1| |pic2| |pic3|

**What our customers say:**

"Our house is on fire. I am here to say, our house is on fire. I saw it with my own eyes using **wetterdienst**
to get the data." - Greta Thunberg

“You must be the change you wish to see in the world. And when it comes to climate I use **wetterdienst**.” - Mahatma Gandhi

"Three things are (almost) infinite: the universe, human stupidity and the temperature time series of
Hohenpeissenberg, Germany I got with the help of **wetterdienst**; and I'm not sure about the universe." - Albert Einstein

"We are the first generation to feel the effect of climate change and the last generation who can do something about
it. I used **wetterdienst** to analyze the climate in my area and I can tell it's getting hot in here." - Barack Obama

.. image:: https://github.com/earthobservations/wetterdienst/workflows/Tests/badge.svg
   :target: https://github.com/earthobservations/wetterdienst/actions?workflow=Tests
   :alt: CI: Overall outcome
.. image:: https://codecov.io/gh/earthobservations/wetterdienst/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/earthobservations/wetterdienst
   :alt: CI: Code coverage
.. image:: https://img.shields.io/pypi/v/wetterdienst.svg
   :target: https://pypi.org/project/wetterdienst/
   :alt: PyPI version
.. image:: https://img.shields.io/conda/vn/conda-forge/wetterdienst.svg
   :target: https://anaconda.org/conda-forge/wetterdienst
   :alt: Conda version

.. image:: https://img.shields.io/pypi/status/wetterdienst.svg
   :target: https://pypi.python.org/pypi/wetterdienst/
   :alt: Project status (alpha, beta, stable)
.. image:: https://static.pepy.tech/personalized-badge/wetterdienst?period=month&units=international_system&left_color=grey&right_color=blue&left_text=PyPI%20downloads/month
   :target: https://pepy.tech/project/wetterdienst
   :alt: PyPI downloads
.. image:: https://img.shields.io/conda/dn/conda-forge/wetterdienst.svg?label=Conda%20downloads
   :target: https://anaconda.org/conda-forge/wetterdienst
   :alt: Conda downloads
.. image:: https://img.shields.io/github/license/earthobservations/wetterdienst
   :target: https://github.com/earthobservations/wetterdienst/blob/main/LICENSE
   :alt: Project license
.. image:: https://img.shields.io/pypi/pyversions/wetterdienst.svg
   :target: https://pypi.python.org/pypi/wetterdienst/
   :alt: Python version compatibility

.. image:: https://readthedocs.org/projects/wetterdienst/badge/?version=latest
   :target: https://wetterdienst.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation status
.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Documentation: Black

.. image:: https://zenodo.org/badge/160953150.svg
   :target: https://zenodo.org/badge/latestdoi/160953150
   :alt: Citation reference


.. overview_start_marker

Introduction
############

Overview
********

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

Data
****

For an overview of the data we have currently made available and under which
license it is published take a look at the data_ section. Detailed information
on datasets and parameters is given at the coverage_ subsection. Licenses and
usage requirements may differ for each provider so check this out before including
the data in your project to be sure that you fulfill copyright requirements!

.. _data: https://wetterdienst.readthedocs.io/en/latest/data/index.html
.. _coverage: https://wetterdienst.readthedocs.io/en/improve-documentation/data/coverage.html

Here is a short glimpse on the data that is included:

.. coverage_start_marker

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

WSV (Wasserstraßen- und Schifffahrtsverwaltung des Bundes / Federal Waterways and Shipping Administration)
    - Pegelonline
        - data of river network of Germany
        - coverage of last 30 days
        - parameters like stage, runoff and more related to rivers

EA (Environment Agency)
    - Hydrology
        - data of river network of UK
        - parameters flow and ground water stage

NWS (NOAA National Weather Service)
    - Observation
        - recent observations (last week) of US weather stations
        - currently the list of stations is not completely right as we use a diverging source!
Eaufrance
    - Hubeau
        - data of river network of France (continental)
        - parameters flow and stage of rivers of last 30 days

To get better insight on which data we have currently made available and under which
license those are published take a look at the data_ section.

.. coverage_end_marker

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
- Interpolation and Summary of station values

Setup
*****

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
- interpolation: Install support for station interpolation.

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

**Task: Get historical climate summary for two German stations between 1990 and 2020**

Library
=======

.. code-block:: python

    >>> import pandas as pd
    >>> pd.options.display.max_columns = 8
    >>> from wetterdienst import Settings
    >>> from wetterdienst.provider.dwd.observation import DwdObservationRequest
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

Client
======

.. code-block:: bash

    # Get list of all stations for daily climate summary data in JSON format
    wetterdienst stations --provider=dwd --network=observations --parameter=kl --resolution=daily

    # Get daily climate summary data for specific stations
    wetterdienst values --provider=dwd --network=observations --station=1048,4411 --parameter=kl --resolution=daily

Further examples (code samples) can be found in the examples_ folder.

.. _examples: https://github.com/earthobservations/wetterdienst/tree/main/example

.. overview_end_marker

Acknowledgements
****************

We want to acknowledge all environmental agencies which provide their data open and free
of charge first and foremost for the sake of endless research possibilities.

We want to acknowledge Jetbrains_ and the `Jetbrains OSS Team`_ for providing us with
licenses for Pycharm Pro, which we are using for the development.

We want to acknowledge all contributors for being part of the improvements to this
library that make it better and better every day.

.. _Jetbrains: https://www.jetbrains.com/
.. _Jetbrains OSS Team: https://github.com/JetBrains

Important Links
***************

- Full documentation: https://wetterdienst.readthedocs.io/
- Usage: https://wetterdienst.readthedocs.io/en/latest/usage/
- Contribution: https://wetterdienst.readthedocs.io/en/latest/contribution/
- Known Issues: https://wetterdienst.readthedocs.io/en/latest/known_issues/
- Changelog: https://wetterdienst.readthedocs.io/en/latest/changelog.html
- Examples (runnable scripts): https://github.com/earthobservations/wetterdienst/tree/main/example
- Benchmarks: https://github.com/earthobservations/wetterdienst/tree/main/benchmarks
