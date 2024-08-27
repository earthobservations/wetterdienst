Wetterdienst - Open weather data for humans
###########################################

.. |pic1| image:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/german_weather_stations.png
    :alt: German weather stations managed by Deutscher Wetterdienst
    :width: 32%

.. |pic2| image:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/temperature_ts.png
    :alt: temperature timeseries of Hohenpeissenberg/Germany
    :width: 32%

.. |pic3| image:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/hohenpeissenberg_warming_stripes.png
    :alt: warming stripes of Hohenpeissenberg/Germany
    :width: 32%

|pic1| |pic2| |pic3|

..

    **"What do we want? Climate Justice! When do we want it? Now!" - FFF**

..

    **WARNING**

    This library is a work in progress!

    Breaking changes should be expected until a 1.0 release, so version pinning is recommended.

**CI**

.. image:: https://github.com/earthobservations/wetterdienst/actions/workflows/tests.yml/badge.svg?branch=main
   :target: https://github.com/earthobservations/wetterdienst/actions?workflow=Tests
   :alt: CI: Overall outcome
.. image:: https://readthedocs.org/projects/wetterdienst/badge/?version=latest
   :target: https://wetterdienst.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation status
.. image:: https://codecov.io/gh/earthobservations/wetterdienst/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/earthobservations/wetterdienst
   :alt: CI: Code coverage

**Meta**

.. image:: https://img.shields.io/pypi/v/wetterdienst.svg
   :target: https://pypi.org/project/wetterdienst/
   :alt: PyPI version
.. image:: https://img.shields.io/conda/vn/conda-forge/wetterdienst.svg
   :target: https://anaconda.org/conda-forge/wetterdienst
   :alt: Conda version
.. image:: https://img.shields.io/github/license/earthobservations/wetterdienst
   :target: https://github.com/earthobservations/wetterdienst/blob/main/LICENSE
   :alt: Project license
.. image:: https://img.shields.io/pypi/status/wetterdienst.svg
   :target: https://pypi.python.org/pypi/wetterdienst/
   :alt: Project status (alpha, beta, stable)
.. image:: https://img.shields.io/pypi/pyversions/wetterdienst.svg
   :target: https://pypi.python.org/pypi/wetterdienst/
   :alt: Python version compatibility

**Downloads**

.. image:: https://static.pepy.tech/personalized-badge/wetterdienst?period=month&units=international_system&left_color=grey&right_color=blue&left_text=PyPI%20downloads/month
   :target: https://pepy.tech/project/wetterdienst
   :alt: PyPI downloads
.. image:: https://img.shields.io/conda/dn/conda-forge/wetterdienst.svg?label=Conda%20downloads
   :target: https://anaconda.org/conda-forge/wetterdienst
   :alt: Conda downloads

**Citation**

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
Python technologies all over the place. The library is based on polars_ (we <3 pandas_, it is still part of some
IO processes) across the board, uses uv_ for package administration and GitHub Actions for all things CI.
Our users are an important part of the development as we are not currently using the
data we are providing and only implement what we think would be the best. Therefore
contributions and feedback whether it be data related or library related are very
welcome! Just hand in a PR or Issue if you think we should include a new feature or data
source.

.. _rdwd: https://github.com/brry/rdwd
.. _polars: https://www.pola.rs/
.. _pandas: https://pandas.pydata.org/
.. _uv: https://github.com/astral-sh/uv

Data
****

.. _data: https://wetterdienst.readthedocs.io/en/latest/data/index.html
.. _coverage: https://wetterdienst.readthedocs.io/en/improve-documentation/data/coverage.html
.. _map: https://bookdown.org/brry/rdwd/interactive-map.html
.. _table: https://bookdown.org/brry/rdwd/available-datasets.html

For an overview of the data we have currently made available and under which
license it is published take a look at the data_ section. Detailed information
on datasets and parameters is given at the coverage_ subsection. Licenses and
usage requirements may differ for each provider so check this out before including
the data in your project to be sure that you fulfill copyright requirements!

Features
********

- APIs for stations and values
- Get stations nearby a selected location
- Define your request by arguments such as `parameter`, `period`, `resolution`,
  `start date`, `end date`
- Define general settings in Settings context
- Command line interface
- Web-API via FastAPI, hosted on `wetterdienst.eobs.org <https://wetterdienst.eobs.org>`_
- Rich UI features like `explorer <https://wetterdienst.streamlit.app>`_, `stripes <https://stripes.streamlit.app>`_
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

    pip install wetterdienst[sql]

- docs: Install the Sphinx documentation generator.
- ipython: Install iPython stack.
- export: Install openpyxl for Excel export and pyarrow for writing files in Feather- and Parquet-format.
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

``wetterdienst`` serves a full environment, including *all* of the optional dependencies of Wetterdienst.

Pull the Docker image:

.. code-block:: bash

    docker pull ghcr.io/earthobservations/wetterdienst

Library
-------

Use the latest stable version of ``wetterdienst``:

.. code-block:: bash

    $ docker run -ti ghcr.io/earthobservations/wetterdienst
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
    alias wetterdienst='docker run -ti ghcr.io/earthobservations/wetterdienst wetterdienst'

    wetterdienst --help
    wetterdienst --version
    wetterdienst info


Raspberry Pi / LINUX ARM
========================

Running wetterdienst on Raspberry Pi, you need to install **numpy**
and **lxml** prior to installing wetterdienst by running the following
lines:

.. code-block:: bash

    # not all installations may be required to get lxml running
    sudo apt-get install gfortran
    sudo apt-get install libopenblas-base
    sudo apt-get install libopenblas-dev
    sudo apt-get install libatlas-base-dev
    sudo apt-get install python3-lxml

Additionally expanding the Swap to 2048 mb may be required and can be done via swap-file:

.. code-block:: bash

    sudo nano /etc/dphys-swapfile

Thanks `chr-sto`_ for reporting back to us!


.. _chr-sto: https://github.com/chr-sto

Example
*******

**Task: Get historical climate summary for two German stations between 1990 and 2020**

Library
=======

.. code-block:: python

    >>> import polars as pl
    >>> _ = pl.Config.set_tbl_hide_dataframe_shape(True)
    >>> from wetterdienst import Settings
    >>> from wetterdienst.provider.dwd.observation import DwdObservationRequest
    >>> settings = Settings( # default
    ...     ts_shape="long",  # tidy data
    ...     ts_humanize=True,  # humanized parameters
    ...     ts_si_units=True  # convert values to SI units
    ... )
    >>> request = DwdObservationRequest(
    ...    parameter="climate_summary",
    ...    resolution="daily",
    ...    start_date="1990-01-01",  # if not given timezone defaulted to UTC
    ...    end_date="2020-01-01",  # if not given timezone defaulted to UTC
    ...    settings=settings
    ... ).filter_by_station_id(station_id=(1048, 4411))
    >>> stations = request.df
    >>> stations.head()
    ┌────────────┬──────────────┬──────────────┬──────────┬───────────┬────────┬─────────────┬─────────┐
    │ station_id ┆ start_date   ┆ end_date     ┆ latitude ┆ longitude ┆ height ┆ name        ┆ state   │
    │ ---        ┆ ---          ┆ ---          ┆ ---      ┆ ---       ┆ ---    ┆ ---         ┆ ---     │
    │ str        ┆ datetime[μs, ┆ datetime[μs, ┆ f64      ┆ f64       ┆ f64    ┆ str         ┆ str     │
    │            ┆ UTC]         ┆ UTC]         ┆          ┆           ┆        ┆             ┆         │
    ╞════════════╪══════════════╪══════════════╪══════════╪═══════════╪════════╪═════════════╪═════════╡
    │ 01048      ┆ 1934-01-01   ┆ ...          ┆ 51.1278  ┆ 13.7543   ┆ 228.0  ┆ Dresden-Klo ┆ Sachsen │
    │            ┆ 00:00:00 UTC ┆ 00:00:00 UTC ┆          ┆           ┆        ┆ tzsche      ┆         │
    │ 04411      ┆ 1979-12-01   ┆ ...          ┆ 49.9195  ┆ 8.9672    ┆ 155.0  ┆ Schaafheim- ┆ Hessen  │
    │            ┆ 00:00:00 UTC ┆ 00:00:00 UTC ┆          ┆           ┆        ┆ Schlierbach ┆         │
    └────────────┴──────────────┴──────────────┴──────────┴───────────┴────────┴─────────────┴─────────┘
    >>> values = request.values.all().df
    >>> values.head()
    ┌────────────┬─────────────────┬───────────────────┬─────────────────────────┬───────┬─────────┐
    │ station_id ┆ dataset         ┆ parameter         ┆ date                    ┆ value ┆ quality │
    │ ---        ┆ ---             ┆ ---               ┆ ---                     ┆ ---   ┆ ---     │
    │ str        ┆ str             ┆ str               ┆ datetime[μs, UTC]       ┆ f64   ┆ f64     │
    ╞════════════╪═════════════════╪═══════════════════╪═════════════════════════╪═══════╪═════════╡
    │ 01048      ┆ climate_summary ┆ cloud_cover_total ┆ 1990-01-01 00:00:00 UTC ┆ 100.0 ┆ 10.0    │
    │ 01048      ┆ climate_summary ┆ cloud_cover_total ┆ 1990-01-02 00:00:00 UTC ┆ 100.0 ┆ 10.0    │
    │ 01048      ┆ climate_summary ┆ cloud_cover_total ┆ 1990-01-03 00:00:00 UTC ┆ 91.25 ┆ 10.0    │
    │ 01048      ┆ climate_summary ┆ cloud_cover_total ┆ 1990-01-04 00:00:00 UTC ┆ 28.75 ┆ 10.0    │
    │ 01048      ┆ climate_summary ┆ cloud_cover_total ┆ 1990-01-05 00:00:00 UTC ┆ 91.25 ┆ 10.0    │
    └────────────┴─────────────────┴───────────────────┴─────────────────────────┴───────┴─────────┘

.. code-block:: python

    values.to_pandas() # to get a pandas DataFrame and e.g. create some matplotlib plots

Client
======

.. code-block:: bash

    # Get list of all stations for daily climate summary data in JSON format
    wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --all

    # Get daily climate summary data for specific stations
    wetterdienst values --provider=dwd --network=observation --station=1048,4411 --parameter=kl --resolution=daily

Further examples (code samples) can be found in the examples_ folder.

.. _examples: https://github.com/earthobservations/wetterdienst/tree/main/examples

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

- Restapi: https://wetterdienst.eobs.org/
- Explorer: https://wetterdienst.streamlit.app/
- Stripes: https://stripes.streamlit.app/
- Documentation: https://wetterdienst.readthedocs.io/

  - Usage: https://wetterdienst.readthedocs.io/en/latest/usage/
  - Contribution: https://wetterdienst.readthedocs.io/en/latest/contribution/
  - Changelog: https://wetterdienst.readthedocs.io/en/latest/changelog.html

- Examples (runnable scripts): https://github.com/earthobservations/wetterdienst/tree/main/examples
- Benchmarks: https://github.com/earthobservations/wetterdienst/tree/main/benchmarks


.. _Polars DataFrame: https://pola-rs.github.io/polars/py-polars/html/reference/dataframe/
